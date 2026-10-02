"""Read-only native hostcut whole/physical-write-cancel evidence replay."""
import json,gzip
from pathlib import Path
from fpga.reference.anext_point_aw16_owner_replay_v1 import archived,read,sha,need
from fpga.reference import anext_hostcut_source_v1 as source
from fpga.reference.anext_hostcut_output_v1 import validate as small
from fpga.reference.anext_hostcut_representative_output_v1 import validate as full
from fpga.reference.anext_hostcut_fault_v1 import validate as cancel
ROOT=source.ROOT
def replay(kind):
    need(kind in ('5','8','16','cancel'),'finite hostcut role');aw=5 if kind=='cancel' else int(kind)
    job='anext-hostcut-fault-aw5-q1-v1' if kind=='cancel' else f'anext-hostcut-whole-aw{aw}-q1-v1'
    e=ROOT/f'queue/evidence/{job}';p=e/'attempt-0/collected/output/native';done=json.loads((ROOT/f'queue/done/{job}.json').read_text());dg=done['dependency_gate']
    g=json.loads(read(e/'gate-receipt.json',dg['sha256']));need(g['status']=='PASS_expected_contracts','actual gate')
    r=json.loads(read(p/'report.json',g['report_sha256']));m=json.loads(read(p/'approved-manifest.json',g['manifest_sha256']))
    for n,h in r['artifacts'].items():read(p/n,h)
    ns=archived(p/'sources.tar.gz',r['sources']);ng=archived(p/'generated-sources.tar.gz',r['generated_source_sha256'])
    need(r['sources']==m['sources'],'source map');elf=gzip.decompress((p/'model.gz').read_bytes());need(elf[:4]==b'\x7fELF' and sha(elf)==r['executable_sha256'],'ELF')
    source.verify();need(r['probe']==dict(context_threads=1,model_threads=1,expected_threads=1),'serial probe')
    for k in ('lint_admission','build_admission'):need(not r[k]['fatal_class_counts'] and not r[k]['unknown_class_counts'] and not r[k]['error_streams'],'class-qualified source')
    role=ROOT/('artifacts/anext-hostcut-fault-aw5-role-v1' if kind=='cancel' else f'artifacts/anext-hostcut-aw{aw}-role-v1');rm=json.loads((role/'manifest.json').read_text())
    need(m['build']==rm['build'] and m['steps']==rm['steps'] and all(m['sources'].get(n)==h for n,h in rm['sources'].items()),'frozen role exact source/build/contracts')
    observed=[];badcount=0
    for step in m['steps']:
        s=next(x for x in r['steps'] if x['name']==step['name']);out=read(p/s['log'],s['sha256']).decode();err=read(p/s['stderr_log'],s['stderr_sha256']).decode();v=step['validator']
        assets={k:read(role/'source/fpga'/n,m['sources'][n]).decode() for k,n in v['assets'].items()};fn=cancel if kind=='cancel' else full if aw==16 else small
        value=fn(out,err,s['returncode'],v['config'],assets);need(value==r['validations'][step['name']],'actual typed output replay');observed.append(value)
        for bad in (out+'extra\n',out.rstrip('\n'),out.partition('\n')[2]):
            try:fn(bad,err,s['returncode'],v['config'],assets)
            except (ValueError,AssertionError):badcount+=1
            else:raise ValueError('malformed hostcut output accepted')
    if kind!='cancel':
        oldjob='anext-upper-representative-aw16-q1-v1' if aw==16 else f'anext-upper-whole-aw{aw}-q1-v1';old=ROOT/f'queue/evidence/{oldjob}/attempt-0/collected/output/native';og=json.loads((ROOT/f'queue/evidence/{oldjob}/gate-receipt.json').read_text());pr=json.loads(read(old/'report.json',og['report_sha256']));previous=list(pr['validations'].values())[0];value=observed[0]
        for a,b in zip(value['metrics'],previous['metrics']):
            need(all(a[k]==b[k] for k in b),'exact hostcut delta in every measured phase row')
        need(value['footer']['ticks']==previous['footer']['ticks'],'exact host-tick delta')
    props=done['result']['properties'];need(props['MainPID']=='0' and props['ExecMainStatus']=='0' and props['Result']=='success' and not props['ControlGroup'],'terminal source-bound model')
    return dict(status='PASS_owner_hostcut_native_delta',job=job,report_sha256=g['report_sha256'],gate_sha256=dg['sha256'],manifest_sha256=g['manifest_sha256'],invocation=props['InvocationID'],artifacts=len(r['artifacts']),sources=ns,generated=ng,executable_sha256=r['executable_sha256'],observed=observed,malformed_output_negatives=badcount,promotion_allowed=False,local_HDL=False,local_full_N_numeric=False)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('kind',choices=('5','8','16','cancel'));print(json.dumps(replay(p.parse_args().kind),indent=2))
