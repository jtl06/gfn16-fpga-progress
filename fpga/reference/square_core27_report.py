"""Normalize a passed core27 matrix report without changing the original evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import socket

BASIS=[
    dict(p=104857601,q=4190109697,r2=45971250,generator=3),
    dict(p=69206017,q=4225761281,r2=50081300,generator=5),
    dict(p=67239937,q=4227727361,r2=63576045,generator=10),
]


def normalize(report,profile):
    if report.get('status')!='passed':raise ValueError('only a passed gate can be normalized')
    if report.get('radix_bits')!=32:raise ValueError('wrong Montgomery radix')
    if report.get('crt_modulus')!=487945222748036195811329:raise ValueError('wrong atomic27 CRT profile')
    if profile not in report.get('profiles',[]):raise ValueError('profile absent from gate')
    lanes,io_lanes=profile
    if lanes not in (16,64) or io_lanes!=16:raise ValueError('unsupported core27 profile')
    metrics=[]
    for item in report.get('metrics',[]):
        if item['ntt_lanes']!=lanes:continue
        if item['io_lanes']!=16:raise ValueError('inconsistent IO width')
        n=1<<item['aw']
        if item['cycles']!=sum(item[k] for k in ('conversion','roots','ntt','crt','carry')):
            raise ValueError('phase accounting mismatch')
        if item['conversion']!=(n+15)//16+9:raise ValueError('conversion contract mismatch')
        metrics.append(dict(item,n=n,root_cache_warm=item['cache_before']==15,readback=bool(item['readback'])))
    if not metrics:raise ValueError('no metrics for profile')
    return dict(status='passed',host=report['host'],ancestor_sha256=report['ancestor_sha256'],
        configuration=dict(difdit=True,ntt_lanes=lanes,prefix_carry=True,root_cache=True,
            banked_ntt=True,carry_lanes=16,vector_io=True,fast_arith=True,io_lanes=16,
            host_adapter=lanes==64,fuse_input_mont=False,stream_carry=False,
            generated_roots=False,field_profile='sparse27-cached-radix32-v1',montgomery_radix_bits=32),
        atomic_profile=dict(basis=BASIS,radix_bits=32,crt_modulus=report['crt_modulus'],
            max_doubled_coefficient=report['max_doubled_coefficient'],
            exposed_parameters=['AW','NTT_LANES']),
        sources=report['sources'],metrics=metrics,steps=report['steps'],
        note='Per-profile metrics view of a passed matrix gate; no rerun or cached correctness claim. All original gate steps are retained as shared evidence.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if socket.gethostname()!='aethia':raise RuntimeError('aethia only')
    raw=args.input.read_bytes();report=json.loads(raw)
    # Validate all views before creating the fresh destination.
    views=[(profile,normalize(report,profile)) for profile in report.get('profiles',[])]
    if not views:raise ValueError('no profiles')
    args.output.mkdir(parents=True,exist_ok=False)
    provenance=dict(original_report=str(args.input.resolve()),original_sha256=hashlib.sha256(raw).hexdigest(),
        normalizer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    for (lanes,io_lanes),view in views:
        view['provenance']=provenance
        path=args.output/f'core27-{lanes}-{io_lanes}-report.json'
        path.write_text(json.dumps(view,indent=2)+'\n')
        print(path,len(view['metrics']),'metrics',flush=True)


if __name__=='__main__':main()
