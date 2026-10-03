"""Private bounded PCIe application leaf, behavioural core-responder only.

Actual generated-IP routing/CDC/full65 compute must be qualified separately.
This helper captures files; it does not deploy, dispatch or grant cloud spend.
"""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/trackS-r15-pcie-avmm-native-v1'
SELF='reference/stream27_r15_pcie_avmm_native_v1.py'
RTL='rtl/kernel/genefer_stream27_r15_pcie_avmm_v1.sv'
CPP='rtl/tb/stream27_r15_pcie_avmm.cpp'
RUNTIME='rtl/tb/native_runtime_context_v1.h'
MODEL='reference/stream27_r15_pcie_avmm_model_v1.py'
PACKETS='reference/stream27_r15_shell_packets_v1.py'
ID='s4-r15-pcie-avmm-normal-q1-v1'


def role(mode='normal'):
    if mode not in ('normal','fault'):raise ValueError('R15_AVMM_MODE')
    paths=(SELF,RTL,CPP,RUNTIME,MODEL,PACKETS)
    files={p:(ROOT/p).read_bytes() for p in paths}
    pins={p:hashlib.sha256(v).hexdigest() for p,v in files.items()}
    stdout=('R15_AVMM_NORMAL_PASS data_records=128 contexts=2 burst=3 A32=3 snapshot=selected command_hold=11 vendor_core=0\n'
            if mode=='normal' else 'R15_AVMM_FAULT_PASS reserved_abort=1 one_abort=1 vendor_core=0\n')
    snapshot={RTL:pins[RTL]}
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',
      source_root='UNBOUND',output_parent='UNBOUND',sources=pins,
      build=dict(top='genefer_stream27_r15_pcie_avmm_v1',sv_sources=[RTL],cpp_source=CPP,
       parameters=dict(N=32),runtime_threads=1,
       cflags=['-std=c++17','-Werror=return-type','-DGFN16_RUNTIME_THREADS=1']),
      probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
      steps=[dict(name='pcie-avmm-'+mode,argv=['{exe}']+(['--faults'] if mode=='fault' else []),
       expected_returncode=0,expected_stderr='',expected_stdout=stdout)],
      test_role='normal' if mode=='normal' else 'deliberate_fault',
      rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-r15-pcie-avmm-v1',
       source_snapshot=snapshot,candidate_source_sha256=hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
       rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')),
      scope=dict(author='p16_independent_reviewer',execution_host='Azure-FIT only',
       behavioural_core_responder=True,N=32,actual_endpoint_RTL=True,
       vendor_IP=False,CDC=False,whole_compute=False,physical=False,host_GL=False,
       independent_review=False,promotion_allowed=False))
    return m,files


def prepare(output,mode='normal'):
    out=Path(output).resolve()
    if not out.is_relative_to(BASE) or out.exists():raise ValueError('R15_AVMM_FRESH_OUTPUT')
    if any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')):raise ValueError('R15_AVMM_PAUSE')
    m,files=role(mode);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(raw)
    m['source_root']=str(source)
    with (out/'manifest.json').open('x') as f:json.dump(m,f,indent=2);f.write('\n')
    return dict(id=ID if mode=='normal' else ID.replace('-normal-','-fault-'),manifest=str(out/'manifest.json'),status='SOURCE_PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--mode',default='normal',choices=('normal','fault'))
    a=p.parse_args();print(json.dumps(prepare(a.output,a.mode),indent=2))
