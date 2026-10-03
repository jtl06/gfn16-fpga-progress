"""Private R7 lean own native normal-first: healthy reference identity, not fault inheritance."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_context_lean_native.py'
BINDER = 'reference/stream27_context_lean_bind.py'
OUTPUT = 'reference/stream27_context_lean_output.py'
LABEL = 'lean build; host GL assumed (unimplemented)'
BASE = ROOT/'results/throughput-20260929/trackS-c2-storage-combo-faultlocal-native-v1'
DONORS = {'aw8': '80063877960064da299a3aeb9b5204b2f4244c6fbddfdea95d57be6b725ad8b9',
          'full': '08ed54df8c3336b56d0c1c391e84e016c9d99b792f906635e89b0c5ff90bcdb3'}
IDS = {s: 's4-p16-c2-lean-r7-'+s+'-normal-q1-v2' for s in DONORS}
READY = '2026-10-02T17:41:00Z'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def need(ok, why):
    if not ok:
        raise ValueError('C2_LEAN_NATIVE_'+why)


def once(text, before, after):
    need(text.count(before) == 1, 'UNIQUE_ANCHOR')
    return text.replace(before, after, 1)


def dump(path, value):
    with Path(path).open('x') as out:
        json.dump(value, out, indent=2)
        out.write('\n')


def role(stage):
    from fpga.reference import stream27_context_lean_bind as lean
    need(stage in DONORS, 'AW8_FULL_ONLY')
    directory = BASE/(stage+'-normal')
    raw = (directory/'manifest.json').read_bytes()
    need(sha(raw) == DONORS[stage], 'EXACT_CAPTURED_TWIN_MANIFEST')
    manifest = json.loads(raw)
    before = copy.deepcopy(manifest)
    files = {}
    for name, digest in manifest['sources'].items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'PATH')
        b = (directory/'source/fpga'/name).read_bytes()
        need(sha(b) == digest, 'CAPTURED_SOURCE:'+name)
        files[name] = b
    parent = lean.capture(256 if stage == 'aw8' else 65536)
    need(all(files['rtl/'+n] == text.encode() for n, text in parent['files'].items()), 'TWIN_PRODUCTION55')
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
        need(count == 1 and not re.search(r'\b(always|always_ff|always_comb|initial)\b', text), 'STATELESS_OBSERVER')
        text = once(text, 'CONTEXTS=2,', 'CONTEXTS=2,LEAN_PRODUCTION=1,')
        text = once(text, '.CONTEXTS(CONTEXTS),', '.CONTEXTS(CONTEXTS),\n  .LEAN_PRODUCTION(LEAN_PRODUCTION),')
        files['rtl/'+observer+'.sv'] = text.encode()
        sv.append('rtl/'+observer+'.sv')
        v = manifest['steps'][0]['validator']
        parent_config = copy.deepcopy(v['config'])
        parent_validator = v['source']
        v.update(source=OUTPUT, function='validate', config=dict(parent_config=parent_config,
                 parent_source_sha256=sha(files[parent_validator])), assets={})
        files[OUTPUT] = (ROOT/OUTPUT).read_bytes()
    cppname = manifest['build']['cpp_source']
    cpp = files[cppname].decode()
    marker = 'return gfn16_runtime::probe(context,d);'
    cpp = once(cpp, marker, marker+'std::cout<<"'+LABEL+'\\n";')
    files[cppname] = cpp.encode()
    manifest['build']['sv_sources'] = sv
    manifest['build']['parameters']['LEAN_PRODUCTION'] = 1
    # Old flags describe the protected source ancestry, never lean safety.
    provenance = {k: manifest.pop(k) for k in list(manifest) if k.startswith('context_storage_combo')}
    for key in ('host_contexts', 'r84_explicit_small'):
        if key in manifest:
            manifest[key]['generated_sha256'] = production['generated_sha256']
    if 'r84' in manifest:
        manifest['r84']['production_generated_sha256'] = production['generated_sha256']
        manifest['r84']['native_observer'].update(production_top=newtop,
            production_root_sha256=production['generated_sha256'][newtop+'.sv'])
    for name, digest in production['source_sha256'].items():
        b = (ROOT/name).read_bytes()
        need(sha(b) == digest, 'SOURCE_FREEZE')
        files['lineage/'+name] = b
    files['lineage/'+SELF] = (ROOT/SELF).read_bytes()
    manifest['sources'] = {name: sha(b) for name, b in files.items()}
    snapshot = {name: pin for name, pin in manifest['sources'].items() if name.endswith('.sv')}
    manifest.update(source_root='UNBOUND', output_parent='UNBOUND', test_role='normal',
        rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1', candidate_id=IDS[stage].removesuffix('-q1-v2'),
            source_snapshot=snapshot, candidate_source_sha256=sha(json.dumps(snapshot, sort_keys=True, separators=(',', ':')).encode()),
            rtl_ready_at_utc=READY))
    manifest['lean_production'] = dict(label=LABEL, contract=production['lean_production'],
        production_top=newtop, production_generated_sha256=production['generated_sha256'],
        protected_twin_manifest_sha256=DONORS[stage], protected_twin_source_provenance=provenance,
        numerical_inputs_reference_oracle_and_assertions_unchanged=True,
        cpp_only_added_nonprobe_label=True, observer_only_root_and_parameter_binding=True,
        host_gl_implemented=False, rollback_implemented=False, fault_immunity_inherited=False,
        native_qualified=False, promotion_allowed=False)
    need(manifest['probe'] == before['probe'] and manifest['build']['parameters'] ==
         dict(before['build']['parameters'], LEAN_PRODUCTION=1), 'EXACT_RUNTIME_AND_PARAMETER_DELTA')
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
        p = source/name
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('xb') as stream:
            stream.write(raw)
    manifest['source_root'] = str(source)
    dump(out/'manifest.json', manifest)
    dump(out/'production-bundle.json', production)
    dump(out/'host-hours.json', candidate_ladder.budget_from_hourly())
    variants = []
    for pair in ('01', '23'):
        profile = 'gcp-c4d-static'+pair+'-v1'
        worker = 's4-p16-c2-lean-r7-'+stage+'-'+pair+'-v2'
        packet = out/('packet-'+pair)
        result = package.prepare(out/'manifest.json', source, profile, worker, 'run', packet, out/'host-hours.json')
        ticket = json.loads((packet/'ticket.json').read_text())
        variants.append(dict(archive=str(packet/'package.tar.gz'), sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'], manifest_sha256=sha((packet/'manifest.json').read_bytes()),
            worker_id=worker, profile=profile, native_root=ticket['native_root'], runner='tools/native_class_package_v2.py',
            runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'), stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/p), sha256=sha((ROOT/p).read_bytes()))
                for p in ('tools/native_package_v3.py', 'tools/native_package_v2.py')], max_seconds=3700))
    logical = dict(schema='gfn16-global-ticket-v1', id=IDS[stage], owner='independent-review',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), priority='P1', kind='sim', needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1', allowed_hosts=['gfn16-pilot-c4d', 'aethia'],
        resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4), minimum_ram_gib=4 if stage == 'aw8' else 8,
        minimum_ram_rationale='Own lean exploratory small4GiB/full8GiB; no twin numerical/runtime/clock inheritance.',
        est_minutes=25, promotion_bound=False, test_role='normal', rtl_readiness=manifest['rtl_readiness'], packages=variants)
    if stage == 'full':
        logical.update(after=[IDS['aw8']], on='PASS_expected_contracts')
    dump(out/'global-ticket.json', logical)
    return dict(id=IDS[stage], ticket=str(out/'global-ticket.json'), production_rtl=55,
                compiled_rtl=len(sv) if (sv := manifest['build']['sv_sources']) else 0,
                status='PREPARED_NOT_NATIVE', label=LABEL)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--stage', choices=('aw8', 'full'), required=True)
    args = p.parse_args()
    print(json.dumps(prepare(args.output, args.stage), indent=2))
