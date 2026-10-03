"""Additive actual-header-bound INTERNAL-only stored-FF diagnostic."""
import json
import tarfile
from pathlib import Path
from . import stream27_r15_canonical_foldstage_native as n

ROOT=n.ROOT;CPP='rtl/tb/stream27_r15_canonical_foldstage_internal.cpp'
SELF='reference/stream27_r15_canonical_foldstage_internal_native.py'

def role(aw=8):
    # Freeze the role through the ordinary owner's existing code, then use a
    # uniquely named additive role. Prior four packets/RTL remain immutable.
    native_id=n.identifier(aw,'normal');evidence=ROOT/'queue/evidence'/native_id
    gate_raw=(evidence/'gate-receipt.json').read_bytes();gate=json.loads(gate_raw)
    n.b.need(gate['status']=='PASS_expected_contracts','OWN_NORMAL_HEADER_GATE')
    archive=evidence/'attempt-0/collected/output/native/generated-sources.tar.gz'
    header='V'+n.TOP+'___024root.h'
    with tarfile.open(archive) as t:raw=t.extractfile(header).read()
    for label in ('parent','local'):
        for name in ('state','correction0','stored_digit_bad'):
            n.b.need(n.TOP+'__DOT__'+label+'_dut__DOT__'+name in raw.decode(),'ACTUAL_GENERATED_MEMBER')
    identifier=f's4-p16-r15-canonical-foldstage-aw{aw}-internal-ff-q1-v2'
    m,files=n.role(aw,'normal');files[CPP]=(ROOT/CPP).read_bytes();files[SELF]=(ROOT/SELF).read_bytes()
    m['rtl_readiness']['candidate_id']=identifier.removesuffix('-q1-v1')
    m['build']['cpp_source']=CPP;m['test_role']='deliberate_fault'
    m['steps']=[dict(name='canonical-foldstage-internal-ff',argv=['{exe}'],expected_returncode=0,
      expected_stdout=f'R15_FOLDSTAGE_INTERNAL_FF_PASS aw={aw} cases=4 signed_extrema=1 code=7 parent_origin=3 candidate_origin=4 recovery_reads={1<<aw} production_mutated=0 simulation_only=1 runtime_threads=1\n',expected_stderr='')]
    m['sources']={name:n.sha(data) for name,data in files.items()}
    m['foldstage']['internal_FF_diagnostic']=dict(own_normal_gate_sha256=n.sha(gate_raw),
      actual_header_sha256=n.sha(raw),mutation='Both correction0[0] FFs after actual accepted-BEGIN+READ, before VALUE; ±3base/INT_MIN/INT_MAX, no state/range/RAM/public output mutation.',
      arbitrary_fault_immunity_claim=False,retained_failed_predecessor=f's4-p16-r15-canonical-foldstage-aw{aw}-internal-ff-q1-v1',
      predecessor_failed_before_native_commands='Invalid uppercase FF step-name label; source/runtime/oracle unchanged.')
    return m,files,identifier

def prepare(aw=8):
    m,files,identifier=role(aw)
    out=n.BASE/('aw'+str(aw)+'-internal-ff-v2');n.b.need(not out.exists(),'FRESH_INTERNAL_ROLE')
    source=out/'source/fpga';source.mkdir(parents=True)
    for name,data in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as f:f.write(data)
    m['source_root']=str(source);n.dump(out/'manifest.json',m)
    # Existing owner package routine chooses this unique ID BEFORE emitting
    # either fresh packet; all previous packets/IDs are untouched.
    return n.package(out,aw,'fault',logical_id=identifier)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--aw',type=int,choices=(8,16),default=8);a=p.parse_args()
    print(json.dumps(prepare(a.aw),indent=2))
