"""Additive lean geometry/calendar provenance; no forecast/RTL/header changes.

Only frame/window integer arithmetic runs locally. Original pilot remains
immutable; stale r84 geometry is explicitly descriptive, not authoritative.
"""
import argparse
import ast
import copy
from dataclasses import dataclass
import json
from pathlib import Path
import types

from . import stream27_context_lean_continuous as own

ROOT = own.ROOT
SOURCE = ROOT/'results/throughput-20260929/trackS-c2-lean-r7-ownlong-v1/continuous1000-source-v1'
BUNDLE = ROOT/'results/throughput-20260929/trackS-c2-lean-r7-native-v2/full-normal/production-bundle.json'
BUNDLE_PIN = '1972287a656f51660e87f14f64c47130f4f7364126bf10b1d9d6f34b5a028f96'
PORTS = 'lineage/reference/s4_two_context_model_v1.py'
PORTS_PIN = '3a3b4f9ad41219fea466de6fd2f32517bd2189d6e4c2235dda2197e97ee4d4f3'
ASSET = 'reference-assets/lean-full-production-bundle.json'
PROOF = 'reference-assets/lean-healthy-geometry-provenance.json'
need, sha, read, dump = own.need, own.sha, own.read, own.dump


def calendar(geometry, count):
    # Reuse only the pinned pure Frame/window functions, not model imports or
    # any arithmetic implementation in the much larger reference module.
    raw = (own.PILOT_DIR/'source/fpga'/PORTS).read_bytes()
    need(sha(raw) == PORTS_PIN, 'CAPTURED_FRAME_WINDOW_MODEL')
    selected = {'ModelError', 'need', 'Frame', 'disjoint', 'correction_calendar'}
    nodes = [node for node in ast.parse(raw.decode()).body
             if isinstance(node,(ast.ClassDef,ast.FunctionDef)) and node.name in selected]
    need({node.name for node in nodes} == selected, 'ONLY_PURE_FRAME_WINDOW_NODES')
    namespace = dict(dataclass=dataclass, __name__=__name__)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'[pinned pure frame windows]','exec'),namespace)
    ports = types.SimpleNamespace(**namespace)
    raw = (own.PILOT_DIR/'source/fpga'/own.pilot.VALIDATOR).read_bytes()
    need(sha(raw) == own.pilot.VALIDATOR_PIN, 'CAPTURED_CALENDAR_RECIPE')
    node = next(node for node in ast.parse(raw.decode()).body
                if isinstance(node,ast.FunctionDef) and node.name == 'calendar')
    need(isinstance(node.body[0],ast.ImportFrom) and node.body[0].module == 'fpga.reference' and
         len(node.body[0].names) == 1 and node.body[0].names[0].name == 's4_two_context_model_v1',
         'ONLY_REPLACE_KNOWN_PURE_MODEL_IMPORT')
    node.body = node.body[1:]
    namespace = dict(ports=ports,need=need,BASES=[604832956,999999937])
    exec(compile(ast.Module(body=[node],type_ignores=[]),'[pinned healthy calendar only]','exec'),namespace)
    return namespace['calendar'](geometry,count)


def prepare(output):
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(), 'FRESH_GEOMETRY_SUCCESSOR')
    manifest = read(SOURCE/'manifest.json')
    files = {name:(SOURCE/'source/fpga'/name).read_bytes() for name in manifest['sources']}
    need(all(sha(raw) == manifest['sources'][name] for name,raw in files.items()), 'FROZEN_FULLROLE_CLOSURE')
    raw_bundle = BUNDLE.read_bytes()
    need(sha(raw_bundle) == BUNDLE_PIN, 'EXACT_OWN_FULL_BUNDLE')
    bundle = json.loads(raw_bundle)
    geometry, generated = bundle['geometry'], bundle['generated_sha256']
    need(len(generated) == 55 and all(manifest['sources']['rtl/'+name] == pin
         for name,pin in generated.items()), 'OWN55_BUNDLE_ACTUAL_MODEL_JOIN')
    need(geometry['boundary_inputreg'] == 1 and geometry['correction_cache_latency'] == 78 and
         (geometry['term_seed_first'],geometry['term_seed_last']) == (71,74), 'SOURCE_BOUND_BOUNDARY_CALENDAR')
    proof = dict(label=own.pilot.LABEL, scope='Source-only healthy frame/window model, not new numerical/native evidence.',
        own_full_bundle=dict(path=str(BUNDLE),sha256=BUNDLE_PIN,closure_path=ASSET),
        production_generated_sha256=generated, geometry=geometry,
        captured_scalar_models=dict(frame_window_source_sha256=PORTS_PIN,
                                   calendar_recipe_source_sha256=own.pilot.VALIDATOR_PIN),
        healthy_calendars={str(count):calendar(geometry,count) for count in (100,1000)},
        immutable_pilot_r84_geometry_role='Descriptive old provenance only; not authoritative lean source/calendar.',
        host_gl_implemented=False, arithmetic_locally_executed=False, promotion_allowed=False)
    files[ASSET] = raw_bundle
    files[PROOF] = (json.dumps(proof,indent=2)+'\n').encode()
    manifest = copy.deepcopy(manifest)
    manifest['lean_production']['geometry'] = geometry
    manifest['lean_production']['geometry_provenance'] = dict(source=PROOF,sha256=sha(files[PROOF]),
        own_full_bundle_sha256=BUNDLE_PIN,own_full_bundle_asset=ASSET,
        original_r84_geometry_not_authoritative=True,original_pilot_unchanged=True)
    manifest['lean_production']['healthy_calendars'] = proof['healthy_calendars']
    manifest['sources'] = {name:sha(raw) for name,raw in files.items()}
    source = out/'source/fpga'
    source.mkdir(parents=True)
    for name,raw in files.items():
        path=source/name
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    manifest['source_root']=str(source)
    dump(out/'manifest.json',manifest)
    # Forecast source+bytes remain exact; no new duration calculation.
    with (out/'forecast.json').open('xb') as stream:
        stream.write((SOURCE/'forecast.json').read_bytes())
    return dict(manifest=str(out/'manifest.json'),forecast=str(out/'forecast.json'),
        geometry_proof_sha256=sha(files[PROOF]),own_bundle_sha256=BUNDLE_PIN,
        label=own.pilot.LABEL,status='ADDITIVE_SOURCE_METADATA_NOT_NATIVE')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.output),indent=2))
