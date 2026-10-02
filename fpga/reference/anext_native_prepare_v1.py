"""Source-only closed A-next whole AW5/AW8 roles for the shared native runner."""
import json
from pathlib import Path
import shutil
import hashlib
from fpga.reference.anext_core_source_v1 import verify
from fpga.reference.anext_a10_block_engine_source_v1 import verify as block_verify,PARENT as BLOCK_PARENT
from fpga.reference.track_a4_core_vectors_v1 import corpus

ROOT=Path(__file__).resolve().parents[1]
EXTRA=[
 'reference/anext_core_source_v1.py','reference/anext_composition_contract_v1.py',
 'reference/anext_small_model_v1.py','reference/anext_native_output_v1.py','reference/anext_native_prepare_v1.py',
 'reference/anext_a10_block_engine_source_v1.py',
 'tests/test_anext_core_source_v1.py','tests/test_anext_composition_contract_v1.py',
 'tests/test_anext_native_output_v1.py','tests/test_anext_a10_block_engine_source_v1.py',
 'rtl/kernel/genefer_anext_a10_block_engine_v1.sv',
 'rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1.sv',
 'docs/briefs/2026-10-01-advisor-verification-T5b.md',
 'docs/briefs/replies/2026-10-01-A-next-composition-contract-v1.md',
 'results/throughput-20260929/core27-t5b-provisional64-aws-fit-v1/manifest.json',BLOCK_PARENT]


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(output,aw):
    if aw not in (5,8):raise ValueError('ANEXT_SMALL_NATIVE_GEOMETRY')
    output=Path(output).resolve()
    if output.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('fresh output/no PAUSE required')
    generated=verify();block_verify()
    a4dir=ROOT/'artifacts/track-a4b-normal-aw5-role-v1'
    a10dir=ROOT/f'results/throughput-20260929/a10-batch-v1/aw{aw}-f{2 if aw==5 else 0}/input'
    a4=json.loads((a4dir/'manifest.json').read_text());a10=json.loads((a10dir/'manifest.json').read_text())
    files={}
    for directory,manifest in ((a4dir,a4),(a10dir,a10)):
        for name,pin in manifest['sources'].items():
            source=directory/'source/fpga'/name
            if digest(source)!=pin:raise ValueError('frozen ancestor drift '+name)
            if name in files and files[name][1]!=pin:raise ValueError('conflicting ancestor bytes '+name)
            files[name]=(source,pin)
    for name in [*EXTRA,*generated]:files[name]=(ROOT/name,digest(ROOT/name))
    source=output/'source/fpga';source.mkdir(parents=True)
    for name,(path,pin) in files.items():
        dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
        if digest(dest)!=pin:raise ValueError('snapshot copy drift')
    vectors,meta=corpus(aw);vector=f'vectors/anext-aw{aw}.txt'
    (source/'vectors').mkdir(exist_ok=True);(source/vector).write_text(vectors)
    pins={name:pin for name,(_,pin) in files.items()};pins[vector]=meta['sha256']
    omit={
      'genefer_root_profile27_r2_rom.sv',
      'genefer_ntt_banked27_prefetch_r2_orient8_rootfused_blockroute_v2_engine.sv',
      'genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rootfused_blockroute_v2_engine.sv',
      'genefer_track_a4_ntt_sequencer_v1.sv','genefer_track_a4_square_backend_v4.sv','genefer_track_a4_core_v4.sv'}
    compiled=[name for name in a4['build']['sv_sources'] if Path(name).name not in omit]
    compiled += ['rtl/kernel/genefer_a10_profile3_v1.sv','rtl/kernel/genefer_a10_canonical_butterfly_v1.sv',
        f'rtl/kernel/a10_packed_lookup_aw{aw}_lint_bound_v2.sv','rtl/kernel/genefer_anext_a10_block_engine_v1.sv',
        'rtl/kernel/genefer_anext_ntt_sequencer_v1.sv','rtl/kernel/genefer_anext_square_backend_v1.sv','rtl/kernel/genefer_anext_core_v1.sv']
    if len(compiled)!=len(set(compiled)) or not set(compiled)<=set(pins):raise ValueError('compiled closure')
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='aethia',
      source_root=f'/home/jtl/gfn-fpga-lab/agent-work/anext-aw{aw}/source/fpga',
      output_parent=f'/home/jtl/gfn-fpga-lab/agent-work/anext-aw{aw}/output',sources=pins,
      build=dict(top='genefer_anext_core_v1',sv_sources=compiled,cpp_source='rtl/tb/track_anext_core_v1.cpp',parameters={'AW':aw},
                 cflags=['-std=c++17','-Werror=return-type',f'-DA4_CORE_AW={aw}']),
      probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
      steps=[dict(name=f'anext-normal-aw{aw}',argv=['{exe}','{root}/'+vector],expected_returncode=0,expected_stderr='',
        validator=dict(source='reference/anext_native_output_v1.py',function='validate',config=dict(mode='normal',aw=aw),assets={'vectors':vector}))])
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    result=dict(status='source_prepared_not_executed',aw=aw,manifest_sha256=digest(output/'manifest.json'),sources=len(pins),compiled_sv=len(compiled),
      new_top='genefer_anext_core_v1',adapter_native_gate_required=True,promotion_allowed=False)
    (output/'preparation.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--aw',type=int,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.output,a.aw),indent=2))
