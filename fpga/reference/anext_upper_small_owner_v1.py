"""Read-only upper whole small + upper-flight native delta replay."""
import json,gzip
from pathlib import Path
from fpga.reference.anext_point_aw16_owner_replay_v1 import archived,read,sha,need
from fpga.reference import anext_upper_source_v1 as source
from fpga.reference.anext_upper_output_v1 import validate as normal
from fpga.reference.anext_upper_cancel_v1 import validate as cancel,CASES
ROOT=source.ROOT
REPORTS={
 'anext-upper-whole-aw5-q1-v1':'748032163fb640cd64eeff4be4425b63576ab4fdb5d32b2dbcf1ab456207eae6',
 'anext-upper-whole-aw8-q1-v1':'cdd9f68021a8215f963ba8ca75930a814a4704892b08b5d96bc2aea1bc021ce9',
 'anext-upper-cancel-aw5-q1-v1':'224ec1b6c7217ab0f0dd7a3c31d2f42621aafa27e44e55185efe0811cff0aebe'}
def replay():
    source.verify();results=[]
    for job,pin in REPORTS.items():
        e=ROOT/f'queue/evidence/{job}';p=e/'attempt-0/collected/output/native';d=json.loads((ROOT/f'queue/done/{job}.json').read_text())
        r=json.loads(read(p/'report.json',pin));m=json.loads(read(p/'approved-manifest.json',d['dependency_gate']['manifest_sha256']))
        need(d['dependency_gate']['status']=='PASS_expected_contracts','machine gate')
        for name,h in r['artifacts'].items():read(p/name,h)
        ns=archived(p/'sources.tar.gz',r['sources']);ng=archived(p/'generated-sources.tar.gz',r['generated_source_sha256'])
        need(r['sources']==m['sources'] and r['sources'][source.CELL]==source.CELL_SHA,'actual compiled cell identity')
        elf=gzip.decompress((p/'model.gz').read_bytes());need(elf[:4]==b'\x7fELF' and sha(elf)==r['executable_sha256'],'ELF pin')
        need(r['probe']==dict(context_threads=1,model_threads=1,expected_threads=1),'serial probe')
        for k in ('lint_admission','build_admission'):need(not r[k]['fatal_class_counts'] and not r[k]['unknown_class_counts'] and not r[k]['error_streams'],'native classes')
        observed=[];same_point=False
        if 'whole' in job:
            aw=5 if 'aw5' in job else 8;s=r['steps'][-1]
            stdout=read(p/s['log'],s['sha256']).decode();stderr=read(p/s['stderr_log'],s['stderr_sha256']).decode()
            vectors=(ROOT/f'artifacts/anext-upper-whole-aw{aw}-role-v1/source/fpga/vectors/anext-aw{aw}.txt').read_text()
            observed.append(normal(stdout,stderr,s['returncode'],dict(mode='normal',aw=aw),{'vectors':vectors}))
            q=ROOT/f'queue/evidence/anext-point-whole-aw{aw}-q1-v1/attempt-0/collected/output/native';pr=json.loads((q/'report.json').read_text());ps=pr['steps'][-1]
            need(stdout==read(q/ps['log'],ps['sha256']).decode(),'literal unchanged point phase/footer output');same_point=True
        else:
            for case,s in zip(CASES,r['steps'][-6:]):
                need(s['name']=='upper-'+case,'ordered upper seam cases')
                observed.append(cancel(read(p/s['log'],s['sha256']).decode(),read(p/s['stderr_log'],s['stderr_sha256']).decode(),s['returncode'],{'case':case},{}))
        props=d['result']['properties'];need(props['MainPID']=='0' and props['ExecMainStatus']=='0' and props['Result']=='success' and not props['ControlGroup'],'native terminal')
        results.append(dict(job=job,report_sha256=pin,gate=d['dependency_gate'],invocation=props['InvocationID'],native_profile=d['result']['queue_report']['profile'],
            artifacts=len(r['artifacts']),sources=ns,generated=ng,executable_sha256=r['executable_sha256'],observed=observed,
            normal_stdout_byte_equal_point=same_point,scope='Exact native upper-cell whole/cancel delta; not fullN/clock/continuous qualification.'))
    return dict(status='PASS_owner_upper_small_and_cancel_native_delta',results=results,promotion_allowed=False,local_RTL_executed=False,full_N_numeric_locally_performed=False)
if __name__=='__main__':print(json.dumps(replay(),indent=2))
