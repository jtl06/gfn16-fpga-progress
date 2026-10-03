"""AUTHOR bounded stand-alone guard roles. No vendor/whole-core proof."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from . import stream27_r15_dma_aperture_model_v1 as model

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/trackS-r15-dma-aperture-native-v1'
SELF='reference/stream27_r15_dma_aperture_native_v1.py'
MODEL='reference/stream27_r15_dma_aperture_model_v1.py'
RTL='rtl/kernel/genefer_stream27_r15_dma_aperture_v1.sv'
CPP='rtl/tb/stream27_r15_dma_aperture.cpp'
RUNTIME='rtl/tb/native_runtime_context_v1.h'
FROZEN_RTL='244ec8e67e8f61dddc3cb7c91f82ebe17fb92de2252a13fd3e55fccbc90fd644'
NORMAL='R15_APERTURE_NORMAL_PASS writes=43 reads=4 held=1 firstbeat=1 symbols64=1 dts_partial=1 core_vendor=0\n'
FAULT='R15_APERTURE_FAULT_PASS cases=20 high_alias=1 dts_split=1 one_fault=1 zero_invalid=1 held_tail=1 unresolved_tail_reset=1 reset=1 core_vendor=0\n'


def role(variant='normal'):
    if variant not in ('normal','fault','missing-mask'):raise ValueError('R15_APERTURE_VARIANT')
    f={p:(ROOT/p).read_bytes() for p in (SELF,MODEL,RTL,CPP,RUNTIME)}
    if hashlib.sha256(f[RTL]).hexdigest()!=FROZEN_RTL:raise ValueError('R15_APERTURE_FROZEN_RTL')
    if variant=='missing-mask':
        before=b"rd_readdata=terminal?256'b0:rd_data_q;"
        after=b'rd_readdata=rd_data_q;'
        if f[RTL].count(before)!=1:raise ValueError('R15_APERTURE_MASK_ANCHOR')
        f[RTL]=f[RTL].replace(before,after,1)
    pins={p:hashlib.sha256(v).hexdigest() for p,v in f.items()}
    snapshot={RTL:pins[RTL]}
    argv=['{exe}'] if variant=='normal' else ['{exe}','--faults']
    step=dict(name='dma-aperture-'+variant,argv=argv,expected_returncode=1 if variant=='missing-mask' else 0,
      expected_stdout='' if variant=='missing-mask' else NORMAL if variant=='normal' else FAULT,
      expected_stderr='R15_APERTURE_FAULT_ORIGIN_DATA_LEAK\n' if variant=='missing-mask' else '')
    m=dict(schema='native-source-gate-v1',status='prepared_not_executed',source_root='UNBOUND',output_parent='UNBOUND',sources=pins,
      build=dict(top='genefer_stream27_r15_dma_aperture_v1',sv_sources=[RTL],cpp_source=CPP,parameters={},runtime_threads=1,
        cflags=['-std=c++17','-Werror=return-type','-DGFN16_RUNTIME_THREADS=1']),
      probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
      steps=[step],test_role='normal' if variant=='normal' else 'bounded-fault',
      rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-r15-dma-aperture-v1-'+variant,
        source_snapshot=snapshot,candidate_source_sha256=hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')),
      scope=dict(author='p16_independent_reviewer',variant=variant,contract=model.CONTRACT,
        independent_review=False,whole_core=False,vendor_IP=False,CDC=False,physical=False,host_GL=False,
        fault_origin_negative_control=variant=='missing-mask',mutant_original_sha256=FROZEN_RTL if variant=='missing-mask' else None,
        promotion_allowed=False))
    return m,f


def prepare(output,variant='normal'):
    out=Path(output).resolve()
    if not out.is_relative_to(BASE) or out.exists():raise ValueError('R15_APERTURE_FRESH_OUTPUT')
    if any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')):raise ValueError('R15_APERTURE_PAUSE')
    m,f=role(variant);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in f.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as h:h.write(raw)
    m['source_root']=str(source)
    with (out/'manifest.json').open('x') as h:json.dump(m,h,indent=2);h.write('\n')
    return dict(id='s4-r15-dma-aperture-'+variant+'-q1-v1',manifest=str(out/'manifest.json'),status='SOURCE_PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--variant',default='normal')
    a=p.parse_args();print(json.dumps(prepare(a.output,a.variant),indent=2))
