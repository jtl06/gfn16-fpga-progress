"""Normal-first canonical_pipe1 bridge of the frozen AW5 eight-PRP corpus.

No baseline source is edited. The emitted canonical1 compiler bytes and exact
9N/10N finalization expectations replace only the baseline candidate binding;
initial states, proved labels, bit programs, expected values and T5b stay frozen.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from . import stream27_host_chain_param_v3 as compiler

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_p8_canonpipe_qualification.py'
NORMAL='rtl/tb/stream27_p8_canonpipe_prp_v1.cpp'
FAULT='rtl/tb/stream27_p8_canonpipe_faults_v1.cpp'
HELPER='rtl/tb/stream27_p8_canonpipe_helpers_v1.h'
SCALAR='rtl/tb/stream27_p8_canonpipe_scalar_v1.cpp'
CONFIG='rtl/tb/stream27_p8_canonpipe_config_v1.h'
DONOR=ROOT/'results/throughput-20260929/p8-small-prp-qualification-v1/input'
DONOR_SHA='f549e1d1b0c1953a21ddbb845228f77afb57597ef33387b0067be090546071e9'
COMPILER_SHA='017f581581d3f832cbb511a278901afb0a9a59ae6ed14a8df6234641634aa102'
DONOR_HELPER='rtl/tb/p8_small_prp_helpers_v1.h'
HELPER_SHA='dc95da89573897e9fcda25837d64c4eccde7d82d24c8e44eb80e94db50ec1abd'


def need(ok,why):
    if not ok:raise ValueError('P8 canonical qualification: '+why)


def sha(raw):return hashlib.sha256(raw).hexdigest()
def dump(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')
def replace_once(text,old,new):
    need(text.count(old)==1,'unique inherited helper anchor '+old)
    return text.replace(old,new,1)


def role(mode):
    need(mode in ('normal','faults'),'separate finite normal/fault mode')
    raw=(DONOR/'manifest.json').read_bytes();need(sha(raw)==DONOR_SHA,'frozen donor manifest')
    need(sha((ROOT/'reference/stream27_host_chain_param_v3.py').read_bytes())==COMPILER_SHA,'exact canonical compiler')
    m=json.loads(raw);files={}
    for name,pin in m['sources'].items():
        path=DONOR/'inputs/fpga'/name
        need(not path.is_symlink() and sha(path.read_bytes())==pin,'donor source '+name)
        files[name]=path.read_bytes()
    need(sha(files[DONOR_HELPER])==HELPER_SHA and m['p8_prp_qualification']['operations']==5000 and
         m['p8_prp_qualification']['host_cycles']==637672,'frozen eight complete PRPs')
    bundle=compiler.prepare(32,8,paired=True,contexts=1,canonical_pipe_stages=1)
    need(len(bundle['rtl_sources'])==60 and bundle['parameters']['CANONICAL_PIPE_STAGES']==1,
         'exact canonical1 paired60 small model')
    for name in m['build']['sv_sources']:files.pop(name)
    for name,text in bundle['files'].items():files['rtl/'+name]=text.encode()
    # New uniquely named copies, with no edits to frozen baseline helpers.
    helper=replace_once(files[DONOR_HELPER].decode(),'#include "stream27_host_core_v1.cpp"',
                        '#include "stream27_p8_canonpipe_scalar_v1.cpp"')
    helper=replace_once(helper,'(special?7u:6u)*N','(special?10u:9u)*N')
    helper=replace_once(helper,'(p.expected[0]==-1?7u:6u)*N','(p.expected[0]==-1?10u:9u)*N')
    scalar=replace_once(files['rtl/tb/stream27_host_core_v1.cpp'].decode(),
                        '#include "s4_host_config_v1.h"','#include "stream27_p8_canonpipe_config_v1.h"')
    need(scalar.count('(job.expected[0]==-1?7u:6u)*N')==2,'both scalar finalization assertions')
    scalar=scalar.replace('(job.expected[0]==-1?7u:6u)*N','(job.expected[0]==-1?10u:9u)*N')
    old_top=m['build']['top'];config=files['rtl/tb/s4_host_config_v1.h'].decode()
    need(config.count(old_top)==2,'paired top include/typedef only')
    config=config.replace(old_top,bundle['top'])
    files[HELPER]=helper.encode();files[SCALAR]=scalar.encode();files[CONFIG]=config.encode()
    for name in (SELF,NORMAL if mode=='normal' else FAULT):files[name]=(ROOT/name).read_bytes()
    for name,pin in bundle['source_sha256'].items():
        data=(ROOT/name).read_bytes();need(sha(data)==pin,'canonical compiler dependency '+name)
        files['canonical-lineage/'+name]=data
    m['build'].update(top=bundle['top'],sv_sources=['rtl/'+name for name in bundle['rtl_sources']],
        cpp_source=NORMAL if mode=='normal' else FAULT,
        parameters=dict(bundle['parameters'],EPOCH_SEED=65534))
    meta=m['p8_prp_qualification'];expected=[]
    for case in meta['cases']:
        case['baseline_cycles']=case['cycles'];case['cycles']+=96
        expected.append(f"P8_PRP_CASE index={case['index']} base={case['base']} operations={case['operations']} cycles={case['cycles']} prp={int(case['expected']==[1]+[0]*31)} reads=32")
    meta['baseline_host_cycles']=meta['host_cycles'];meta['host_cycles']+=8*96
    need(meta['host_cycles']==638440,'eight once-per-job 3N finalizations')
    meta['canonical_pipe_stages']=1
    meta['scope']='Own canonical1 eight complete AW5 PRPs, same frozen labels/bits/x0/pow words; persistent DUT and one initial load per PRP, no mid-PRP barrier; paired actual T5b/signed96 reads. Not fullN PRP/clock.'
    expected.append('P8_PRP_PASS cases=8 operations=5000 descriptors=4992 rows=32 reads=256 cycles=638440 base_floor=172')
    if mode=='normal':
        m['steps']=[dict(name='p8-canon1-eight-prp-normal',argv=['{exe}','{root}/assets/p8-eight-prp-v1.txt'],
            expected_returncode=0,expected_stdout='\n'.join(expected)+'\n',expected_stderr='')]
    else:
        m['steps']=[dict(name='p8-canon1-minimal-reset-cancellation',argv=['{exe}'],expected_returncode=0,
            expected_stdout='P8_FAULT_PASS underflow_cancels=1 reset_aborts=2 reset_ages=10,237 recovery_reads=128 nonzero_recovery_reads=32\n',expected_stderr=''),
            dict(name='p8-canon1-typed-oracle-negative',argv=['{exe}','--negative-oracle'],expected_returncode=1,
            expected_stdout='',expected_stderr='S4_HOST_ORACLE_TYPED aw=5 case=0 job=0 address=0 expected=19 actual=18\n')]
        m.pop('p8_prp_qualification')
    m['canonical_qualification']=dict(canonical_pipe_stages=1,mode=mode,donor_manifest_sha256=DONOR_SHA,
        shared_compiler_sha256=COMPILER_SHA,generated_sha256=bundle['generated_sha256'],
        source_sha256=bundle['source_sha256'],initial_states_and_oracle_assets_byte_preserved=True,
        added_candidate_finalization_cycles_per_job=96,baseline_native_result_not_inherited=True,
        full_N_numeric_locally_performed=False,promotion_allowed=False)
    m['sources']={name:sha(data) for name,data in files.items()}
    return m,files


def prepare(mode,output,budget):
    from fpga.tools import native_class_package_v2 as package
    output,budget=Path(output).resolve(),Path(budget).resolve()
    need(not output.exists() and not any((ROOT/name).exists() for name in ('queue/PAUSE','docs/briefs/PAUSE')),
         'fresh source/package output, no PAUSE')
    m,files=role(mode);source=output/'input/source/fpga';source.mkdir(parents=True)
    for name,data in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    m['source_root']=str(source);manifest=output/'input/manifest.json';dump(manifest,m)
    identifier='s4-p8-canon1-eight-prp-normal-q1-v1' if mode=='normal' else 's4-p8-canon1-host-faults-q1-v1'
    worker='s4-p8-canon1-'+('eight-prp' if mode=='normal' else 'host-faults')+'-gcp01-v1'
    packet=output/'packet-01';receipt=package.prepare(manifest,source,'gcp-c4d-static01-v1',worker,'run',packet,budget)
    def tool(name):return dict(path=str(ROOT/'tools'/name),sha256=sha((ROOT/'tools'/name).read_bytes()))
    spec=dict(schema='gfn16-global-ticket-v1',id=identifier,owner='soak-chunks',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
        test_role='normal' if mode=='normal' else 'deliberate_fault',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8,
        minimum_ram_rationale='Source-bound paired canonical1 P8 image, retain existing8GiB/model1/j2 admission; no host/tool/resource expansion.',
        est_minutes=15 if mode=='normal' else 10,promotion_bound=True,on='PASS_expected_contracts',
        allowed_hosts=['gfn16-azure-sim-f32','gfn16-azure-f16'],after=['s4-aw16-p8-canon-pipe-host-normal-q1-v2'],
        packages=[dict(profile='gcp-c4d-static01-v1',worker_id=worker,archive=str(packet/'package.tar.gz'),
            sha256=receipt['archive_sha256'],ticket_sha256=receipt['ticket_sha256'],
            manifest_sha256=sha((packet/'manifest.json').read_bytes()),native_root=receipt['native_root'],
            runner='tools/native_class_package_v2.py',runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[tool('native_package_v3.py'),tool('native_package_v2.py')],max_seconds=3700)],
        scope=meta_scope(mode))
    dump(output/'global-ticket.json',spec)
    return dict(status='source_prepared_not_native',id=identifier,manifest_sha256=sha(manifest.read_bytes()),
                global_ticket=str(output/'global-ticket.json'),operations=5000 if mode=='normal' else None)


def meta_scope(mode):
    return ('Own canonical_pipe1 '+('eight proved-label AW5 PRPs:5000 dependent operations/4992descriptors/256 full signed96 T5b/pow words,638440 exacthostcycles; same labels/basefloor172/bitprogram/x0 from frozen donor, +3N once/job.' if mode=='normal' else
        'whole-host underflow cancellation/sticky quarantine, one-edge cold10/warm237 reset with FIFO4,128 recoverywords including32nonzero, separate exact oracle negative. Standalone canonical-cell faults are separate reused evidence.')+
        ' No inherited baseline numeric PASS, current PrimeGrid claim, fullN PRP, achievable clock or production adoption. Normal and deliberate-fault jobs independent; promotion remains evidence gated.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('normal','faults'),required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--budget',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.mode,args.output,args.budget),indent=2))
