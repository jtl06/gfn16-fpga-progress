"""Bounded CDC scoreboard role; not PCIe vendor/IP or physical CDC proof."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/trackS-r15-cdc-native-v1'
SELF='reference/stream27_r15_async_fifo_native.py'
RTL='rtl/kernel/genefer_stream27_r15_async_fifo_v1.sv'
CPP='rtl/tb/stream27_r15_async_fifo.cpp'
RUNTIME='rtl/tb/native_runtime_context_v1.h'


def role():
    files={p:(ROOT/p).read_bytes() for p in (SELF,RTL,CPP,RUNTIME)}
    pins={p:hashlib.sha256(v).hexdigest() for p,v in files.items()}
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',source_root='UNBOUND',output_parent='UNBOUND',sources=pins,
      build=dict(top='genefer_stream27_r15_async_fifo_v1',sv_sources=[RTL],cpp_source=CPP,
       parameters=dict(WIDTH=256,ADDR_W=3),cflags=['-std=c++17','-Werror=return-type','-DGFN16_RUNTIME_THREADS=1']),
      probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
      steps=[dict(name='cdc-scoreboard',argv=['{exe}'],expected_returncode=0,expected_stderr='',
       expected_stdout='R15_CDC_PASS ticks=24000 resets=6 width=256 depth=8 independent_clocks=1 runtime_threads=1\n')],
      test_role='normal',rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-r15-cdc-v1',
       source_snapshot={RTL:pins[RTL]},candidate_source_sha256=hashlib.sha256(json.dumps({RTL:pins[RTL]},sort_keys=True,separators=(',',':')).encode()).hexdigest(),
       rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')),
      scope=dict(execution_host='Azure-FIT only',author='stream_interface',cdc_rtl=True,vendor_pcie=False,
       metastability_or_physical_constraints_qualified=False,whole_core=False))
    return m,files


def prepare(output):
    out=Path(output).resolve()
    if not out.is_relative_to(BASE) or out.exists():raise ValueError('R15_CDC_FRESH_OUTPUT')
    if any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')):raise ValueError('R15_CDC_PAUSE')
    m,files=role();source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    m['source_root']=str(source)
    with (out/'manifest.json').open('x') as f:json.dump(m,f,indent=2);f.write('\n')
    return {'manifest':str(out/'manifest.json'),'status':'SOURCE_PREPARED_NOT_SUBMITTED'}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    print(json.dumps(prepare(p.parse_args().output),indent=2))
