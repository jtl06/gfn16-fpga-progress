"""Source-exact rebind of the frozen 39-case endpoint corpus to current v8.

Only production RTL and new-input initialization change; fault CPP is literal.
Old failed v6 jobs remain failed. Current v8 normal is a queue dependency, not
substitution for execution of this corpus. No real core/vendor/CDC proof.
"""
import copy
import hashlib
import json
from pathlib import Path
from fpga.reference import stream27_r15_pcie_avmm_v8 as leaf

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/trackS-r15-pcie-avmm-packetfault-v8'
DONOR=ROOT/'results/throughput-20260929/trackS-r15-pcie-avmm-native-v6/fault-v6'
SELF='reference/stream27_r15_pcie_avmm_packetfault_v8.py'
RTL='rtl/kernel/genefer_stream27_r15_pcie_avmm_v1.sv'
NORMAL_CPP='rtl/tb/stream27_r15_pcie_avmm.cpp'
FAULT_CPP='rtl/tb/stream27_r15_pcie_avmm_faults.cpp'
BEFORE=b'if(resp_data[15:8]==0 && !protocol_error && !held_violation && !external_fault_valid &&\n'
AFTER=b'if(resp_data[15:8]==0 && !protocol_error && !external_fault_valid &&\n'


def role(negative=False):
    if type(negative) is not bool:raise ValueError('R15_AVMM_PACKETFAULT_BOOL')
    m=copy.deepcopy(json.loads((DONOR/'manifest.json').read_bytes()))
    f={p:(DONOR/'source/fpga'/p).read_bytes() for p in m['sources']}
    if any(hashlib.sha256(raw).hexdigest()!=m['sources'][p] for p,raw in f.items()):raise ValueError('R15_AVMM_PACKETFAULT_DONOR_PINS')
    f[RTL]=leaf.source()
    if negative:
        if f[RTL].count(BEFORE)!=1:raise ValueError('R15_AVMM_PACKETFAULT_MASK_ANCHOR')
        f[RTL]=f[RTL].replace(BEFORE,AFTER,1)
    before=b'd.clk=0;d.reset=1;d.link_ready=0;'
    if f[NORMAL_CPP].count(before)!=1:raise ValueError('R15_AVMM_PACKETFAULT_INPUT_INIT')
    f[NORMAL_CPP]=f[NORMAL_CPP].replace(before,before+b'd.external_fault_valid=0;',1)
    for p in (SELF,'reference/stream27_r15_pcie_avmm_v7.py','reference/stream27_r15_pcie_avmm_v8.py'):f[p]=(ROOT/p).read_bytes()
    m['sources']={p:hashlib.sha256(raw).hexdigest() for p,raw in f.items()}
    name='held-origin-negative' if negative else 'packet-fault39'
    m['steps'][0].update(name='pcie-avmm-v8-'+name,expected_returncode=1 if negative else 0,
      expected_stdout='' if negative else 'R15_AVMM_FAULT_PASS cases=39 invalid_records=33 one_abort=1 reset_cache=1 vendor_core=0\n',
      expected_stderr='R15_AVMM_FAULT_VALID_A_LEAK\n' if negative else '')
    m['test_role']='deliberate_fault'
    snapshot={RTL:m['sources'][RTL]}
    m['rtl_readiness'].update(candidate_id='s4-r15-pcie-avmm-v8-'+name,source_snapshot=snapshot,
      candidate_source_sha256=hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()).hexdigest())
    m['scope'].update(author='p16_independent_reviewer',frozen39_fault_cpp_literal=True,
      frozen39_fault_cpp_sha256=m['sources'][FAULT_CPP],external_fault_input_initialized_zero=True,
      current_endpoint_source='v8 unsigned export bounds plus external-fault conduit',
      negative_only_held_origin_A32_mask_removed=negative,
      required_normal_dependency='s4-r15-pcie-avmm-normal-q1-v8',normal_result_not_fault_substitution=True,
      old_v6_failed_jobs_preserved=True,old_native_result_inherited=False,
      real_core=False,vendor_IP=False,physical_CDC=False,independent_review=False,promotion_allowed=False)
    return m,f


def prepare(output,negative=False):
    out=Path(output).resolve()
    if not out.is_relative_to(BASE) or out.exists():raise ValueError('R15_AVMM_PACKETFAULT_FRESH_OUTPUT')
    if any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')):raise ValueError('R15_AVMM_PACKETFAULT_PAUSE')
    m,f=role(negative);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in f.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as h:h.write(raw)
    m['source_root']=str(source)
    with (out/'manifest.json').open('x') as h:json.dump(m,h,indent=2);h.write('\n')
    name='held-origin-negative' if negative else 'packet-fault39'
    return dict(id='s4-r15-pcie-avmm-'+name+'-q1-v8',manifest=str(out/'manifest.json'),status='SOURCE_PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--negative',action='store_true')
    a=p.parse_args();print(json.dumps(prepare(a.output,a.negative),indent=2))
