"""Validate/normalize completed precision-stream evidence without editing raw reports."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path


def exact(a,b):return json.dumps(a,sort_keys=True)==json.dumps(b,sort_keys=True)
def require(condition,message):
    if not condition:raise ValueError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expected_config(lanes):
    return dict(difdit=True,ntt_lanes=lanes,prefix_carry=True,root_cache=True,
        banked_ntt=True,carry_lanes=16,vector_io=True,fast_arith=True,io_lanes=16,
        host_adapter=lanes==64,fuse_input_mont=False,stream_carry=True,precision_carry=True,
        generated_roots=False,field_profile='sparse27-cached-stream-precision-radix32-v1',
        montgomery_radix_bits=32)


def expected_atomic():
    basis=[dict(p=p,q=pow(p,-1,1<<32),generator=g,r2=pow(2,64,p))
           for p,g in ((104857601,3),(69206017,5),(67239937,10))]
    return dict(basis=basis,radix_bits=32,crt_modulus=math.prod(x['p'] for x in basis),
        max_doubled_coefficient=2*65536*999999999**2,exposed_parameters=['AW','NTT_LANES'])


def normalize(raw):
    require(raw.get('status')=='passed','requires a completed passing raw gate')
    config=raw.get('configuration',{});lanes=config.get('ntt_lanes')
    require(type(lanes) is int and lanes in (16,64),'unsupported NTT profile')
    require(exact(config,expected_config(lanes)),'architecture/profile mismatch')
    require(exact(raw.get('atomic_profile'),expected_atomic()),'basis/radix/bound mismatch')
    require(exact(raw.get('radix_bits'),32),'raw Montgomery radix mismatch')
    result=copy.deepcopy(raw);seen=set();counts={};readbacks={}
    require(bool(result.get('metrics')),'missing measured metrics')
    for row in result['metrics']:
        for name in ('aw','n','ntt_lanes','io_lanes','base','cycles','conversion','roots',
                     'ntt','crt','carry','passes','cache_before','root_loads','root_hits','readback'):
            require(type(row.get(name)) is int,'noninteger measured '+name)
        aw=row['aw'];n=row['n'];identity=(aw,row.get('case'))
        require(1<=aw<=16 and n==1<<aw,'measured size mismatch')
        require(row['ntt_lanes']==lanes and row['io_lanes']==16,'measured lane mismatch')
        require(2*n+4<row['base']<=1000000000,'measured base outside prefix domain')
        require(isinstance(identity[1],str) and identity[1] and identity not in seen,
                'missing/duplicate case identity')
        seen.add(identity)
        require(row['cycles']>0 and all(row[k]>=0 for k in ('conversion','roots','ntt','crt','carry')),
                'invalid measured counter')
        require(row['cycles']==sum(row[k] for k in ('conversion','roots','ntt','crt','carry')),
                'phase accounting mismatch')
        require(row['readback'] in (0,1),'readback outside0/1')
        if row['cache_before']==0:
            require((row['root_loads'],row['root_hits'],row['roots'])==(4,0,4*(n+2)),
                    'incoherent cold-cache evidence')
            warm=False
        elif row['cache_before']==15:
            require((row['root_loads'],row['root_hits'],row['roots'])==(0,4,0),
                    'incoherent warm-cache evidence')
            warm=True
        else:raise ValueError('incomplete cache state in completed operation')
        row['root_cache_warm']=warm;row['readback']=bool(row['readback'])
        counts[str(aw)]=counts.get(str(aw),0)+1
        readbacks[str(aw)]=readbacks.get(str(aw),0)+int(row['readback'])
    require(set(counts)==set(raw.get('vectors',{})),'vector/metric size coverage mismatch')
    for aw,count in counts.items():
        vector=raw['vectors'][aw]
        require(exact(vector.get('squares'),count) and exact(vector.get('readbacks'),readbacks[aw]),
                'completed operation/readback count mismatch')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();raw_path=args.raw.resolve();output=args.output.resolve()
    require(not output.exists(),'normalized output already exists')
    raw_hash=sha(raw_path);result=normalize(json.loads(raw_path.read_text()))
    result['raw_evidence']={'path':str(raw_path),'sha256':raw_hash,'status':'passed'}
    result['normalization']={'schema':'atomic27-stream-precision-v1',
        'validator_sha256':sha(__file__),'description':'Readback integers validated then converted to bool; warm cache derived only from coherent measured counters. No oracle rerun or raw-report mutation.'}
    require(sha(raw_path)==raw_hash,'raw report changed during normalization')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':'passed','output':str(output),'metrics':len(result['metrics']),
                      'raw_sha256':raw_hash}))


if __name__=='__main__':main()
