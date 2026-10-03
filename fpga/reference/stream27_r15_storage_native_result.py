"""Routine source/gate association only; no numerical replay or self review."""
import json
from pathlib import Path
from . import stream27_r15_storage_ram_bind as b

ROOT=b.ROOT;BASE=ROOT/'results/throughput-20261003/trackS-r15-storage-ram-v1'

def gate(identifier):
    p=ROOT/'queue/evidence'/identifier/'gate-receipt.json';raw=p.read_bytes();g=json.loads(raw)
    b.need(g['id']==identifier and g['status']=='PASS_expected_contracts','ACTUAL_TYPED_GATE')
    report=p.parent/'attempt-0/collected/output/native/report.json'
    b.need(b.sha(report.read_bytes())==g['report_sha256'],'ACTUAL_REPORT_HASH')
    return b.sha(raw),g,json.loads(report.read_bytes())

def report():
    pins={}
    for key,identifier in [('pair','s4-p16-r15-crt-numeric-pair-normal-q1-v1'),
      ('reset','s4-p16-r15-crt-numeric-pair-reset-q1-v1'),('aw8','s4-p16-r15-storage-crt-aw8-normal-q1-v2'),
      ('full','s4-p16-r15-storage-crt-full-normal-q1-v2')]:
        pin,g,r=gate(identifier);pins[key]=pin
        if key in ('aw8','full'):
            bundle=json.loads((BASE/('aw8-normal-v2' if key=='aw8' else 'full-normal-v2')/'production-bundle.json').read_bytes())
            b.need(len(bundle['files'])==59,'PRODUCTION59')
            for name,text in bundle['files'].items():
                b.need(r['sources'].get('rtl/'+name)==b.sha(text),'EXACT_COMPILED_PRODUCTION_MEMBER:'+name)
        if key=='full':metrics=g['steps'][0]['validation']['measurements']
    b.need(metrics['interval']==8461 and metrics['squares']==8 and metrics['reads']==393216 and
      metrics['context_alone_bit_identical'] and metrics['independent_reference'],'OWN_FULL_MEASUREMENTS')
    return dict(status='ACTUAL_OWN_PAIR_RESET_AW8_FULL_PASS',gates=pins,
      frozen_binder_sha256=b.sha((ROOT/'reference/stream27_r15_storage_ram_bind.py').read_bytes()),
      compiled_production_members=59,native_latency_delta=0,coefficient_E16=True,II1=True,
      full=dict(squares=metrics['squares'],signed96_reads=metrics['reads'],interval=metrics['interval'],
        alone_joint_bit_identical=True,independent_reference=True,peer_live_reads=metrics['peer_live_reads']),
      component_only_delta=dict(LAB=-2,FF=-579,MLAB=7,needed_ALM=135),
      whole_resource_or_clock_savings=None,arbitrary_RAM_corruption_immunity=False,independent_review=False,promotion_allowed=False)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();b.need(out.is_relative_to(BASE) and not out.exists(),'FRESH_RESULT')
    value=report()
    with out.open('x') as f:json.dump(value,f,separators=(',',':'));f.write('\n')
    print(json.dumps(dict(path=str(out),sha256=b.sha(out.read_bytes()),status=value['status'])))
