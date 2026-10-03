"""Additive R11 native1000 join; frozen native2 result/producer stay intact."""
import argparse
import json
from pathlib import Path
from . import stream27_c2_r11_transport_healthy_join as base

ROOT=base.ROOT
SELF='reference/stream27_c2_r11_transport_healthy_join_v3.py'
BASE_PIN='01802aacb27700e0efa03622adb6aa35880ea56125b24636b86bb1b9ea366c66'
NATIVE2='results/throughput-20260929/trackS-c2-transport11-ledger-v1/publication-ledger-native2-100-joined-v1.json'
NATIVE2_PIN='2e5c2c6c34a1b27da399034948591a02bd2ee429adef44d18d3985a7bec71b31'
ID='s4-p16-c2-combo-r11-continuous1000-q1-v1'
STEP='normal-full-c2-combo-r11-continuous1000-percontext'


def close():
    base.need(base.sha((ROOT/base.SELF).read_bytes())==BASE_PIN,'IMMUTABLE_NATIVE2_PRODUCER')
    prior=(ROOT/NATIVE2).read_bytes();base.need(base.sha(prior)==NATIVE2_PIN,'IMMUTABLE_NATIVE2_RESULT')
    out=json.loads(prior);b=base.source();evidence=ROOT/'queue/evidence'/ID
    native=evidence/'attempt-0/collected/output/native';gp=evidence/'gate-receipt.json'
    rp=native/'report.json';mp=native/'approved-manifest.json';lp=native/(STEP+'.log')
    gate,report,manifest=[json.loads(path.read_bytes()) for path in (gp,rp,mp)]
    base.need(gate['status']=='PASS_expected_contracts' and gate['manifest_sha256']==base.sha(mp.read_bytes())==
        report['manifest_sha256'] and gate['report_sha256']==base.sha(rp.read_bytes()),'OWN_NATIVE1000_BINDING')
    base.need(manifest['build']['parameters']==out['production']['compiled_parameters'] and
        len(manifest['build']['sv_sources'])==59,'OWN_NATIVE1000_COMPILED_PARAMETERS')
    for name,pin in b['generated_sha256'].items():
        base.need(manifest['sources']['rtl/'+name]==pin==report['sources']['rtl/'+name],
                  'OWN_NATIVE1000_ALL58_SOURCE')
    build=[row for row in report['steps'] if row['name']=='build']
    base.need(len(build)==1 and build[0]['returncode']==0 and
        all('-G'+key+'='+str(value) in build[0]['command'] for key,value in manifest['build']['parameters'].items()),
        'OWN_NATIVE1000_ACTUAL_PARAMETER_ARGV')
    base.need(report['host']=='gfn16-pilot-c4d' and report['model_threads']==1 and
        report['artifacts'][STEP+'.log']==base.sha(lp.read_bytes()),'OWN_GCP_SOURCE_BOUND_LOG')
    text=lp.read_text();base.need(text.startswith('R84_C2_THREAD100_PASS ') and len(text.splitlines())==1,'OWN1000_FOOTER')
    footer=json.loads(text.removeprefix('R84_C2_THREAD100_PASS '));calendar=base.validate_footer(footer,b['geometry'],1000)
    out.update(status='OWN_SOURCE_NATIVE2_100_1000_JOIN_PASS_CONTROL_PRP_CLOCK_PENDING',
        prior_native2=dict(path=NATIVE2,sha256=NATIVE2_PIN),
        producer=dict(path=SELF,sha256=base.sha((ROOT/SELF).read_bytes())),native1000_join_pending=False,
        native1000=dict(id=ID,gate_sha256=base.sha(gp.read_bytes()),report_sha256=base.sha(rp.read_bytes()),
            manifest_sha256=base.sha(mp.read_bytes()),log_sha256=base.sha(lp.read_bytes()),
            measurements=footer,calendar=calendar))
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    target=args.output.resolve();base.need(target.is_relative_to(ROOT) and not target.exists(),'FRESH_OUTPUT')
    value=close();target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(status=value['status'],path=str(target),sha256=base.sha(target.read_bytes()),
        pair_cycles=value['sample']['pair_completion_cycles'],selected_period_ns=None)))

