"""Fresh FIELD100-specific native normal roles for the private R15 D16 cut.

Captured C++/oracle/observer/calendar bytes are unchanged. This is source
binding, not inherited numerical qualification or a new runner framework.
"""
import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path

from fpga.reference import stream27_r15_storage_ram_bind as binder

ROOT = binder.ROOT
SELF = 'reference/stream27_r15_storage_ram_native.py'
BASE = ROOT / 'results/throughput-20260929/trackS-c2-protected-field100-native-v1'
CAPTURES = {
    'aw8': ('aw8-normal', 'a396059b51146bb5daffd13cd4f5403f146805293651fa81f41510dcaa1970e0',
            'dd8d9196a5ac79381b8e701d021d19a067dde4d319b15799b13f8d8f61441a00'),
    'full': ('full-normal-v2', '51ef1347d976d852f0488d29b575c112329a1e43560b6ee94d53fdc924d4de6e',
             'f5f0617d989b64bb965b612a0d0cb8b6074c1ecd4f85f01ed66f970dfbf521f2')}
IDS = {stage: 's4-p16-r15-storage-crt-'+stage+'-normal-q1-v2' for stage in CAPTURES}


def need(ok, why):
    if not ok:
        raise ValueError('R15_STORAGE_NATIVE_'+why)


def role(stage):
    need(stage in CAPTURES, 'AW8_FULL_ONLY')
    name, manifest_pin, production_pin = CAPTURES[stage]
    directory = BASE / name
    mr, br = (directory/'manifest.json').read_bytes(), (directory/'production-bundle.json').read_bytes()
    need((binder.sha(mr), binder.sha(br)) == (manifest_pin, production_pin), 'EXACT_FROZEN_FIELD100')
    manifest, parent = json.loads(mr), json.loads(br)
    before = copy.deepcopy(manifest)
    files = {}
    for name, pin in manifest['sources'].items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'SOURCE_PATH')
        raw = (directory/'source/fpga'/name).read_bytes()
        need(binder.sha(raw) == pin, 'CAPTURE_PIN:'+name)
        files[name] = raw
    need(all(files['rtl/'+n] == t.encode() for n,t in parent['files'].items()), 'EXACT_PRODUCTION58')
    production = binder.bind(parent, storage_to_ram=1)
    for name, text in production['files'].items():
        files['rtl/'+name] = text.encode()
    manifest['build']['sv_sources'] = ['rtl/'+n for n in production['rtl_sources']]
    if stage == 'full':
        observer = 'rtl/'+manifest['build']['top']+'.sv'
        need(observer in files and files[observer] == (directory/'source/fpga'/observer).read_bytes(),
             'UNCHANGED_TRANSPARENT_OBSERVER')
        manifest['build']['sv_sources'].append(observer)
    for name in (binder.SELF, SELF, 'reference/stream27_r15_storage_ram_model.py'):
        files[name] = (ROOT/name).read_bytes()
    snapshot = {n:binder.sha(raw) for n,raw in files.items() if n.endswith('.sv')}
    ready = datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    manifest.update(source_root='UNBOUND', output_parent='UNBOUND', test_role='normal',
        sources={n:binder.sha(raw) for n,raw in files.items()},
        rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1',
            candidate_id=IDS[stage].removesuffix('-q1-v2'), source_snapshot=snapshot,
            candidate_source_sha256=binder.sha(json.dumps(snapshot,sort_keys=True,separators=(',',':'))),
            rtl_ready_at_utc=ready))
    for meta in manifest.values():
        if isinstance(meta, dict) and 'production_generated_sha256' in meta:
            meta['production_generated_sha256'] = production['generated_sha256']
    if stage == 'aw8':
        for key in ('r84_explicit_small', 'host_contexts'):
            manifest[key]['generated_sha256'] = production['generated_sha256']
    else:
        manifest['r84']['production_generated_sha256'] = production['generated_sha256']
    manifest['r15_storage_ram'] = dict(contract=production['r15_storage_ram'],
        production_top=production['top'], production_generated_sha256=production['generated_sha256'],
        source_sha256=production['source_sha256'], geometry=production['geometry'],
        donor_manifest_sha256=manifest_pin, donor_bundle_sha256=production_pin,
        frozen_cpp_reference_steps_observer_params_unchanged=True,
        source_specific_native_required=True, ancestor_result_not_inherited=True,
        model_full_N_locally_performed=False, promotion_allowed=False)
    need(manifest['steps'] == before['steps'] and manifest['probe'] == before['probe'] and
         manifest['build']['parameters'] == before['build']['parameters'] and
         files[before['build']['cpp_source']] == (directory/'source/fpga'/before['build']['cpp_source']).read_bytes(),
         'UNCHANGED_INDEPENDENT_NUMERIC_CALENDAR')
    need(len(production['files']) == 59 and
         len(manifest['build']['sv_sources']) == (59 if stage=='aw8' else 60), 'COMPILED_CLOSURE')
    return manifest, files, production


def dump(path, value):
    with Path(path).open('x') as out:
        json.dump(value,out,indent=2)
        out.write('\n')


def emit(output, stage):
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(), 'FRESH_PRIVATE_OUTPUT')
    manifest, files, production = role(stage)
    source = out/'source/fpga'
    source.mkdir(parents=True)
    for name, raw in files.items():
        target = source/name
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    manifest['source_root'] = str(source)
    dump(out/'manifest.json',manifest)
    dump(out/'production-bundle.json',production)
    return dict(id=IDS[stage], manifest=str(out/'manifest.json'), source_root=str(source),
                production=59, compiled_rtl=len(manifest['build']['sv_sources']),
                status='SOURCE_READY_NOT_PACKAGED_NOT_NATIVE')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--stage', choices=tuple(CAPTURES), required=True)
    args = p.parse_args()
    print(json.dumps(emit(args.output,args.stage),indent=2))
