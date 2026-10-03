"""Fresh fault-only body over literal frozen normal-v1 RTL/fixture bytes."""
from pathlib import Path
import hashlib
from . import stream27_r15_pcie_avmm_native_v1 as normal

SELF='reference/stream27_r15_pcie_avmm_fault_native_v1.py'
CPP='rtl/tb/stream27_r15_pcie_avmm_faults.cpp'
ID='s4-r15-pcie-avmm-fault-q1-v1'


def role():
    m,f=normal.role()
    frozen=normal.BASE/'normal-v1/source/fpga'
    for name in f:
        if (frozen/name).read_bytes()!=f[name]:raise ValueError('R15_AVMM_FROZEN_NORMAL_IDENTITY')
    for p in (SELF,CPP):f[p]=(normal.ROOT/p).read_bytes()
    m['sources']={p:hashlib.sha256(v).hexdigest() for p,v in f.items()}
    m['build']['cpp_source']=CPP;m['test_role']='deliberate_fault'
    m['steps']=[dict(name='pcie-avmm-bounded-faults',argv=['{exe}'],expected_returncode=0,expected_stderr='',
       expected_stdout='R15_AVMM_FAULT_PASS cases=27 invalid_records=15 one_abort=1 reset_cache=1 vendor_core=0\n')]
    return m,f


def prepare(output):
    import json
    out=Path(output).resolve()
    if not out.is_relative_to(normal.BASE) or out.exists():raise ValueError('R15_AVMM_FAULT_FRESH_OUTPUT')
    if any((normal.ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')):raise ValueError('R15_AVMM_PAUSE')
    m,f=role();source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in f.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as h:h.write(raw)
    m['source_root']=str(source)
    with (out/'manifest.json').open('x') as h:json.dump(m,h,indent=2);h.write('\n')
    return dict(id=ID,manifest=str(out/'manifest.json'),status='SOURCE_PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    print(json.dumps(prepare(p.parse_args().output),indent=2))
