"""Read-only point whole AW16 native archive/cycle/source consumption."""
import gzip,json,hashlib,tarfile
from pathlib import Path,PurePosixPath
from fpga.reference import anext_point_representative_v1 as source
from fpga.reference.anext_point_representative_output_v1 import validate

ROOT=source.ROOT
JOB='anext-point-representative-aw16-q1-v1'
REPORT='2ae7a6367b3b436576204c0224117d914294434da02b90c0bc255923db68110d'
GATE='c9c7082ca546c3834f000c9e99768918585f4e0cda00cab2b4ec6313fb27be44'
MANIFEST='bb1103d4cc5815fab34eb29dd02aecc027ce461843ca12b09d4034e9bb56649f'
def sha(data):return hashlib.sha256(data).hexdigest()
def need(value,message):
    if not value:raise ValueError(message)
def read(path,pin):
    raw=path.read_bytes();need(sha(raw)==pin,'pinned bytes '+str(path));return raw
def archived(path,pins):
    seen=set()
    with tarfile.open(path) as t:
        for m in t:
            need(m.isfile() and m.name not in seen and not PurePosixPath(m.name).is_absolute() and '..' not in PurePosixPath(m.name).parts,'safe unique archive')
            need(m.name in pins and sha(t.extractfile(m).read())==pins[m.name],'member hash');seen.add(m.name)
    need(seen==set(pins),'complete archive');return len(seen)

def replay():
    e=ROOT/f'queue/evidence/{JOB}';p=e/'attempt-0/collected/output/native'
    r=json.loads(read(p/'report.json',REPORT));m=json.loads(read(p/'approved-manifest.json',MANIFEST));g=json.loads(read(e/'gate-receipt.json',GATE))
    need(g['status']=='PASS_expected_contracts' and g['report_sha256']==REPORT and g['manifest_sha256']==MANIFEST,'machine gate binding')
    for name,pin in r['artifacts'].items():read(p/name,pin)
    need(r['sources']==m['sources'],'complete source map')
    ns=archived(p/'sources.tar.gz',r['sources']);ng=archived(p/'generated-sources.tar.gz',r['generated_source_sha256'])
    elf=gzip.decompress((p/'model.gz').read_bytes());need(elf[:4]==b'\x7fELF' and sha(elf)==r['executable_sha256'],'native ELF')
    need(r['probe']==dict(context_threads=1,model_threads=1,expected_threads=1) and r['limits']['affinity']==[2,3] and r['limits']['memory_max_bytes']==24<<30 and r['limits']['swap_max_bytes']==0,'native caps/probe')
    for k in ('lint_admission','build_admission'):
        need(not r[k]['fatal_class_counts'] and not r[k]['unknown_class_counts'] and not r[k]['error_streams'],'actual class-qualified source')
    role=json.loads((ROOT/'artifacts/anext-point-representative-aw16-role-v1/manifest.json').read_text())
    need(m['build']==role['build'] and m['probe']==role['probe'] and m['steps']==role['steps'],'actual expected build/probe/step')
    need(all(m['sources'][n]==pin for n,pin in role['sources'].items()),'frozen role closure')
    source.parent.verify()
    for name,text in source.expected().items():need((ROOT/name).read_text()==text and sha(text.encode())==m['sources'][name],'exact closed-form recipe/parser successor')
    for fit in ('anext-point-9668ps-f16-plain-v1','anext-point-9668ps-aws6-plain-v1'):
        physical=json.loads((ROOT/f'artifacts/{fit}/project/manifest.json').read_text())
        need(physical['source_sha256']=={Path(n).name:m['sources'][n] for n in m['build']['sv_sources']},'fit30RTL identical to actual native')
    run=r['steps'][-1];stdout=read(p/run['log'],run['sha256']).decode();stderr=read(p/run['stderr_log'],run['stderr_sha256']).decode()
    result=validate(stdout,stderr,run['returncode'],dict(mode='representative',aw=16),{})
    # Actual compiled C++ compares all524288 read words to the unchanged closed
    # form recipe; no new native run or full-N arithmetic is performed here.
    negatives=[stdout.replace('ntt=17710','ntt=17709',1),stdout.replace('total=25990','total=25989',1),stdout.replace('post=4158','post=4159',1),stdout.replace('readbacks=524288','readbacks=524287'),stdout+'extra\n',stdout.split('\n',1)[1]]
    for bad in negatives:
        need(bad!=stdout,'actual negative mutation')
        try:validate(bad,'',0,dict(mode='representative',aw=16),{})
        except (ValueError,AssertionError):pass
        else:raise ValueError('bad output accepted')
    done=json.loads((ROOT/f'queue/done/{JOB}.json').read_text());pr=done['result']['properties']
    need(pr['InvocationID']=='4d189bfde7184f939856212e2e4e7ce9' and pr['ExecMainStatus']=='0' and pr['MainPID']=='0' and not pr['ControlGroup'],'actual terminal')
    return dict(status='PASS_owner_point_AW16_native_source_and_cycle_replay',report_sha256=REPORT,gate_sha256=GATE,manifest_sha256=MANIFEST,
        invocation=pr['InvocationID'],artifacts=len(r['artifacts']),sources=ns,generated=ng,executable_sha256=r['executable_sha256'],
        native_metrics=result,native_model_seconds=run['seconds'],native_build_seconds=r['steps'][3]['seconds'],native_peak_bytes=int(pr['MemoryPeak']),
        malformed_output_negatives=len(negatives),fit_alternatives_same30SV=True,local_full_N_numeric=False,local_native_execution=False,
        promotion_allowed=False,independent_review_required=True,
        scope='16 representative squares/eight full images, exact+1 point/NTT/backend/host schedule. No PRP/continuous1000 inheritance from original core; separate point-flight cancel cases exist.')

if __name__=='__main__':print(json.dumps(replay(),indent=2))
