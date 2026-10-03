"""Additive sampled-value INTERNAL diagnostic; immutable v1/v2 failures retained."""
import json
import tarfile
from . import stream27_r15_canonical_foldstage_native as n

ROOT=n.ROOT
CPP='rtl/tb/stream27_r15_canonical_foldstage_internal_v3.cpp'
SELF='reference/stream27_r15_canonical_foldstage_internal_v3_native.py'

def identifier(aw):return f's4-p16-r15-canonical-foldstage-aw{aw}-internal-ff-q1-v3'

def role(aw=8):
    evidence=ROOT/'queue/evidence'/n.identifier(aw,'normal')
    gate_raw=(evidence/'gate-receipt.json').read_bytes()
    n.b.need(json.loads(gate_raw)['status']=='PASS_expected_contracts','OWN_NORMAL_HEADER_GATE')
    with tarfile.open(evidence/'attempt-0/collected/output/native/generated-sources.tar.gz') as archive:
        raw=archive.extractfile('V'+n.TOP+'___024root.h').read()
    for label in ('parent','local'):
        for member in ('state','correction0','stored_digit_bad','fold_q_payload','fold_remainder_payload','fold_range_payload'):
            n.b.need(n.TOP+'__DOT__'+label+'_dut__DOT__'+member in raw.decode(),'ACTUAL_GENERATED_MEMBER')
    n.b.need(n.TOP+'__DOT__local_dut__DOT__value' in raw.decode(),'ACTUAL_VALUE_FF')
    m,files=n.role(aw,'normal')
    files[CPP]=(ROOT/CPP).read_bytes();files[SELF]=(ROOT/SELF).read_bytes()
    m['rtl_readiness']['candidate_id']=identifier(aw)
    m['build']['cpp_source']=CPP;m['test_role']='deliberate_fault'
    m['steps']=[dict(name='canonical-foldstage-sampled-internal-ff',argv=['{exe}'],expected_returncode=0,
        expected_stdout=f'R15_FOLDSTAGE_INTERNAL_FF_V3_PASS aw={aw} cases=4 signed_extrema=1 code=7 parent_origin=3 candidate_origin=4 recovery_reads={1<<aw} injected_before_READ=1 actual_value_fold_tokens=1 production_mutated=0 simulation_only=1 runtime_threads=1\n',expected_stderr='')]
    m['sources']={name:n.sha(data) for name,data in files.items()}
    m['foldstage']['internal_FF_diagnostic']=dict(own_normal_gate_sha256=n.sha(gate_raw),actual_header_sha256=n.sha(raw),
        mutation='Stored correction0[0] after actual accepted BEGIN, before READ; explicit VALUE/fold q/remainder/range token assertions before origin checks.',
        cases=['+3base','-3base','INT_MIN','INT_MAX'],production_source_unchanged=True,
        arbitrary_fault_immunity_claim=False,
        retained_failed_predecessor=f's4-p16-r15-canonical-foldstage-aw{aw}-internal-ff-q1-v2',
        predecessor_sampling_failure_not_waived=True)
    return m,files

def prepare(aw=8):
    m,files=role(aw);out=n.BASE/f'aw{aw}-internal-ff-v3'
    n.b.need(not out.exists(),'FRESH_INTERNAL_ROLE')
    source=out/'source/fpga';source.mkdir(parents=True)
    for name,data in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as f:f.write(data)
    m['source_root']=str(source);n.dump(out/'manifest.json',m)
    result=n.package(out,aw,'fault',logical_id=identifier(aw))
    ticket=json.loads((out/'global-ticket.json').read_bytes())
    ticket['priority']='P2'
    if aw==16:ticket['after'].append(identifier(8))
    # Fresh, not submitted metadata only: preserve packets and functional source.
    n.dump(out/'global-ticket-p2.json',ticket)
    result['ticket']=str(out/'global-ticket-p2.json')
    return result

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--aw',type=int,choices=(8,16),default=8)
    print(json.dumps(prepare(parser.parse_args().aw),indent=2))
