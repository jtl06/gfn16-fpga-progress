"""Zero-extra-edge canonical threshold snapshot; native normals first.

Uses the frozen 42-image small integer oracle and exact signed96/read calendar.
Only metadata and N<=256 corpus arithmetic may execute on the coordinator.
No timing improvement is claimed before the combined physical refit.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from fpga.reference import stream27_canonical_pipe_v1 as donor

ROOT=donor.ROOT
SELF='reference/stream27_canonical_localbase_v1.py'
TEST='tests/test_stream27_canonical_localbase_v1.py'
SV='rtl/kernel/genefer_stream27_canonical_image_localbase_v1.sv'
TOP='genefer_stream27_canonical_image_localbase_v1'
CPP='rtl/tb/stream27_canonical_localbase_normal_v1.cpp'
FAULT='rtl/tb/stream27_canonical_localbase_fault_v1.cpp'
DONOR_SHA='5906556e3749033fd84e6db107b9be2a408758593d303dd7a0224a08f156b2b2'
DONOR_SV_SHA='763b069a9797b91c7122bdf30fe86879b8c34dd318613ec4e096797610a379a5'


def need(ok,why):
    if not ok:raise ValueError('CANON_LOCALBASE '+why)


def sha(raw):return hashlib.sha256(raw).hexdigest()
def dump(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')


def role(aw=5,p=8,mode='normal'):
    need(mode in ('normal','faults') and (mode=='normal' or (aw,p)==(5,8)),
         'separate exact AW5/P8 fault role')
    need(sha((ROOT/donor.SELF).read_bytes())==DONOR_SHA and
         sha((ROOT/donor.SV).read_bytes())==DONOR_SV_SHA,'frozen canonical1 donor')
    m,files=donor.role(aw,p)
    for name in (SV,CPP,SELF,TEST):files[name]=(ROOT/name).read_bytes()
    m['build'].update(top=TOP,sv_sources=[donor.RAM,SV],cpp_source=CPP)
    expected='CANON_LOCALBASE_PASS aw='+str(aw)+' p='+str(p)+' '+' '.join(
        f'{key}={value}' for key,value in donor.counts(aw,p).items())+'\n'
    m['steps']=[dict(name='canonical-localbase-normal',argv=['{exe}'],expected_returncode=0,
                     expected_stdout=expected,expected_stderr='')]
    if mode=='faults':
        files[FAULT]=(ROOT/FAULT).read_bytes();m['build']['cpp_source']=FAULT
        m['steps']=[dict(name='canonical-localbase-range-reset',argv=['{exe}'],expected_returncode=0,
            expected_stdout='CANON_LOCALBASE_FAULT_PASS aw=5 p=8 range_faults=2 reset_aborts=11 pending_read_resets=1 recovery_images=15 signed96_reads=480\n',expected_stderr=''),
            dict(name='canonical-localbase-wrong-word',argv=['{exe}','--wrong-word'],expected_returncode=1,
                 expected_stdout='',expected_stderr='CANON_PIPE_WRONG_WORD_REJECT\n')]
    m['sources']={name:sha(data) for name,data in files.items()}
    m['localbase']=dict(parent_sv_sha256=DONOR_SV_SHA,added_cycles=0,
        normal_cycles=9*(1<<aw),special_cycles=10*(1<<aw),read_request_to_response=1,
        coherent_thresholds=['b','2b','3b','-b','-2b','b-1'],capture='legal_begin only',
        arithmetic_and_error_contract_unchanged=True,physical_timing_not_measured=True,mode=mode)
    return m,files


def prepare(output,aw,p,budget,mode='normal'):
    from fpga.tools import native_class_package_v2 as package
    out=Path(output).resolve();budget=Path(budget).resolve()
    need(not out.exists() and not any((ROOT/name).exists() for name in
         ('docs/briefs/PAUSE','queue/PAUSE')),'fresh output/no PAUSE')
    m,files=role(aw,p,mode);now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    source=out/'input/source/fpga';source.mkdir(parents=True)
    for name,data in files.items():
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    manifest=out/'input/manifest.json';dump(manifest,m)
    worker=f's4-canon-localbase-aw{aw}-p{p}-'+('faults-' if mode=='faults' else '')+'gcp01-v1';packet=out/'packet'
    receipt=package.prepare(manifest,source,'gcp-c4d-static01-v1',worker,'run',packet,budget)
    def pin(name):return dict(path=str(ROOT/'tools'/name),sha256=sha((ROOT/'tools'/name).read_bytes()))
    snapshot={SV:sha(files[SV])}
    ticket=dict(schema='gfn16-global-ticket-v1',id=f's4-canon-localbase-aw{aw}-p{p}-{mode}-q1-v1',
        owner='soak-chunks',created=now,priority='P1',kind='sim',needs='verilator',test_role='normal' if mode=='normal' else 'deliberate_fault',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=4,
        minimum_ram_rationale='Two-RTL standalone N<=256 image leaf; retain bounded4GiB exploratory minimum, no full-core peak claim.',
        est_minutes=5,promotion_bound=False,on='PASS_expected_contracts',
        allowed_hosts=['gfn16-pilot-c4d','gfn16-azure-sim-f32','gfn16-azure-f16'],
        after=[f's4-canon-localbase-aw5-p{p}-normal-q1-v1'] if aw==8 or mode=='faults' else [],
        rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-canonical-localbase-v1',
            rtl_ready_at_utc=now,source_snapshot=snapshot,
            candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode())),
        packages=[dict(profile='gcp-c4d-static01-v1',worker_id=worker,archive=str(packet/'package.tar.gz'),
            sha256=receipt['archive_sha256'],ticket_sha256=receipt['ticket_sha256'],
            manifest_sha256=sha((packet/'manifest.json').read_bytes()),native_root=receipt['native_root'],
            runner='tools/native_class_package_v2.py',runner_sha256=pin('native_class_package_v2.py')['sha256'],
            stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=pin('native_package_v4.py')['sha256'],
            stager_dependencies=[pin('native_package_v3.py'),pin('native_package_v2.py')],max_seconds=3700)],
        scope='42 own standalone exact normal/special images/all signed96 words at unchanged9N/10N, E0→E1 reads; coherent setup-only base terms, same value/write-legality token. No inherited native/whole-host/clock PASS. Fault tests separate.' if mode=='normal' else
          'Own same-leaf range rejection/sticky quarantine,11 reset abortions across READ/VALUE/PROCESS and special write, pendingE0/E1 revocation,15 full recovery images/480signed96 reads; separate exact wrong-word comparator negative. Normal source unchanged; no whole-host/clock/adoption claim.')
    dump(out/'global-ticket.json',ticket)
    return dict(status='normal_source_prepared_not_native',id=ticket['id'],global_ticket=str(out/'global-ticket.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aw',type=int,choices=(5,8),required=True)
    parser.add_argument('--p',type=int,choices=(8,16),default=8)
    parser.add_argument('--mode',choices=('normal','faults'),default='normal')
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--budget',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.output,args.aw,args.p,args.budget,args.mode),indent=2))
