"""Private AUTHOR watchdog component diagnostic; no whole-NTT qualification."""
import argparse
import json
from pathlib import Path
from .stream27_context_storage_combo_registerederror_native import sha, need, dump

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_watchdog_native.py'
CPP='rtl/tb/stream27_r15_watchdog_probe.cpp'
SV='rtl/tb/stream27_r15_watchdog_probe.sv'
WATCH='rtl/kernel/genefer_stream27_r15_progress_watchdog_v1.sv'
RUNTIME='rtl/tb/native_runtime_context_v1.h'
PINS={WATCH:'0e0bbad86bc4735bb766c6b67850bfa69ceca71bb6ab1a07b8bab5ab16372c71',
      RUNTIME:'afd27444d1b4c991d11c84482db08f2fcef62757968e96ac83c5d44e55622f90'}
READY='2026-10-03T08:13:44Z'
IDS={mode:'s4-r15-watchdog-'+mode+'-q1-v1' for mode in ('normal','fault')}


def role(mode='normal'):
    need(mode in IDS,'R15_WATCHDOG_MODE')
    files={p:(ROOT/p).read_bytes() for p in (SELF,CPP,SV,WATCH,RUNTIME)}
    for p,pin in PINS.items():need(sha(files[p])==pin,'R15_WATCHDOG_PIN:'+p)
    normal='R15_WATCHDOG_NORMAL_PASS trace_age=20805 limit=20480 old_false_abort=1 completed=96/95 repaired_errors=0 runtime_threads=1 model_scope=counter_only\n'
    fault='R15_WATCHDOG_FAULT_PASS cases=6 contexts=2 peer_cannot_hide_stall=1 gap_disarm=1 sticky_reset_only=1 runtime_threads=1\n'
    steps=[dict(name='watchdog-'+mode,argv=['{exe}']+(['--fault'] if mode=='fault' else []),
          expected_returncode=0,expected_stdout=fault if mode=='fault' else normal,expected_stderr='')]
    if mode=='fault':steps.append(dict(name='watchdog-peer-reset-sensitivity',argv=['{exe}','--peer-reset-mutant'],
         expected_returncode=1,expected_stdout='',expected_stderr='R15_WATCHDOG_CONTEXT_STALL\n'))
    snapshot={n:sha(raw) for n,raw in files.items() if n.endswith('.sv')}
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',source_root='UNBOUND',output_parent='UNBOUND',
        sources={n:sha(raw) for n,raw in files.items()},
        build=dict(top='stream27_r15_watchdog_probe',sv_sources=[WATCH,SV],cpp_source=CPP,
                   parameters={},runtime_threads=1,cflags=['-std=c++17','-O2','-Werror=return-type','-DGFN16_RUNTIME_THREADS=1']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=steps,test_role='normal' if mode=='normal' else 'deliberate_fault',promotion_allowed=False,
        rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',candidate_id='s4-r15-watchdog-component-v1',
          source_snapshot=snapshot,candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
          rtl_ready_at_utc=READY),
        r15_watchdog_component=dict(contexts=2,limit=20480,production_watchdog_sha256=PINS[WATCH],
          old_trace_last_progress325_inferred=True,NTT_native_replay=False,whole_host_signal_qualification=False,
          host_GL_implemented=False,protected_fault_credit=False,lean_build_label='host GL assumed (unimplemented)',
          explicit_context_before_single_DUT=True,execution_policy='existing AzureFIT only',author_only=True))
    return manifest,files


def freeze(output,mode='normal'):
    out=Path(output).resolve();need(out.is_relative_to(ROOT) and not out.exists(),'R15_WATCHDOG_FRESH_OUTPUT')
    manifest,files=role(mode);source=out/'source/fpga';source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
    manifest['source_root']=str(source);dump(out/'manifest.json',manifest)
    return dict(id=IDS[mode],manifest=str(out/'manifest.json'),status='SOURCE_PREPARED_NOT_NATIVE')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--mode',choices=tuple(IDS),default='normal')
    args=p.parse_args();print(json.dumps(freeze(args.output,args.mode),indent=2))
