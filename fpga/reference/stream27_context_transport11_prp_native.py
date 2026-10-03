"""Own captured R11 N256 healthy PRPs; lean build, host GL unimplemented.

Graph-only binding of immutable production, frozen small oracle and CPP. No
generator call, full-N arithmetic, ancestor PASS/clock or protection inheritance.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_context_transport11_prp_native.py'
CPP = 'rtl/tb/stream27_context_lean_prp.cpp'
HEADER = 'rtl/tb/stream27_context_lean_prp_config.h'
ASSET = 'reference-assets/r10-healthy-prp-n256.json'
CAPTURE = ROOT/'results/throughput-20260929/trackS-c2-storage-combo-transport11-native-v1/aw8-normal-v2'
CAPTURE_MANIFEST = 'd0a7ee42e8a9560b64abf13218e680dd8f0bb17e59f82184ff74fbd63de46c72'
CAPTURE_BUNDLE = 'b05eb490e37b4cc8944557d1b8188334ab8eca2d34f2bf4ea3f3eb7acdd22dbc'
RECIPE = ROOT/'results/throughput-20260929/trackS-c2-lean-warmprogress-native-v1/prp-normal-v2'
RECIPE_MANIFEST = '8e782fba3fdf145b0c0783e5b5f47fc647b03c85074add1a453e4896e5249508'
RECIPE_BUNDLE = '81f51a89d05cb9be0732ad8f828fab218e4a0d4a0ba0777d6a818f341a1419da'
CPP_PIN = '04e2025323cd23860e4d677af229137a6ac66a7ca5039b7bb2046e61d83d4e70'
ORACLE_PIN = 'b9956fff4658b8af2e778a796cbff8526c5fec951844c0fe15933793d8caf95f'
HEADER_PIN = 'b4661a0c7578bc372824642f763a47d3952324b5ad00f0d59ba1c9c0c4dcf2d3'
N, P, INTERVAL, CARRY_DONE = 256, 16, 217, 217
FIRST = (204, 312)
BASES = (599, 600, 7552, 768, 989233152, 999999998, 999999999, 1000000000)
LABEL = 'lean build; host GL assumed (unimplemented)'
READY = '2026-10-02T20:43:00Z'
NORMAL_ID = 's4-p16-c2-r11-prp-normal-q1-v1'
NORMAL_GATE = 's4-p16-c2-combo-r11-aw8-normal-q1-v1'


def need(ok, reason):
    if not ok:
        raise ValueError('R11_PRP_'+reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def validate(stdout, stderr, rc, config, assets):
    """Standalone stdlib validator; does not load builders or compute an oracle."""
    need(set(config) == {'family', 'mode', 'oracle_sha256'} and config['family'] == 'R11' and
         config['mode'] in ('normal', 'negative-comparator', 'negative-schedule') and
         config['oracle_sha256'] == ORACLE_PIN, 'CONFIG')
    need(set(assets) == {'oracle'} and sha(assets['oracle'].encode()) == ORACLE_PIN, 'FROZEN_SMALL_ORACLE')
    oracle = json.loads(assets['oracle'])
    need(oracle['schema'] == 'gfn16-r10-healthy-prp-n256-v1' and oracle['n'] == N and oracle['p'] == P and
         [row['base'] for row in oracle['cases']] == list(BASES), 'ORACLE_DOMAIN')
    mode = config['mode']
    if mode != 'normal':
        need(type(rc) is int and rc == 1 and stdout == LABEL+'\n' and
             stderr == 'A_PRP_RESIDUE_MISMATCH case=0 digit=0\n', 'TYPED_HOST_CONTROL')
        return dict(status='PASS_expected_contracts', family='R11', mode=mode, build_label=LABEL,
                    scope='Own finite host comparator/schedule sensitivity; not hardware protection.', promotion_allowed=False)
    need(type(rc) is int and rc == 0 and stderr == '' and stdout.endswith('\n'), 'NORMAL_EXIT')
    lines = stdout.splitlines()
    need(len(lines) == 12 and lines[0] == LABEL, 'LABELED_EXTENT')
    rows = []
    for index, line in enumerate(lines[1:11]):
        need(line.startswith('A_CONTEXT_PRP_RESULT '), 'ROW_GRAMMAR')
        row = json.loads(line.removeprefix('A_CONTEXT_PRP_RESULT '))
        need(set(row) == {'case', 'base', 'steps', 'doubles', 'done_edge', 'sentinel', 'digits'}, 'ROW_KEYS')
        wanted = oracle['cases'][index] if index < 8 else dict(base=BASES[index-8], steps=1, doubles=0,
            expected_digits=oracle['sentinel']['expected_digits'])
        for key, expected in (('case', index), ('base', wanted['base']), ('steps', wanted['steps']), ('doubles', wanted['doubles'])):
            need(type(row[key]) is int and row[key] == expected, 'FULL_EXPONENT_OR_SENTINEL_IDENTITY')
        need(row['sentinel'] is (index >= 8), 'SENTINEL_IDENTITY')
        need(row['digits'] == wanted['expected_digits'] and len(row['digits']) == N and
             all(type(v) is int for v in row['digits']), 'ALL_SIGNED96_DIGITS')
        counts = [c['steps'] for c in oracle['cases'][index-index%2:index-index%2+2]] if index < 8 else [1, 1]
        need(type(row['done_edge']) is int and FIRST[index%2]+(wanted['steps']-1)*INTERVAL+CARRY_DONE <
             row['done_edge'] < max(counts)*INTERVAL+33*N+10000, 'OWN_FINITE_PUBLICATION_CALENDAR')
        rows.append(row)
    squares, doubles = sum(r['steps'] for r in rows), sum(r['doubles'] for r in rows)
    need((squares, doubles) == (41091, 15137) and lines[-1] ==
         f'A_CONTEXT_PRP_PASS cases=8 sentinel_cases=2 squares={squares} doubles={doubles} signed96_words=2560 interval=217',
         'COMPLETE_FOOTER')
    return dict(status='PASS_expected_contracts', family='R11', build_label=LABEL, cases=8, sentinel_cases=2,
        squares=squares, doubles=doubles, signed96_words=2560, interval=217, host_gl_implemented=False,
        rollback_implemented=False, protected_fault_immunity_inherited=False, promotion_allowed=False,
        scope='Own N256 full b^256 Fermat-exponent outputs and same-DUT impulse special−1. No primality/fullN/full-sample/clock/board/protection claim.')


def role(controls=False):
    need(type(controls) is bool, 'BOOL_CONTROLS')
    mr, br = (CAPTURE/'manifest.json').read_bytes(), (CAPTURE/'production-bundle.json').read_bytes()
    need((sha(mr), sha(br)) == (CAPTURE_MANIFEST, CAPTURE_BUNDLE), 'CAPTURE_PINS')
    manifest, production = json.loads(mr), json.loads(br)
    files = {}
    for name, pin in manifest['sources'].items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'SOURCE_PATH')
        raw = (CAPTURE/'source/fpga'/name).read_bytes()
        need(sha(raw) == pin, 'EXACT_CAPTURE:'+name)
        files[name] = raw
    g, parameters = production['geometry'], production['parameters']
    need(len(production['files']) == 58 and set(manifest['build']['sv_sources']) == {'rtl/'+n for n in production['files']} and
         all(files['rtl/'+name] == text.encode() and sha(text.encode()) == production['generated_sha256'][name]
             for name, text in production['files'].items()), 'EXACT58_COMPILED_GRAPH')
    need((g['n'], g['p'], g['contexts'], g['warm_interval'], g['first_digit'], g['carry_done']) ==
         (256, 16, 2, 217, 198, 217), 'OWN_SOURCE_GEOMETRY')
    need(all(parameters.get(k) == 1 for k in ('LEAN_PRODUCTION', 'LEAN_PROGRESS_WATCHDOG', 'CRT_TRANSPORT_REG',
         'INVERSE_INGRESS_REG', 'TERM_JOIN_TRANSPORT_REG', 'ERROR_AGGREGATION_REGISTERED')), 'OWN_R11_FLAGS')
    need(manifest['build']['parameters'] == dict(parameters, EPOCH_SEED0=65534, EPOCH_SEED1=42), 'EXACT_BUILD_PARAMETERS')
    donor_header = files['rtl/tb/s4_host_contexts_config_v1.h'].decode()
    need('INTERVAL=217,FIRST_DIGIT=198,CARRY_DONE=217' in donor_header and 'FIRST[2]={204,312}' in donor_header and
         'EPOCHS[2]={65534,42}' in donor_header, 'CAPTURED_HOST_CALENDAR')
    need((sha((RECIPE/'manifest.json').read_bytes()), sha((RECIPE/'production-bundle.json').read_bytes())) ==
         (RECIPE_MANIFEST, RECIPE_BUNDLE), 'FROZEN_RECIPE_IDENTITY')
    oracle_raw, cpp, header = ((RECIPE/'source/fpga'/name).read_bytes() for name in (ASSET, CPP, HEADER))
    need((sha(oracle_raw), sha(cpp), sha(header)) == (ORACLE_PIN, CPP_PIN, HEADER_PIN), 'FROZEN_ORACLE_CPP_HEADER')
    old_top = json.loads((RECIPE/'production-bundle.json').read_bytes())['top']
    text = header.decode()
    need(text.count(old_top) == 2 and text.count('INTERVAL=214,CARRY_DONE=214') == 1 and
         text.count('FIRST[2]={204,311}') == 1, 'ONLY_TOP_AND_CALENDAR_HEADER_DELTA')
    text = text.replace(old_top, production['top']).replace('INTERVAL=214,CARRY_DONE=214', 'INTERVAL=217,CARRY_DONE=217')
    text = text.replace('FIRST[2]={204,311}', 'FIRST[2]={204,312}')
    need(cpp.decode().count('DUT d(&context)') == 1 and cpp.decode().index('gfn16_runtime::configure(context,argc,argv)') <
         cpp.decode().index('DUT d(&context)') and 'gfn16_runtime::matches(context,d)' in cpp.decode(), 'RUNTIME_BEFORE_SINGLE_DUT')
    files.update({ASSET: oracle_raw, CPP: cpp, HEADER: text.encode(), SELF: (ROOT/SELF).read_bytes()})
    build = copy.deepcopy(manifest['build']); build.update(cpp_source=CPP)
    modes = ('negative-comparator', 'negative-schedule') if controls else ('normal',)
    steps = [dict(name='r11-healthy-prp-'+mode, argv=['{exe}']+([] if mode == 'normal' else ['--'+mode]),
        expected_returncode=0 if mode == 'normal' else 1,
        validator=dict(source=SELF, function='validate', config=dict(family='R11', mode=mode, oracle_sha256=ORACLE_PIN),
                       assets=dict(oracle=ASSET))) for mode in modes]
    identifier = 's4-p16-c2-r11-prp-'+('controls' if controls else 'normal')+'-q1-v1'
    ancestry = {key:value for key,value in manifest.items() if key not in
        ('schema', 'status', 'source_root', 'output_parent', 'sources', 'build', 'probe', 'steps', 'test_role', 'rtl_readiness')}
    sources = {name:sha(raw) for name,raw in files.items()}; snapshot = {n:p for n,p in sources.items() if n.endswith('.sv')}
    manifest = dict(schema=manifest['schema'], status='source_prepared_not_native', source_root='UNBOUND', output_parent='UNBOUND',
        sources=sources, build=build, probe=manifest['probe'], steps=steps, test_role='deliberate_fault' if controls else 'normal',
        rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1', candidate_id=identifier.removesuffix('-q1-v1'),
            source_snapshot=snapshot, candidate_source_sha256=sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()),
            rtl_ready_at_utc=READY),
        transport11_prp=dict(label=LABEL, production_top=production['top'], production_generated_sha256=production['generated_sha256'],
            capture_manifest_sha256=CAPTURE_MANIFEST, capture_bundle_sha256=CAPTURE_BUNDLE, geometry=g,
            healthy_calendar=dict(interval=217,first_digit=198,carry_done=217,first=[204,312],epochs=[65534,42],publication_fence=1,copy_edges=260),
            immutable_recipe_manifest_sha256=RECIPE_MANIFEST, cpp_sha256=CPP_PIN, oracle_sha256=ORACLE_PIN,
            donor_normal_metadata_provenance=ancestry, ancestor_results_inherited=False, full_exponent_not_short_pattern=True,
            host_gl_implemented=False, rollback_implemented=False, fault_immunity_inherited=False, promotion_allowed=False))
    return manifest, files, production, identifier


def prepare(output, controls=False):
    from fpga.tools import candidate_ladder, native_class_package_v2 as package
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists() and not any((ROOT/p).exists() for p in ('queue/PAUSE', 'docs/briefs/PAUSE')), 'FRESH_UNPAUSED')
    manifest, files, production, identifier = role(controls)
    source = out/'source/fpga'; source.mkdir(parents=True)
    for name, raw in files.items():
        path = source/name; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream: stream.write(raw)
    manifest['source_root'] = str(source)
    dump(out/'manifest.json', manifest); dump(out/'production-bundle.json', production)
    dump(out/'host-hours.json', candidate_ladder.budget_from_hourly())
    variants = []
    for pair in ('01', '23'):
        profile = 'gcp-c4d-static'+pair+'-v1'; worker = identifier.removesuffix('-q1-v1')+'-'+pair+'-v1'; packet = out/('packet-'+pair)
        result = package.prepare(out/'manifest.json', source, profile, worker, 'run', packet, out/'host-hours.json')
        native = json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'), sha256=result['archive_sha256'], ticket_sha256=result['ticket_sha256'],
            manifest_sha256=sha((packet/'manifest.json').read_bytes()), worker_id=worker, profile=profile, native_root=native['native_root'],
            runner='tools/native_class_package_v2.py', runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT/'tools/native_package_v4.py'), stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT/p),sha256=sha((ROOT/p).read_bytes())) for p in
                ('tools/native_package_v3.py','tools/native_package_v2.py')], max_seconds=3700))
    ticket = dict(schema='gfn16-global-ticket-v1', id=identifier, owner='independent-review',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'), priority='P1', kind='sim', needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1', allowed_hosts=['gfn16-pilot-c4d','aethia'],
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4), minimum_ram_gib=4,
        minimum_ram_rationale='Own N256 R11 captured58 healthy full exponent trial; frozen small CPP/arrays, no fullN runtime or protection inheritance.',
        est_minutes=30, promotion_bound=False, test_role=manifest['test_role'], rtl_readiness=manifest['rtl_readiness'], packages=variants,
        after=[NORMAL_ID if controls else NORMAL_GATE], on='PASS_expected_contracts')
    dump(out/'global-ticket.json', ticket)
    return dict(id=identifier, ticket=str(out/'global-ticket.json'), status='PREPARED_NOT_NATIVE', production_rtl=58, label=LABEL)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--controls', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.controls), indent=2))
