"""Pinned T5b batch/anchor/reuse executor. Main dispatch only; no cloud actions.

Builds use the frozen native_source_gate_v1 policy unchanged. Reuse never
compiles: it requires a separately hash-approved successful AW16 anchor report
and independent review, identical source/harness/config/tools, and exact ELF.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import socket
import subprocess
import tarfile
import time
import types

SELF='tools/native_t5b_qualification_v1.py'
HELPER='tools/native_source_gate_v1.py'
HELPER_SHA='5205f587313a1403fddabff58bbcf4565d27c8219aa2e0c3f4aaa3af2901c2cd'
NATIVE_BASE=Path('/home/jtl/gfn-fpga-lab/agent-work/core27-t5b-qualification-v1')
NATIVE_ROOT=NATIVE_BASE/'snapshot-v1/fpga'
GIB=1<<30


def need(ok,why):
    if not ok:raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def regular(root,name):
    p=Path(name);path=root/p
    need(type(name) is str and not p.is_absolute() and '..' not in p.parts and str(p)==name
         and path.is_file() and not path.is_symlink() and path.stat().st_nlink==1 and path.resolve().is_relative_to(root),'safe input '+name)
    return path


def read_pinned(path,digest):
    need(re.fullmatch('[0-9a-f]{64}',digest or '') and path.is_file() and not path.is_symlink() and sha(path)==digest,'approved file SHA')
    return json.loads(path.read_text())


def verify_bundle(path,digest,root):
    bundle=read_pinned(path,digest)
    need(bundle['schema']=='t5b-qualification-v1' and bundle['status']=='prepared_not_executed'
         and bundle['host']=='aethia' and bundle['source_root']==str(NATIVE_ROOT)
         and bundle['output_parent']==str(NATIVE_BASE),'exact qualification profile')
    need(root.is_dir() and root.resolve()==root,'canonical input tree')
    actual=set()
    for p in root.rglob('*'):
        need(not p.is_symlink(),'input symlink')
        if p.is_file():actual.add(str(p.relative_to(root)))
    need(actual==set(bundle['sources']),'exact source closure before imports')
    for name,pin in bundle['sources'].items():need(sha(regular(root,name))==pin,'input pin '+name)
    need(bundle['sources'].get(HELPER)==HELPER_SHA and SELF in bundle['sources'],'frozen launcher/self closure')
    roles={}
    need(set(bundle['roles'])=={'shared-control','aw16-anchor'}|set(bundle['mutations']),'closed role set')
    need(len(bundle['mutations'])==8,'eight contracts only')
    for role,item in bundle['roles'].items():
        need(Path(item['manifest']).name==item['manifest'],'role manifest basename')
        manifest=read_pinned(path.parent/item['manifest'],item['sha256'])
        need(manifest['schema']=='native-source-gate-v1' and manifest['status']=='prepared_not_executed'
             and manifest['host']=='aethia' and manifest['source_root']==bundle['source_root']
             and manifest['output_parent']==bundle['output_parent'] and manifest['sources']==bundle['sources'],'role source/profile equality')
        roles[role]=manifest
    need(roles['aw16-anchor']['build']==bundle['reuse_build'],'exact AW16 reuse configuration')
    return bundle,roles


def source_review(path,digest,bundle,manifest_sha):
    review=read_pinned(path,digest)
    need(review['status'].startswith('PASS_') and review['manifest_sha256']==manifest_sha
         and review['sources']==bundle['sources'],'independent source admission binding')


def load_helper(root):
    namespace={'__file__':str(root/HELPER),'__name__':'_pinned_t5b_native_helper'}
    exec(compile((root/HELPER).read_bytes(),str(root/HELPER),'exec'),namespace)
    return types.SimpleNamespace(**namespace)


def archive_inventory(path):
    result={}
    with tarfile.open(path,'r:gz') as archive:
        for item in archive:
            need(item.isfile() and not Path(item.name).is_absolute() and '..' not in Path(item.name).parts
                 and item.name not in result,'safe unique regular archive member')
            result[item.name]=hashlib.file_digest(archive.extractfile(item),'sha256').hexdigest()
    return result


def completed_report(out,manifest,manifest_sha,helper,root):
    report=json.loads(regular(out,'report.json').read_text())
    need(report['status']=='completed_native_commands_unreviewed' and report['manifest_sha256']==manifest_sha
         and report['sources']==manifest['sources'],'successful source-bound predecessor')
    need(sha(regular(out,'approved-manifest.json'))==manifest_sha,'preserved approved manifest')
    for name,pin in report['artifacts'].items():need(sha(regular(out,name))==pin,'artifact drift '+name)
    need(archive_inventory(out/'sources.tar.gz')==manifest['sources'],'source archive closure')
    need(archive_inventory(out/'generated-sources.tar.gz')==report['generated_source_sha256'],'generated archive closure')
    paths=helper.tools_for(helper.PROFILES['aethia'])
    need(report['tool_sha256']=={str(p):sha(p) for p in paths.values()},'same native host/tool fingerprint')
    names=['verilator-version','compiler-version','build','probe']+[s['name'] for s in manifest['steps']]
    need([s['name'] for s in report['steps']]==names,'complete ordered native steps')
    build=manifest['build'];directory=Path(report['scratch'])/'build';exe=directory/('V'+build['top'])
    need(directory.parent.parent==Path('/dev/shm') and directory.parent.name.startswith('gfn16-source-gate-'),'original bounded build directory')
    prefix=[str(paths['taskset']),'-c','4,6']
    expected=prefix+[str(paths['verilator']),'--cc','--exe','--build','-j','2','--threads','1','--top-module',build['top'],
        *[f'-G{k}={v}' for k,v in build['parameters'].items()],'-CFLAGS',' '.join(build['cflags']),'--Mdir',str(directory),
        *[str(root/n) for n in build['sv_sources']],str(root/build['cpp_source'])]
    need(report['steps'][2]['command']==expected,'exact ordered RTL/harness/config build')
    need(report['probe']==manifest['probe']['expected_json']==dict(context_threads=1,model_threads=1,expected_threads=1),'one-thread probe')
    need(report['steps'][3]['command']==prefix+helper.expand(manifest['probe']['argv'],exe,root),'exact probe command')
    for step in report['steps'][:4]:need(step['returncode']==0 and step.get('error') is None,'successful build/probe')
    for actual,wanted in zip(report['steps'][4:],manifest['steps']):
        need(actual['command']==prefix+helper.expand(wanted['argv'],exe,root)
             and actual['returncode']==wanted['expected_returncode'] and actual.get('error') is None,'exact case argv/exit')
        for key,suffix in [('expected_stdout','.log'),('expected_stderr','.stderr.log')]:
            if key in wanted:need((out/(wanted['name']+suffix)).read_text()==wanted[key],'exact output '+wanted['name'])
    with gzip.open(out/'model.gz','rb') as stream:data=stream.read()
    need(data.startswith(b'\x7fELF') and hashlib.sha256(data).hexdigest()==report['executable_sha256'],'native ELF archive identity')
    return report


def typed_fatal(output,returncode,contract):
    need(returncode==-6 and 'T5_TARGET_PASS' not in output,'SIGABRT not success/build/timeout')
    errors=re.findall(r'^.*%(?:Fatal|Error):\s+(\S+):(\d+): Assertion failed in (\S+): (.*)$',output,re.M)
    need(len(errors)==1,'exactly one typed native observer fatal')
    filename,line,scope,message=errors[0]
    need(Path(filename).name==Path(contract['observer']).name and int(line) in contract['lines']
         and (scope==contract['required_scope'] or scope.startswith(contract['required_scope']+'.'))
         and message.strip()==contract['fatal'],'observer basename/line/scope/message attribution')
    return dict(signal=6,source_line=int(line),scope=scope,fatal=message.strip())


def execute(bundle_path,bundle_sha,review_path,review_sha,mode,out,group=None,prior_path=None,prior_sha=None,prior_review_path=None,prior_review_sha=None):
    need(__debug__ and socket.gethostname()=='aethia','native aethia only')
    root=Path(__file__).resolve().parents[1]
    need(root==NATIVE_ROOT and Path.cwd()==root,'fixed snapshot/cwd')
    bundle,roles=verify_bundle(bundle_path,bundle_sha,root);source_review(review_path,review_sha,bundle,bundle_sha)
    helper=load_helper(root);profile=helper.PROFILES['aethia'];helper.tools_for(profile);limits=helper.execution_limits([4,6])
    need(out.parent==NATIVE_BASE and out.resolve()==out and not out.exists(),'fresh bounded output')
    need(mode in ('mutants','anchor','reuse'),'explicit qualification mode')
    if mode=='anchor':
        need(out.name=='aw16-anchor-v1' and group is None,'one fresh AW16 anchor')
        item=bundle['roles']['aw16-anchor']
        result=helper.execute(bundle_path.parent/item['manifest'],item['sha256'],out)
        verify_bundle(bundle_path,bundle_sha,root);source_review(review_path,review_sha,bundle,bundle_sha)
        return result
    if mode=='mutants':
        need(out.name=='mutants-v1' and group is None,'one complete eight-mutant batch')
        out.mkdir();started=time.monotonic();report=dict(status='running',mode=mode,manifest_sha256=bundle_sha,
            source_review_sha256=review_sha,sources=bundle['sources'],receipts=[],artifacts={},active_role='shared-control',
            role_outputs={name:str(NATIVE_BASE/('shared-control-v1' if name=='shared-control' else 'mutant-'+name+'-v1'))
                for name in ['shared-control']+bundle['mutations']},scope='eight typed negatives only; no physical promotion')
        def save():(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        try:
            save()
            shared=bundle['roles']['shared-control'];control_out=NATIVE_BASE/'shared-control-v1'
            helper.execute(bundle_path.parent/shared['manifest'],shared['sha256'],control_out)
            control=completed_report(control_out,roles['shared-control'],shared['sha256'],helper,root)
            for name in bundle['mutations']:
                need(time.monotonic()-started<3600,'batch overall budget')
                verify_bundle(bundle_path,bundle_sha,root)
                report['active_role']=name;save()
                item=bundle['roles'][name];target=NATIVE_BASE/('mutant-'+name+'-v1')
                helper.execute(bundle_path.parent/item['manifest'],item['sha256'],target)
                result=completed_report(target,roles[name],item['sha256'],helper,root)
                contract=bundle['contracts'][name];step=roles[name]['steps'][0]
                control_step=next(s for s in roles['shared-control']['steps'] if s['name']=='control-'+name.replace('_','-'))
                need(step['argv']==control_step['argv'],'identical control/mutant invocation')
                rejection=typed_fatal((target/(step['name']+'.log')).read_text()+(target/(step['name']+'.stderr.log')).read_text(),result['steps'][-1]['returncode'],contract)
                receipt=dict(name=name,status='passed_typed_mutation_with_shared_fresh_control',typed_rejection=rejection,
                    contract=contract,control_report_sha256=sha(control_out/'report.json'),mutant_report_sha256=sha(target/'report.json'),
                    control_executable_sha256=control['executable_sha256'],mutant_executable_sha256=result['executable_sha256'],
                    manifest_sha256=bundle_sha,role_manifest_sha256=item['sha256'],source_review_sha256=review_sha)
                path=out/('receipt-'+name+'.json');path.write_text(json.dumps(receipt,indent=2)+'\n')
                report['receipts'].append(path.name);report['artifacts'][path.name]=sha(path);save()
            need(len(report['receipts'])==8,'all eight typed negatives')
            verify_bundle(bundle_path,bundle_sha,root);source_review(review_path,review_sha,bundle,bundle_sha)
            need(time.monotonic()-started<3600,'batch overall budget')
            need(all(sha(out/n)==h for n,h in report['artifacts'].items()),'batch receipt drift')
            report['active_role']=None
            report['status']='passed_eight_typed_mutation_contracts_only'
        except BaseException as error:report.update(status='failed_or_incomplete',error=repr(error));raise
        finally:report['seconds']=time.monotonic()-started;save()
        return report
    need(group in bundle['reuse_groups'] and out.name=='reuse-'+group+'-v1','one bounded prepared reuse group')
    need(prior_path==NATIVE_BASE/'aw16-anchor-v1/report.json','only own successful AW16 anchor may be reused')
    prior=read_pinned(prior_path,prior_sha);anchor=bundle['roles']['aw16-anchor']
    need(prior==completed_report(prior_path.parent,roles['aw16-anchor'],anchor['sha256'],helper,root),'full anchor replay')
    review=read_pinned(prior_review_path,prior_review_sha)
    need(review['status'].startswith('PASS_') and review['pins']['report_sha256']==prior_sha
         and review['pins']['manifest_sha256']==anchor['sha256'],'independent anchor admission')
    need(roles['aw16-anchor']['build']==bundle['reuse_build'],'no foreign RTL/harness/config reuse')
    resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(4*GIB,4*GIB))
    out.mkdir();started=time.monotonic();temporary=out/'tmp';temporary.mkdir()
    report=dict(status='running',mode=mode,group=group,sources=bundle['sources'],manifest_sha256=bundle_sha,
        source_review_sha256=review_sha,anchor_report_sha256=prior_sha,anchor_review_sha256=prior_review_sha,
        build_configuration=bundle['reuse_build'],executable_sha256=prior['executable_sha256'],tool_sha256=prior['tool_sha256'],
        limits=limits,compile_allowed=False,compile_workers=0,model_threads=1,steps=[],artifacts={},
        scope='one selected full-N group only; no aggregate/clock promotion')
    def save():(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    def remember(p):report['artifacts'][str(p.relative_to(out))]=sha(p)
    def guard():
        need(time.monotonic()-started<3600,'reuse overall timeout')
        need(shutil.disk_usage(out).free>=10*GIB,'durable10GiB floor')
        available=int(next(row.split()[1] for row in Path('/proc/meminfo').read_text().splitlines() if row.startswith('MemAvailable:')))*1024
        need(available>=4*GIB,'host4GiB floor')
    def recheck():
        guard();verify_bundle(bundle_path,bundle_sha,root)
        need(sha(prior_path)==prior_sha and sha(prior_review_path)==prior_review_sha and sha(review_path)==review_sha,'evidence drift')
        helper.tools_for(profile)
        if (out/'model').exists():need(sha(out/'model')==prior['executable_sha256'],'reused ELF drift')
    def interrupted(signum,frame):raise RuntimeError('termination requested')
    previous=signal.signal(signal.SIGTERM,interrupted)
    try:
        recheck()
        for source,name in [(bundle_path,'approved-bundle.json'),(review_path,'source-review.json'),(prior_path,'anchor-report.json'),(prior_review_path,'anchor-review.json'),(prior_path.parent/'model.gz','model.gz')]:
            shutil.copyfile(source,out/name);remember(out/name)
        with tarfile.open(out/'sources.tar.gz','x:gz') as archive:
            for name in sorted(bundle['sources']):archive.add(root/name,arcname=name,recursive=False)
        remember(out/'sources.tar.gz')
        with gzip.open(out/'model.gz','rb') as source,(out/'model').open('xb') as dest:shutil.copyfileobj(source,dest)
        (out/'model').chmod(0o500);remember(out/'model');recheck()
        steps=[dict(name='probe',argv=['{exe}','--runtime-probe'],expected_returncode=0)]+bundle['reuse_groups'][group]
        for step in steps:
            recheck();before=time.monotonic();failure=None;command=['/usr/bin/taskset','-c','4,6',*helper.expand(step['argv'],out/'model',root)]
            stdout=out/(step['name']+'.log');stderr=out/(step['name']+'.stderr.log')
            with stdout.open('x') as so,stderr.open('x') as se:
                child=subprocess.Popen(command,cwd=root,env=helper.clean_env(root,temporary,profile),stdout=so,stderr=se,start_new_session=True)
                try:
                    while child.poll() is None:guard();need(time.monotonic()-before<1800,'case timeout');time.sleep(.25)
                except BaseException as error:
                    failure=error
                    try:os.killpg(child.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    child.wait()
            remember(stdout);remember(stderr)
            report['steps'].append(dict(name=step['name'],command=command,returncode=child.returncode,seconds=time.monotonic()-before,
                error=repr(failure) if failure else None,log=stdout.name,sha256=sha(stdout),stderr_log=stderr.name,stderr_sha256=sha(stderr)));save()
            if failure:raise failure
            need(child.returncode==0 and stderr.read_text()=='','successful clean native process')
            if step['name']=='probe':need(json.loads(stdout.read_text())==dict(context_threads=1,model_threads=1,expected_threads=1),'fresh reused probe')
            else:need(stdout.read_text()==step['expected_stdout'],'exact command-bound fault footer')
        recheck();need(all(sha(out/n)==h for n,h in report['artifacts'].items()),'terminal artifact drift')
        report['status']='passed_selected_aw16_group_reuse_only'
    except BaseException as error:report.update(status='failed_or_incomplete',error=repr(error));raise
    finally:report['seconds']=time.monotonic()-started;save();signal.signal(signal.SIGTERM,previous)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('bundle','source-review','output','prior-report','prior-review'):parser.add_argument('--'+name,type=Path,required=name in ('bundle','source-review','output'))
    for name in ('bundle-sha','source-review-sha','prior-report-sha','prior-review-sha'):parser.add_argument('--'+name,required=name in ('bundle-sha','source-review-sha'))
    parser.add_argument('--mode',choices=('mutants','anchor','reuse'),required=True);parser.add_argument('--group')
    a=parser.parse_args()
    print(json.dumps(execute(a.bundle,a.bundle_sha,a.source_review,a.source_review_sha,a.mode,a.output,a.group,a.prior_report,a.prior_report_sha,a.prior_review,a.prior_review_sha),indent=2))
