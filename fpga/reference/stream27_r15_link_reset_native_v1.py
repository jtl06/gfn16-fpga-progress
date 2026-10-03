"""Bounded literal reset leaf with two-clock probes, not physical CDC proof."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/trackS-r15-link-reset-native-v1'
SELF='reference/stream27_r15_link_reset_native_v1.py'
RTL='rtl/kernel/genefer_stream27_r15_link_reset_v2.sv'
PROBE='rtl/tb/stream27_r15_link_reset_probe.sv'
CPP='rtl/tb/stream27_r15_link_reset_probe.cpp'
RUNTIME='rtl/tb/native_runtime_context_v1.h'
ID='s4-r15-link-reset-normal-q1-v1'


def role():
    f={p:(ROOT/p).read_bytes() for p in (SELF,RTL,PROBE,CPP,RUNTIME)}
    pins={p:hashlib.sha256(v).hexdigest() for p,v in f.items()}
    snap={p:pins[p] for p in (RTL,PROBE)}
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',
      source_root='UNBOUND',output_parent='UNBOUND',sources=pins,
      build=dict(top='stream27_r15_link_reset_probe',sv_sources=[RTL,PROBE],cpp_source=CPP,
       parameters={},runtime_threads=1,cflags=['-std=c++17','-Werror=return-type','-DGFN16_RUNTIME_THREADS=1']),
      probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
      steps=[dict(name='link-reset-two-domain-normal',argv=['{exe}'],expected_returncode=0,expected_stderr='',
       expected_stdout='R15_RESET_NORMAL_PASS ticks=1800 resets=5 seeds=0/fffffffe own_domain_release=2 async_assert=1 peer_wait=1 no_wrap=1 vendor_core=0\n')],
      test_role='normal',rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-r15-link-reset-v1',
       source_snapshot=snap,candidate_source_sha256=hashlib.sha256(json.dumps(snap,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
       rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')),
      scope=dict(author='p16_independent_reviewer',leaf_author='stream_interface',execution_host='Azure-FIT only',
       literal_reset_leaf=True,two_binary_clocks=True,metastability=False,physical_CDC=False,
       outstanding_command_write_drain=False,vendor_IP=False,whole_compute=False,
       independent_review=False,promotion_allowed=False))
    return m,f


def prepare(output):
    out=Path(output).resolve()
    if not out.is_relative_to(BASE) or out.exists():raise ValueError('R15_RESET_FRESH_OUTPUT')
    if any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')):raise ValueError('R15_RESET_PAUSE')
    m,f=role();source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in f.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as h:h.write(raw)
    m['source_root']=str(source)
    with (out/'manifest.json').open('x') as h:json.dump(m,h,indent=2);h.write('\n')
    return dict(id=ID,manifest=str(out/'manifest.json'),status='SOURCE_PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    print(json.dumps(prepare(p.parse_args().output),indent=2))
