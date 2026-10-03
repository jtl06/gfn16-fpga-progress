"""Own private lean-R9 normal-first from immutable qualified R9 captures."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .stream27_context_lean_native import sha, need, dump, once

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_context_lean_r9_native.py'
BINDER = 'reference/stream27_context_lean_r9_bind.py'
OUTPUT = 'reference/stream27_context_lean_r9_output.py'
BASE = ROOT/'results/throughput-20260929/trackS-c2-storage-combo-registerederror-native-v1'
DONORS = {'aw8': '42982023a665231b36f15aab6d51bae70e4ea1b023b793ec2cc5540dfc2a442a',
          'full': '92e4c5d3df79b3161595a372697f93defdbf7a8dcd9a2131a47ee10e57e8bc08'}
IDS = {stage: 's4-p16-c2-lean-r9-'+stage+'-normal-q1-v1' for stage in DONORS}
READY = '2026-10-02T18:02:16Z'
LABEL = 'lean build; host GL assumed (unimplemented)'


def role(stage):
    from . import stream27_context_lean_r9_bind as lean
    need(stage in DONORS, 'R9_AW8_FULL_ONLY')
    directory = BASE/(stage+'-normal')
    raw = (directory/'manifest.json').read_bytes()
    need(sha(raw) == DONORS[stage], 'EXACT_CAPTURED_R9_MANIFEST')
    manifest = json.loads(raw)
    probe = manifest['probe']
    parameters = dict(manifest['build']['parameters'])
    files = {}
    for name, digest in manifest['sources'].items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'PATH')
        data = (directory/'source/fpga'/name).read_bytes()
        need(sha(data) == digest, 'R9_SOURCE:'+name)
        files[name] = data
    parent = lean.capture(256 if stage == 'aw8' else 65536)
    need(all(files['rtl/'+name] == text.encode() for name, text in parent['files'].items()),
         'EXACT_R9_PRODUCTION55')
    production = lean.bind(parent, enabled=1)
    oldtop, newtop = parent['top'], production['top']
    for name in parent['files']:
        files.pop('rtl/'+name)
    files.update({'rtl/'+name: text.encode() for name, text in production['files'].items()})
    sv = ['rtl/'+name for name in production['rtl_sources']]
    if stage == 'aw8':
        header = 'rtl/tb/s4_host_contexts_config_v1.h'
        text = files[header].decode()
        need(text.count(oldtop) == 2, 'ONLY_HEADER_IDENTIFIER')
        files[header] = text.replace(oldtop, newtop).encode()
        manifest['build']['top'] = newtop
        manifest['steps'][0]['expected_stdout'] = LABEL+'\n'+manifest['steps'][0]['expected_stdout']
    else:
        observer = manifest['build']['top']
        text = files['rtl/'+observer+'.sv'].decode()
        text, count = re.subn(r'\b'+re.escape(oldtop)+r'\b', newtop, text)
        need(count == 1 and not re.search(r'\b(always|always_ff|always_comb|initial)\b', text),
             'STATE_FREE_R9_OBSERVER')
        text = once(text, 'CONTEXTS=2,', 'CONTEXTS=2,LEAN_PRODUCTION=1,')
        text = once(text, '.CONTEXTS(CONTEXTS),', '.CONTEXTS(CONTEXTS),\n  .LEAN_PRODUCTION(LEAN_PRODUCTION),')
        files['rtl/'+observer+'.sv'] = text.encode()
        sv.append('rtl/'+observer+'.sv')
        validator = manifest['steps'][0]['validator']
        parent_config, parent_source = validator['config'], validator['source']
        validator.update(source=OUTPUT, function='validate', assets={},
            config=dict(parent_config=parent_config, parent_source_sha256=sha(files[parent_source])))
        files[OUTPUT] = (ROOT/OUTPUT).read_bytes()
    cppname = manifest['build']['cpp_source']
    text = files[cppname].decode()
    marker = 'return gfn16_runtime::probe(context,d);'
    files[cppname] = once(text, marker, marker+'std::cout<<"'+LABEL+'\\n";').encode()
    manifest['build']['sv_sources'] = sv
    manifest['build']['parameters']['LEAN_PRODUCTION'] = 1
    ancestry = {key: manifest.pop(key) for key in list(manifest)
                if key.startswith('context_storage_combo') or key == 'context_registered_error'}
    for key in ('host_contexts', 'r84_explicit_small'):
        if key in manifest:
            manifest[key]['generated_sha256'] = production['generated_sha256']
    if 'r84' in manifest:
        manifest['r84']['production_generated_sha256'] = production['generated_sha256']
        manifest['r84']['native_observer'].update(production_top=newtop,
            production_root_sha256=production['generated_sha256'][newtop+'.sv'])
    for name, digest in production['source_sha256'].items():
        data = (ROOT/name).read_bytes()
        need(sha(data) == digest, 'R9_LEAN_SOURCE_FREEZE')
        files['lineage/'+name] = data
    files['lineage/'+SELF] = (ROOT/SELF).read_bytes()
    files['lineage/reference/stream27_context_lean_native.py'] = (ROOT/'reference/stream27_context_lean_native.py').read_bytes()
    manifest['sources'] = {name: sha(data) for name, data in files.items()}
    snapshot = {name: pin for name, pin in manifest['sources'].items() if name.endswith('.sv')}
    manifest.update(source_root='UNBOUND', output_parent='UNBOUND', test_role='normal',
        rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1', candidate_id=IDS[stage].removesuffix('-q1-v1'),
            source_snapshot=snapshot, candidate_source_sha256=sha(json.dumps(snapshot, sort_keys=True, separators=(',', ':')).encode()),
            rtl_ready_at_utc=READY))
    manifest['lean_production'] = dict(label=LABEL, contract=production['lean_production'],
        production_top=newtop, production_generated_sha256=production['generated_sha256'],
        protected_twin_manifest_sha256=DONORS[stage], protected_twin_source_provenance=ancestry,
        numerical_inputs_reference_oracle_and_assertions_unchanged=True,
        cpp_only_added_nonprobe_label=True, observer_only_root_and_parameter_binding=True,
        r9_safety_and_publication_preserved=True, no_R7_lean_native_inheritance=True,
        host_gl_implemented=False, rollback_implemented=False, fault_immunity_inherited=False,
        native_qualified=False, promotion_allowed=False)
    need(manifest['probe'] == probe and manifest['build']['parameters'] ==
         dict(parameters, LEAN_PRODUCTION=1), 'EXACT_RUNTIME_PARAMETER_DELTA')
    return manifest, files, production


def prepare(output, stage):
    from fpga.tools import candidate_ladder, native_class_package_v2 as package
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists(), 'FRESH_OUTPUT')
    need(not any((ROOT/p).exists() for p in ('queue/PAUSE', 'docs/briefs/PAUSE')), 'PAUSE')
    manifest, files, production = role(stage)
    source = out/'source/fpga'
    source.mkdir(parents=True)
    for name, raw in files.items():
        path = source/name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    manifest['source_root'] = str(source)
    dump(out/'manifest.json', manifest)
    dump(out/'production-bundle.json', production)
    dump(out/'host-hours.json', candidate_ladder.budget_from_hourly())
    variants = []
    for pair in ('01', '23'):
        profile = 'gcp-c4d-static'+pair+'-v1'
        worker = 's4-p16-c2-lean-r9-'+stage+'-'+pair+'-v1'
        packet = out/('packet-'+pair)
        result = package.prepare(out/'manifest.json', source, profile, worker, 'run', packet, out/'host-hours.json')
        ticket = json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'), sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'], manifest_sha256=sha((packet/'manifest.json').read_bytes()),
            worker_id=worker, profile=profile, native_root=ticket['native_root'], runner='tools/native_class_package_v2.py',
            runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'), stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/name), sha256=sha((ROOT/name).read_bytes()))
                for name in ('tools/native_package_v3.py', 'tools/native_package_v2.py')], max_seconds=3700))
    logical = dict(schema='gfn16-global-ticket-v1', id=IDS[stage], owner='independent-review',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), priority='P1', kind='sim',
        needs='verilator', tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        allowed_hosts=['gfn16-pilot-c4d', 'aethia'], resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4),
        minimum_ram_gib=4 if stage == 'aw8' else 8,
        minimum_ram_rationale=LABEL+'; own AW8 small4/full8 bounded trial, no ancestor resource/clock claim.',
        est_minutes=25, promotion_bound=False, test_role='normal', rtl_readiness=manifest['rtl_readiness'], packages=variants)
    if stage == 'full':
        logical.update(after=[IDS['aw8']], on='PASS_expected_contracts')
    dump(out/'global-ticket.json', logical)
    return dict(id=IDS[stage], ticket=str(out/'global-ticket.json'), label=LABEL,
                production_rtl=55, compiled_rtl=len(manifest['build']['sv_sources']), status='PREPARED_NOT_NATIVE')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stage', choices=('aw8', 'full'), required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.stage), indent=2))
