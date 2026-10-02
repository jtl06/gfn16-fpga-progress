"""Separate minimal cancellation/reset sample on the frozen normal P8 image."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
from . import p8_small_prp_qualification_v1 as normal

ROOT=normal.ROOT
ID='s4-aw5-p8-minimal-faults-q1-v1'
CPP='rtl/tb/p8_small_prp_faults_v1.cpp'
SELF='reference/p8_small_prp_faults_v1.py'

def prepare(output,budget):
    from fpga.tools import native_class_package_v2 as package
    pack=normal.packaging;output=Path(output).resolve();budget=Path(budget).resolve()
    assert not output.exists() and not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE'))
    assert normal.sha(budget)==pack.BUDGET_SHA
    parent=ROOT/'results/throughput-20260929/p8-small-prp-qualification-v1/input'
    manifest=json.loads((parent/'manifest.json').read_text());source=output/'input/inputs/fpga'
    for name,pin in manifest['sources'].items():assert normal.sha(parent/'inputs/fpga'/name)==pin
    shutil.copytree(parent/'inputs/fpga',source)
    for name in (CPP,SELF):
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
    manifest['build']['cpp_source']=CPP
    manifest['steps']=[dict(name='p8-minimal-reset-cancellation',argv=['{exe}'],expected_returncode=0,
        expected_stdout='P8_FAULT_PASS underflow_cancels=1 reset_aborts=2 reset_ages=10,237 recovery_reads=128 nonzero_recovery_reads=32\n',expected_stderr=''),
        dict(name='p8-typed-oracle-negative',argv=['{exe}','--negative-oracle'],expected_returncode=1,expected_stdout='',
             expected_stderr='S4_HOST_ORACLE_TYPED aw=5 case=0 job=0 address=0 expected=19 actual=18\n')]
    manifest.pop('p8_prp_qualification')
    manifest['fault_scope']='Underflow registered error/sticky quarantine, one-edge reset at cold age10 and warm237 with FIFO4, 3 zero recovery reads plus one nonzero recovery32words. No dedicated external cancel input or exhaustive phase coverage.'
    manifest['sources']={str(p.relative_to(source)):normal.sha(p) for p in sorted(source.rglob('*')) if p.is_file()}
    path=output/'input/manifest.json';normal.dump(path,manifest);variants=[]
    for pair in ('01','23'):
        profile='gcp-c4d-static'+pair+'-v1';worker='s4-p8-minimal-faults-'+pair+'-v1';packet=output/('packet-'+pair)
        r=package.prepare(path,source,profile,worker,'run',packet,budget)
        variants.append(dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),
            sha256=r['archive_sha256'],ticket_sha256=r['ticket_sha256'],manifest_sha256=normal.sha(packet/'manifest.json'),
            native_root=r['native_root'],runner=pack.PACKAGE,runner_sha256=pack.PACKAGE_SHA,
            stager=str(ROOT/pack.STAGER),stager_sha256=pack.STAGER_SHA,
            stager_dependencies=[dict(path=str(ROOT/pack.COMPANION),sha256=pack.COMPANION_SHA)],max_seconds=3700))
    ticket=dict(schema='gfn16-global-ticket-v1',id=ID,owner='qualification-recovery',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=8,minimum_ram_rationale='Unmeasured paired P8 peak; preserve inherited 8GiB minimum.',
        est_minutes=10,promotion_bound=False,test_role='deliberate_fault',packages=variants)
    normal.dump(output/'global-ticket-v1.json',ticket)
    return dict(status='fault_source_prepared_not_executed',id=ID)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--budget',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.output,args.budget)))
