"""Promoted T5b exact-state soak adapter for the shared finite native worker.

No candidate cloud runner is added. Existing GCP/Azure reference runtimes stay
individually admitted; T5b lineage, case IDs and source snapshots are separate
from preserved CRTMont results. Integer arithmetic is the frozen common oracle.
"""
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/core27_t5b_soak_native_v1.py'
REFERENCE = 'reference/core27_t5b_soak_v1.py'
REFERENCE_SHA = '636460b5fd8e96696112d53ca792a340f5d2ad1ad843f6f23135877bae6ce962'
DEPENDENCIES = {
    REFERENCE:REFERENCE_SHA,
    'reference/core27_crtmont_soak_v1.py':'8075e2033a01b09b9bbc344b72f23df4ebbc90b8489caadfbd0546e6f3bcfe3a',
    'reference/core27_crtmont_soak_native_v2.py':'17c4d4a8830cf03f371a476836b942066552e9bcb44bf9858236194919717844',
    'reference/core27_crtmont_soak_native_v3.py':'c79bb901d37f113f5b12cdd7ee1b52ee57f175bd131fec8ee02daf25b8451473',
    'tools/native_gmpy2_runtime_v1.py':'56cf38c3dd18279e68309e98bf224bde97a95e776660c9ff5b91c3178a258d1c',
}


def need(ok,message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def load(name):
    need(sha(ROOT/name)==DEPENDENCIES[name], 'SOAK_T5B_CLOSED_ADAPTER_DEPENDENCY')
    spec=importlib.util.spec_from_file_location('_t5b_adapter_'+Path(name).stem,ROOT/name)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def reference():
    return load(REFERENCE).reference()


def admit_runtime(text):
    value=json.loads(text)
    name='reference/core27_crtmont_soak_native_v2.py' if value['host']=='gfn16-pilot-c4d' else 'reference/core27_crtmont_soak_native_v3.py'
    return load(name).admit_runtime(text)


def validate(stdout,stderr,returncode,config,assets):
    need(set(assets)=={'oracle','runtime'},'SOAK_T5B_VALIDATOR_ASSETS')
    admitted=admit_runtime(assets['runtime'])
    result=reference().validate(stdout,stderr,returncode,config,{'oracle':assets['oracle']})
    result.update(auxiliary_reference_runtime=admitted,lineage='promoted-t5b')
    return result


def dump(path,value):
    with path.open('x') as stream:
        json.dump(value,stream,indent=2);stream.write('\n')


def capture(output,runtime_file):
    ref=reference();lineage=load(REFERENCE)
    output=Path(output).resolve();need(not output.exists(),'SOAK_T5B_FRESH_CAPTURE')
    need(not (ROOT/'docs/briefs/PAUSE').exists(),'brief PAUSE')
    order,pins=ref.parent_sources()
    for name in (*DEPENDENCIES,SELF,ref.BENCH,ref.HEADER,ref.TEST,
                 lineage.READINESS,lineage.ADVISOR,lineage.AUDIT):
        pins[name]=sha(ROOT/name)
    for name in ('manifest.json','probe.qsf',*('rtl/'+name for name in order)):
        pins[ref.PARENT+'/'+name]=sha(ROOT/ref.PARENT/name)
    source=output/'source/fpga';source.mkdir(parents=True)
    for name,pin in pins.items():
        need(not (ROOT/name).is_symlink(),'SOAK_T5B_CAPTURE_SYMLINK')
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,target);need(sha(target)==pin,'SOAK_T5B_CAPTURE_DRIFT')
    target=source/'soak/runtime.json';target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(runtime_file,target);pins['soak/runtime.json']=sha(target)
    with (output/'reference-source.tar.gz').open('xb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as zipped:
        with tarfile.open(fileobj=zipped,mode='w') as archive:
            for name in sorted(pins):
                content=(source/name).read_bytes();need(hashlib.sha256(content).hexdigest()==pins[name],'SOAK_T5B_ARCHIVE_DRIFT')
                entry=tarfile.TarInfo('source/fpga/'+name);entry.mode=0o644;entry.mtime=0;entry.size=len(content)
                archive.addfile(entry,io.BytesIO(content))
    result=dict(status='captured_promoted_T5b_reference_sources_not_executed',sources=pins,
        archive_sha256=sha(output/'reference-source.tar.gz'),archive_bytes=(output/'reference-source.tar.gz').stat().st_size,
        runtime_manifest_sha256=sha(runtime_file),promotion_advisor_sha256=lineage.ADVISOR_SHA)
    dump(output/'reference-source.json',result);return result


def generate(output,runtime_file,plan):
    admitted=admit_runtime(Path(runtime_file).read_text())
    result=reference().generate(output,plan,'gmpy2')
    admitted.update(adapter_sha256=sha(ROOT/SELF),reference_generation_sha256=sha(Path(output)/'generation.json'))
    dump(Path(output)/'auxiliary-runtime-admission.json',admitted);return result


def stage(references,segment,output,runtime_file,host,remote_root,controls=True):
    ref=reference();lineage=load(REFERENCE);output=Path(output).resolve()
    ref.stage_segment(references,segment,output,host,remote_root,1)
    manifest=json.loads((output/'manifest.json').read_text());source=output/'source/fpga'
    for name in (*DEPENDENCIES,SELF,lineage.READINESS,lineage.ADVISOR,lineage.AUDIT):
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():shutil.copyfile(ROOT/name,target)
        need(sha(target)==sha(ROOT/name),'SOAK_T5B_STAGE_CLOSED_DEPENDENCY');manifest['sources'][name]=sha(target)
    target=source/'soak/runtime.json';target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(runtime_file,target);manifest['sources']['soak/runtime.json']=sha(target)
    runtime=json.loads(target.read_text())
    need(runtime['host']==host,'SOAK_T5B_STAGE_RUNTIME_HOST')
    admitted=json.loads((Path(references)/'auxiliary-runtime-admission.json').read_text())
    need(admitted['status']=='passed_exact_auxiliary_reference_runtime'
         and admitted['runtime_manifest_sha256']==sha(target),'SOAK_T5B_REFERENCE_RUNTIME_BINDING')
    manifest['build'].pop('runtime_threads');manifest['build']['cflags'].remove('-DGFN16_RUNTIME_THREADS=1');manifest.pop('model_threads')
    for step in manifest['steps']:
        step['validator']['source']=SELF;step['validator']['assets']['runtime']='soak/runtime.json'
    if not controls:
        manifest['steps']=[step for step in manifest['steps'] if step['validator']['config']['negative']=='none']
    manifest['auxiliary_reference_runtime_manifest_sha256']=sha(target)
    manifest['promotion_advisor_sha256']=lineage.ADVISOR_SHA
    dump(output/'serial-manifest.json',manifest)
    return dict(status='staged_promoted_T5b_not_dispatched',manifest_sha256=sha(output/'serial-manifest.json'),
        source_root=str(source),sources=manifest['sources'],model_threads=1,promotion_allowed=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    cap=commands.add_parser('capture');cap.add_argument('--output',type=Path,required=True);cap.add_argument('--runtime-file',type=Path,required=True)
    gen=commands.add_parser('generate');gen.add_argument('--output',type=Path,required=True);gen.add_argument('--runtime-file',type=Path,required=True)
    for name,default in (('aw',16),('base',604832956),('squares',1000),('chunk-squares',100),('checkpoint-every',100),('seed',20261001)):
        gen.add_argument('--'+name,type=int,default=default)
    st=commands.add_parser('stage')
    for name in ('references','output','runtime-file'):st.add_argument('--'+name,type=Path,required=True)
    for name in ('segment','host','remote-root'):st.add_argument('--'+name,required=True)
    st.add_argument('--normal-only',action='store_true')
    args=parser.parse_args()
    if args.command=='capture':result=capture(args.output,args.runtime_file)
    elif args.command=='generate':
        plan=reference().make_plan(args.aw,args.squares,args.chunk_squares,args.checkpoint_every,args.seed,args.base)
        result=generate(args.output,args.runtime_file,plan)
    else:result=stage(args.references,args.segment,args.output,args.runtime_file,args.host,args.remote_root,not args.normal_only)
    print(json.dumps(result,indent=2))
