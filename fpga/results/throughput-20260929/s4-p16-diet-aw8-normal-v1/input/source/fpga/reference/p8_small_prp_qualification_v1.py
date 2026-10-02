"""Normal-first eight AW5/P8 PRPs; immutable RTL, ordinary small integer oracle.

Only source preparation/model arithmetic runs locally. The shared queue owns
all Linux HDL execution and all-lane expansion. Faults are a separate packet.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from . import core27_small_gfn_prp_v1 as oracle
from . import stream27_host_chain_native_v4 as inherited
from . import stream27_host_chain_full_native_v1 as packaging

ROOT=inherited.ROOT
SELF='reference/p8_small_prp_qualification_v1.py'
CPP='rtl/tb/p8_small_prp_qualification_v1.cpp'
HELPER='rtl/tb/p8_small_prp_helpers_v1.h'
ID='s4-aw5-p8-eight-prp-normal-q1-v1'
SPEC=((173,'composite',2),(176,'composite',257),(448,'prime',3),(7552,'prime',3),
      (989233152,'prime',5),(999999998,'composite',1409),(999999999,'composite',2),(1000000000,'composite',193))

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')

def corpus():
    cases=[];lines=['5 8'];output=[];total=0
    for index,(base,label,witness) in enumerate(SPEC):
        proof=oracle.prove_label(base,label,witness)
        assert base>=172
        exponent=base**32;bits=[int(x) for x in bin(exponent)[2:]]
        value=pow(2,exponent,exponent+1);chained=1
        for bit in bits:chained=chained*chained*(1<<bit)%(exponent+1)
        assert value==chained and (label!='prime' or value==1)
        digits=oracle.encode(value,base);assert oracle.decode(digits,base)==value
        cycles=102+(len(bits)-1)*127+129+2+(7 if digits[0]==-1 else 6)*32+32+4
        total+=cycles
        lines += [f'{base} {len(bits)}',' '.join(map(str,bits)),' '.join(map(str,digits))]
        output.append(f'P8_PRP_CASE index={index} base={base} operations={len(bits)} cycles={cycles} prp={int(value==1)} reads=32')
        cases.append(dict(index=index,base=base,label=label,proof=proof,operations=len(bits),doubles=sum(bits),
                          bits=bits,expected=digits,residue_hex=hex(value),cycles=cycles))
    operations=sum(x['operations'] for x in cases)
    output.append(f'P8_PRP_PASS cases=8 operations={operations} descriptors={operations-8} rows=32 reads=256 cycles={total} base_floor=172')
    return '\n'.join(lines)+'\n',dict(base_floor=172,cases=cases,operations=operations,
        host_cycles=total,reads=256,scope='Eight complete AW5 PRPs, persistent DUT/new base and initial load per job; no reload within PRP; actual T5b/all signed96 words.'),'\n'.join(output)+'\n'

def prepare(output,budget):
    from fpga.tools import native_class_package_v2 as package
    output=Path(output).resolve();budget=Path(budget).resolve()
    assert not output.exists() and not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE'))
    assert sha(budget)==packaging.BUDGET_SHA
    seed=output/'input';old=inherited.prepare(seed,n=32,p=8)
    source=seed/'inputs/fpga';manifest=json.loads((seed/'manifest.json').read_text())
    text=(source/'rtl/tb/stream27_host_chain_v1.cpp').read_text()
    assert text.count('int main(int argc,char** argv)')==1
    (source/HELPER).write_text(text.split('int main(int argc,char** argv)')[0])
    for name in (CPP,SELF):
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
    asset,meta,expected=corpus();(source/'assets/p8-eight-prp-v1.txt').write_text(asset)
    dump(source/'assets/p8-eight-prp-oracle-v1.json',meta)
    manifest['build']['cpp_source']=CPP
    manifest['steps']=[dict(name='p8-eight-prp-normal',argv=['{exe}','{root}/assets/p8-eight-prp-v1.txt'],
        expected_returncode=0,expected_stdout=expected,expected_stderr='')]
    manifest['sources']={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file()}
    manifest['p8_prp_qualification']=meta
    dump(seed/'manifest.json',manifest)
    variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1';worker='s4-p8-eight-prp-'+pair+'-v1';packet=output/('packet-'+pair)
        r=package.prepare(seed/'manifest.json',source,profile,worker,'run',packet,budget)
        variants.append(dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),
            sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],manifest_sha256=sha(packet/'manifest.json'),
            native_root=r['native_root'],runner=packaging.PACKAGE,runner_sha256=packaging.PACKAGE_SHA,
            stager=str(ROOT/packaging.STAGER),stager_sha256=packaging.STAGER_SHA,
            stager_dependencies=[dict(path=str(ROOT/packaging.COMPANION),sha256=packaging.COMPANION_SHA)],max_seconds=3700))
    ticket=dict(schema='gfn16-global-ticket-v1',id=ID,owner='qualification-recovery',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=8,minimum_ram_rationale='Unmeasured paired P8 peak; preserve inherited 8GiB minimum.',
        est_minutes=15,promotion_bound=False,test_role='normal',packages=variants,
        rtl_readiness_note='Unchanged previously native-qualified RTL; original owner-declared ready timestamp unknown, not backfilled.')
    dump(output/'global-ticket-v1.json',ticket)
    result=dict(status='normal_source_prepared_not_executed',id=ID,qualification=meta,
        unchanged_rtl=True,geometry=old['geometry'],manifest=str(seed/'manifest.json'),native_executed=False)
    dump(output/'preparation.json',result);return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--budget',type=Path,required=True)
    args=parser.parse_args();r=prepare(args.output,args.budget);print(json.dumps(dict(status=r['status'],id=ID,operations=r['qualification']['operations'])))
