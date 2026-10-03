"""Additive negative-only preparation after v8 generic-prefix ambiguity.

Normal/external-fault v8 captures remain unchanged. Select ONLY the newline
A32 predicate, not the successful BEGIN predicate sharing its text prefix.
"""
from . import stream27_r15_pcie_avmm_v8_native as parent
import hashlib
import json
from pathlib import Path

SELF='reference/stream27_r15_pcie_avmm_v8_negative.py'
BEFORE=b'if(resp_data[15:8]==0 && !protocol_error && !held_violation && !external_fault_valid &&\n'
AFTER=b'if(resp_data[15:8]==0 && !protocol_error && !held_violation &&\n'


def role():
    m,f=parent.role('external-fault')
    if f[parent.RTL].count(BEFORE)!=1:raise ValueError('R15_AVMM_V8_NEGATIVE_A32_ANCHOR')
    f[parent.RTL]=f[parent.RTL].replace(BEFORE,AFTER,1)
    f[SELF]=(parent.ROOT/SELF).read_bytes()
    m['sources']={p:hashlib.sha256(raw).hexdigest() for p,raw in f.items()}
    m['steps']=[dict(name='pcie-avmm-v8-missing-external-mask',argv=['{exe}','--external-faults'],
      expected_returncode=1,expected_stdout='',expected_stderr='R15_AVMM_EXTERNAL_FAULT_VALID_A_LEAK\n')]
    snap={parent.RTL:m['sources'][parent.RTL]}
    m['rtl_readiness'].update(candidate_id='s4-r15-pcie-avmm-v8-missing-external-mask',source_snapshot=snap,
      candidate_source_sha256=hashlib.sha256(json.dumps(snap,sort_keys=True,separators=(',',':')).encode()).hexdigest())
    m['scope'].update(negative_control='ONLY external A32-origin mask removed',
      preparation_failure_preserved='original v8 negative prefix also matched BEGIN; no native run or qualification')
    return m,f


def prepare(output):
    out=Path(output).resolve()
    if not out.is_relative_to(parent.BASE) or out.exists():raise ValueError('R15_AVMM_V8_NEGATIVE_FRESH_OUTPUT')
    if any((parent.ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')):raise ValueError('R15_AVMM_V8_NEGATIVE_PAUSE')
    m,f=role();source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in f.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as h:h.write(raw)
    m['source_root']=str(source)
    with (out/'manifest.json').open('x') as h:json.dump(m,h,indent=2);h.write('\n')
    return dict(id='s4-r15-pcie-avmm-missing-external-mask-q1-v8',manifest=str(out/'manifest.json'),status='SOURCE_PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    print(json.dumps(prepare(p.parse_args().output),indent=2))
