"""Prepare immutable S4 AW8 source inputs; no native execution on the Mac."""
import hashlib
import json
from pathlib import Path
import shutil

from .stream27_shared_field_v1 import ROOT,prepare as compile_field


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(destination):
    destination=Path(destination).resolve()
    if destination.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('S4_FRESH_PAUSE')
    b=compile_field(256,16,0);source=destination/'inputs/fpga';source.mkdir(parents=True)
    for name,text in b['files'].items():
        path=source/'rtl'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    bench='rtl/tb/stream27_shared_warm_aw8_v1.cpp'
    path=source/bench;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/bench,path)
    for name in b['source_dependencies']+['reference/stream27_shared_warm_native_v1.py']:
        target=source/'lineage'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    sources={str(path.relative_to(source)):sha(path) for path in sorted(source.rglob('*')) if path.is_file()}
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='UNBOUND_NO_DISPATCH',
        source_root=str(source),output_parent=str(destination/'UNBOUND_OUTPUT'),sources=sources,
        build=dict(top=b['top'],sv_sources=['rtl/'+name for name in b['rtl_sources']],cpp_source=bench,
            parameters=dict(AW=8,P=16,CONTEXTS=1),cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='s4-aw8-real-warm-field',argv=['{exe}'],expected_returncode=0,
            expected_stdout='S4_SHARED_AW8_PASS cases=9 frames=9 physical_rows=144 physical_words=2304 eligible_rows=112 commits=112 peak_owners=2\n',
            expected_stderr='')],lint_baseline_policy='Fresh r38 class-gated lint; no defect or unknown-warning waiver.')
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    receipt=dict(status='prepared_unbound_not_executed',manifest_sha256=sha(destination/'manifest.json'),
        source_count=len(sources),build=manifest['build'],geometry=b['geometry'],source_sha256=b['source_sha256'],
        generated_sha256=b['generated_sha256'],full_N_numeric_NTT_performed=False,native_run_performed=False,
        gate_scope='real merged field + unsigned digits + nonzero signed c0/c1 + segmented terms + overlap + lease/cycle/controller checks',
        promotion='Independent replay/advisor verification still required; no whole-core CRT/carry or physical claim.')
    (destination/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    import sys
    if len(sys.argv)!=2:raise ValueError('usage: python -B -m fpga.reference.stream27_shared_warm_native_v1 NEW_OUTPUT')
    print(json.dumps(prepare(sys.argv[1]),indent=2))
