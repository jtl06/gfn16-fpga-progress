"""Explicit recovery of the preserved small-v1 point-root test-coverage failure.

Reuses only hash-verified completed evidence; adds an AW14 folded-half boundary
control and the identical escaped mutant, then executes the three unrun faults.
No original report, source, executable, vector or log is overwritten.
"""
import argparse
import json
from pathlib import Path
import re
import resource
import socket
import subprocess

from .ntt27_rootpipe_full_regression import FullLab,digest,resources,ENGINE_SHA,BENCH_SHA,HARNESS_SHA
from .ntt27_rootpipe_regression import bench_proof,validate_files,cache_context,EXPERIMENT_PRIMES

OLD_FAULTS=['upper-control','rotation','cut-word','data-delay','valid-delay','row-tag','orientation-tag','point-half-tag']


def boundary_proof():
    def bank(a):return (a&127)^((a>>7)&127)^((a>>14)&127)
    halves=[(bank(g<<6)>>6)&1 for g in range(256)]
    repeat=[g for g in range(255) if halves[g]==halves[g+1]]
    if repeat!=[127]:raise RuntimeError('unexpected first repeated half')
    # At that pair, physical bank127 changes from row63/logical8128 to
    # row64/logical8255 on consecutive reads. An undelayed root word is wrong.
    logical_old=(63<<7)|(127^63);logical_new=(64<<7)|(127^64)
    if (logical_old,logical_new)!=(8128,8255):raise RuntimeError('row inverse mismatch')
    return dict(first_same_half_groups=[127,128],read_bases=[8128,8192],rows=[63,64],
                witness_bank=127,witness_logical_words=[logical_old,logical_new],
                aw10_cannot_reach_boundary=True,aw14_required_for_this_vector=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--failed-report',type=Path,required=True)
    parser.add_argument('--compile-lock',type=Path,required=True)
    args=parser.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    resource.setrlimit(resource.RLIMIT_AS,(6<<30,6<<30))
    root=Path(__file__).resolve().parents[1];old_root=args.failed_report.resolve()
    ancestor=json.loads(old_root.read_text());old_path=old_root.parent/'lanes64/report.json'
    old=json.loads(old_path.read_text())
    if ancestor['status']!='failed' or old['status']!='failed':raise RuntimeError('expected preserved failed gate')
    bad=[s['name'] for s in old['steps'] if not s['passed']]
    if bad!=['reject-mutation-point-data']:raise RuntimeError('unexpected ancestor failure')
    for name,sha in old['source_sha256'].items():
        if digest(root/name)!=sha:raise RuntimeError('ancestor source mismatch '+name)
    for name,sha in ((f'rtl/kernel/genefer_ntt_banked27_rootpipe_engine.sv',ENGINE_SHA),
                     ('rtl/tb/ntt_banked27_rootpipe_engine.cpp',BENCH_SHA),
                     ('reference/ntt27_rootpipe_regression.py',HARNESS_SHA)):
        if digest(root/name)!=sha:raise RuntimeError('frozen source mismatch '+name)
    old_builds={b['name']:b for b in old['builds']}
    retained={}
    for name in OLD_FAULTS:
        step=next(s for s in old['steps'] if s['name']=='reject-mutation-'+name)
        build=old_builds['build-mutation-'+name]
        if not step['passed'] or digest(build['executable'])!=build['executable_sha256']:
            raise RuntimeError('old mutation evidence mismatch '+name)
        for attempt in step['attempts']:
            if digest(attempt['evidence_log'])!=attempt['evidence_sha256']:
                raise RuntimeError('old mutation log mismatch')
        retained[name]=dict(passed=True,origin='verified prior run',step=step,build=build)
    control=old_builds['build-ntt27-rootpipe-p1-aw10-l64']
    if digest(control['executable'])!=control['executable_sha256']:raise RuntimeError('old AW10 control changed')
    for name,sha in old['evidence_sha256'].items():
        if digest(old_path.parent/name)!=sha:raise RuntimeError('old vector/log changed '+name)
    args.output.mkdir(parents=True,exist_ok=False)
    lab=FullLab(args.output,'verilator');lab.lanes=64;lab.compile_lock=args.compile_lock.resolve()
    lab.report.update(profile='rootpipe-recovery-aw14-j4-runtime1-v1',compile_workers=4,model_threads=1,
        memory_limit_bytes=6<<30,ancestor=dict(status='failed',root_report=str(old_root),root_sha256=digest(old_root),
            lane_report=str(old_path),lane_sha256=digest(old_path),failure='point-data survived AW10'),
        inherited_mutations=retained,boundary_proof=boundary_proof(),logical_mutations=dict(retained))
    try:
        lab.report['structure_proof']=validate_files(root);lab.report['bench_proof']=bench_proof(root)
        _,toolchain,environment=cache_context(args.output/'unused-cache-record-only')
        tools_path=args.output/'toolchain.json'
        tools_path.write_text(json.dumps(dict(toolchain=toolchain,environment=environment),indent=2)+'\n')
        lab.report['toolchain_manifest']={'path':str(tools_path),'sha256':digest(tools_path)}
        p=EXPERIMENT_PRIMES[0].p;r=(1<<32)%p;n=1<<14
        lines=['14']
        def emit(cmd,words):lines.extend((cmd,' '.join(map(str,words))))
        for phase in (0,3):
            data=[((17 if phase==0 else 23)*i+3+phase)%p for i in range(n)]
            roots=[((29 if phase==0 else 31)*i+7+phase)%p for i in range(n)]
            lines.append(f'PHASE {phase}');emit('LOAD',[x*r%p for x in data])
            emit('ROOTS',[x*r%p for x in roots] if phase==0 else roots)
            lines.append('RUN 2 0 0')
            emit('CHECK',[a*b*(r if phase==0 else 1)%p for a,b in zip(data,roots)])
        vectors=lab.output/'directed-aw14-point-boundary.txt';vectors.write_text('\n'.join(lines)+'\n')
        baseline=lab.build_ntt(0,14,64)
        output=lab.run('directed-aw14-baseline',['env','NTT_SKIP_HOST_FUZZ=1',baseline,str(vectors),str(lab.output/'baseline-dump.txt')])
        if re.findall(r'cycles=(\d+)',output)!=['265','265']:raise RuntimeError('directed boundary cycle mismatch')
        lab.report['boundary_baseline']=dict(passed=True,aw=14,lanes=64,phases=[0,3],cycles=[265,265],
            vector_sha256=digest(vectors),checked_words=2*n)
        faults=[('point-data',14,'root_point_q[b]<=root_point_mid_q[b];','root_point_q[b]<=root_q[b];'),
            ('point-valid',10,'mul_route_valid<=mul_mid_valid;','mul_route_valid<=mul_in_valid;'),
            ('clip-delay',10,'stage_bit_e<=stage_bit_mid;',"stage_bit_e<=5'd0;"),
            ('pairing-delay',10,'pairing_e<=pairing_mid;',"pairing_e<='0;")]
        engine=root/'rtl/kernel/genefer_ntt_banked27_rootpipe_engine.sv'
        deps=[root/'rtl/kernel'/name for name in ('genefer_montgomery_mul27_sparse_pipe.sv',
            'genefer_sdp_ram32.sv','genefer_ntt_banked27_engine.sv')]
        for name,aw,find,replace in faults:
            text=engine.read_text()
            if text.count(find)!=1:raise RuntimeError('mutation anchor mismatch '+name)
            directory=lab.output/('mutation-'+name);directory.mkdir()
            changed=directory/engine.name;changed.write_text(text.replace(find,replace))
            if name=='point-data' and digest(changed)!=next(s['source_sha256'] for s in old['steps'] if s['name']=='reject-mutation-point-data'):
                raise RuntimeError('escaped mutant was changed')
            exe=lab.build('build-mutation-'+name,'genefer_ntt_banked27_rootpipe_engine',[*deps,changed],
                root/'rtl/tb/ntt_banked27_rootpipe_engine.cpp',
                [f'-GAW={aw}','-GLANES=64','-CFLAGS',f'-O0 -DNTT_AW={aw} -DNTT_LANES=64 -DNTT_P=104857601u'])
            selected=[vectors] if aw==14 else [old_path.parent/'cached-squares-p1-aw10.txt',old_path.parent/'reset-ntt27-rootpipe-p1-l64.txt']
            attempts=[];passed=False
            for index,vector in enumerate(selected):
                proc=subprocess.run(['env','NTT_SKIP_HOST_FUZZ=1',exe,str(vector),str(directory/f'dump{index}.txt')],
                    cwd=root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
                path=lab.output/f'reject-{name}-{index}.log';path.write_text(proc.stdout)
                rejected=proc.returncode!=0 and any(s in proc.stdout for s in ('mismatch','collision','noncanonical','timeout','completion','reset'))
                attempts.append(dict(returncode=proc.returncode,rejected=rejected,log=str(path),sha256=digest(path),vector_sha256=digest(vector)))
                if rejected:passed=True;break
            result=dict(name='reject-'+name,passed=passed,source_sha256=digest(changed),attempts=attempts)
            lab.report['steps'].append(result);lab.report['logical_mutations'][name]=result
            if not passed:raise RuntimeError('recovery mutant survived '+name)
            print('reject-'+name,'PASS',flush=True)
        if len(lab.report['logical_mutations'])!=12 or not all(s['passed'] for s in lab.report['logical_mutations'].values()):
            raise RuntimeError('incomplete twelve-fault coverage')
        for name,sha in lab.report['source_sha256'].items():
            if digest(root/name)!=sha:raise RuntimeError('source changed '+name)
        if not all(s['passed'] for s in lab.report['steps']):raise RuntimeError('failed new gate step')
        lab.report['status']='passed'
    except BaseException as error:
        lab.report.update(status='failed',error=repr(error));raise
    finally:
        lab.report['evidence_sha256']={str(p.relative_to(lab.output)):digest(p) for p in lab.output.iterdir() if p.suffix in ('.log','.txt')}
        (lab.output/'report.json').write_text(json.dumps(lab.report,indent=2)+'\n')


if __name__=='__main__':main()
