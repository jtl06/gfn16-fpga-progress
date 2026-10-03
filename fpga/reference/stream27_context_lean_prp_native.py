"""Own N256 R10 healthy full-exponent PRPs and same-DUT special sentinel.

Lean and protected verification twin are separate source-exact native builds.
No primality certificate, full-sample PRP, protected fault, clock or GL claim.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_context_lean_prp_native.py'
CPP = 'rtl/tb/stream27_context_lean_prp.cpp'
HEADER = 'rtl/tb/stream27_context_lean_prp_config.h'
BINDER = 'reference/stream27_context_storage_combo_timing10_bind.py'
BINDER_PIN = '8404e36c688c040f47433b7aff2b5fbee34e438968f41898fe8fee6818f51491'
DONOR = ROOT/'results/throughput-20260929/trackS-c2-storage-combo-timing10-native-v1/aw8-normal'
DONOR_MANIFEST = '63d58f4645eb55931c35aa4b72f034732eecced860125593036c76df7c70abd7'
DONOR_BUNDLE = 'f1c9f7cccd8303afd0c0ccdeca81aea7f8ccdfac1dbb04aa5b497774448f66cf'
LABELS = {'lean': 'lean build; host GL assumed (unimplemented)',
          'protected': 'protected R10 verification twin; healthy numerical scope only'}
BASES = (599, 600, 7552, 768, 989233152, 999999998, 999999999, 1000000000)
N, P, INTERVAL, CARRY_DONE = 256, 16, 214, 214
FIRST, EPOCHS = (204, 311), (65534, 42)
READY = '2026-10-02T18:53:00Z'


def need(ok, why):
    if not ok:
        raise ValueError('C2_LEAN_PRP_'+why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def encode(value, base):
    need(type(value) is int and type(base) is int and 599 <= base <= 1000000000, 'ENCODE_DOMAIN')
    modulus = base**N+1
    value %= modulus
    if value == modulus-1:
        return [-1]+[0]*(N-1)
    result = []
    for _ in range(N):
        value, digit = divmod(value, base)
        result.append(digit)
    need(value == 0, 'RADIX_N_EXTENT')
    return result


def decode(digits, base):
    need(len(digits) == N and all(type(v) is int for v in digits), 'SIGNED_DIGITS')
    if digits == [-1]+[0]*(N-1):
        return base**N
    need(all(0 <= v < base for v in digits), 'CANONICAL_RADIX')
    return sum(value*base**address for address, value in enumerate(digits))


def corpus():
    # Ordinary whole-integer arithmetic is bounded to N256 here. No NTT/GMP.
    cases = []
    for index, base in enumerate(BASES):
        exponent = base**N
        bits = bin(exponent)[2:]
        value = pow(2, exponent, exponent+1)
        digits = encode(value, base)
        need(decode(digits, base) == value, 'POW_RADIX_ROUNDTRIP')
        cases.append(dict(case=index, base=base, exponent_bits=bits, steps=len(bits),
            doubles=bits.count('1'), expected_digits=digits, fermat_prp_passed=value == 1,
            classification='not asserted'))
    changed = encode(pow(2, BASES[0]**N ^ 1, BASES[0]**N+1), BASES[0])
    need(changed[0] != cases[0]['expected_digits'][0], 'LAST_BIT_NEGATIVE_WORD0_SENSITIVITY')
    return dict(schema='gfn16-r10-healthy-prp-n256-v1', n=N, p=P, minimum_base=599,
        cases=cases, sentinel=dict(initial_impulse_address=N//2, steps=1, double=0,
            bases=list(BASES[:2]), expected_digits=[-1]+[0]*(N-1)),
        oracle='ordinary builtin pow(2,b**256,b**256+1), full MSB exponent; no RNS/NTT/GMP',
        primality_claim=False, full_sample_claim=False)


def header(production, oracle, branch):
    arrays = ','.join('{'+','.join(map(str, row['expected_digits']))+'}' for row in oracle['cases'])
    bits = ','.join(json.dumps(row['exponent_bits']) for row in oracle['cases'])
    return ('#pragma once\n#include <cstdint>\n#include "V'+production['top']+'.h"\nusing DUT=V'+production['top']+';\n'
        'static constexpr unsigned AW=8,N=256,P=16,INTERVAL=214,CARRY_DONE=214;\n'
        'static constexpr unsigned FIRST[2]={204,311},EPOCHS[2]={65534,42};\n'
        'static constexpr unsigned BASES[8]={'+','.join(map(str, BASES))+'};\n'
        'static constexpr unsigned COUNTS[8]={'+','.join(str(row['steps']) for row in oracle['cases'])+'};\n'
        'static constexpr const char* BITS[8]={'+bits+'};\n'
        'static constexpr int32_t EXPECTED[8][N]={'+arrays+'};\n'
        'static constexpr const char* BUILD_LABEL='+json.dumps(LABELS[branch])+';\n').encode()


def validate(stdout, stderr, rc, config, assets):
    need(set(config) == {'branch', 'mode', 'oracle_sha256'} and config['branch'] in LABELS and
         config['mode'] in ('normal', 'negative-comparator', 'negative-schedule'), 'CONFIG')
    need(set(assets) == {'oracle'} and sha(assets['oracle'].encode()) == config['oracle_sha256'], 'EXACT_ORACLE_ASSET')
    oracle = json.loads(assets['oracle'])
    need(oracle['schema'] == 'gfn16-r10-healthy-prp-n256-v1' and oracle['n'] == N and oracle['p'] == P and
         [row['base'] for row in oracle['cases']] == list(BASES), 'ORACLE_DOMAIN')
    label, mode = LABELS[config['branch']], config['mode']
    if mode != 'normal':
        need(type(rc) is int and rc == 1 and stdout == label+'\n' and
             stderr == 'A_PRP_RESIDUE_MISMATCH case=0 digit=0\n', 'TYPED_HOST_CONTROL')
        return dict(status='PASS_expected_contracts', mode=mode, build_label=label,
            scope='Finite comparator/schedule sensitivity only; not a hardware detector test.', promotion_allowed=False)
    need(type(rc) is int and rc == 0 and stderr == '' and stdout.endswith('\n'), 'NORMAL_EXIT')
    lines = stdout.splitlines()
    need(len(lines) == 12 and lines[0] == label, 'LABELED_OUTPUT_EXTENT')
    rows = []
    for index, line in enumerate(lines[1:11]):
        need(line.startswith('A_CONTEXT_PRP_RESULT '), 'ROW_GRAMMAR')
        row = json.loads(line.removeprefix('A_CONTEXT_PRP_RESULT '))
        need(set(row) == {'case', 'base', 'steps', 'doubles', 'done_edge', 'sentinel', 'digits'}, 'ROW_KEYS')
        wanted = oracle['cases'][index] if index < 8 else dict(base=BASES[index-8], steps=1, doubles=0,
                                                                          expected_digits=oracle['sentinel']['expected_digits'])
        need(row['case'] == index and type(row['case']) is int and row['base'] == wanted['base'] and
             type(row['base']) is int and row['steps'] == wanted['steps'] and type(row['steps']) is int and
             row['doubles'] == wanted['doubles'] and type(row['doubles']) is int and
             row['sentinel'] is (index >= 8), 'FULL_EXPONENT_OR_SENTINEL_IDENTITY')
        need(row['digits'] == wanted['expected_digits'] and len(row['digits']) == N and
             all(type(v) is int for v in row['digits']), 'ALL_SIGNED96_DIGITS')
        need(type(row['done_edge']) is int and FIRST[index%2]+(wanted['steps']-1)*INTERVAL+CARRY_DONE <
             row['done_edge'] < max(oracle['cases'][index-index%2]['steps'] if index < 8 else 1,
                                   oracle['cases'][index-index%2+1]['steps'] if index < 8 else 1)*INTERVAL+33*N+10000,
             'FINITE_SOURCE_CALENDAR_PUBLICATION')
        rows.append(row)
    squares = sum(row['steps'] for row in rows)
    doubles = sum(row['doubles'] for row in rows)
    need(lines[-1] == f'A_CONTEXT_PRP_PASS cases=8 sentinel_cases=2 squares={squares} doubles={doubles} signed96_words={10*N} interval={INTERVAL}',
         'COMPLETE_FOOTER')
    return dict(status='PASS_expected_contracts', branch=config['branch'], build_label=label,
        cases=8, sentinel_cases=2, squares=squares, doubles=doubles, signed96_words=10*N,
        interval=INTERVAL, host_gl_implemented=False, rollback_implemented=False,
        protected_fault_immunity_inherited=False, promotion_allowed=False,
        scope='Own N256 full Fermat-exponent healthy PRPs plus same-DUT b^(N/2) special−1; all small outputs retained. No fullN/full-sample PRP, fault/clock/board claim.')


def role(branch, controls=False):
    from fpga.reference import stream27_context_storage_combo_timing10_bind as core
    need(branch in LABELS and type(controls) is bool, 'BRANCH')
    need(sha((ROOT/BINDER).read_bytes()) == BINDER_PIN, 'FROZEN_R10_API')
    mr, br = (DONOR/'manifest.json').read_bytes(), (DONOR/'production-bundle.json').read_bytes()
    need((sha(mr), sha(br)) == (DONOR_MANIFEST, DONOR_BUNDLE), 'IMMUTABLE_LEAN_CAPTURE')
    manifest, donor = json.loads(mr), json.loads(br)
    files = {}
    for name, pin in manifest['sources'].items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'SOURCE_PATH')
        raw = (DONOR/'source/fpga'/name).read_bytes()
        need(sha(raw) == pin, 'EXACT_CAPTURE:'+name)
        files[name] = raw
    emitted = core.prepare(N, p=P, contexts=2, enabled=1, lean_production=1)
    need(emitted['generated_sha256'] == donor['generated_sha256'] and emitted['files'] == donor['files'], 'EXACT58_CAPTURE_API')
    production = donor if branch == 'lean' else core.prepare(N, p=P, contexts=2, enabled=1, lean_production=0)
    need(len(production['files']) == 58 and (production['geometry']['warm_interval'], production['geometry']['first_digit'],
         production['geometry']['carry_done']) == (214, 195, 214), 'OWN_BRANCH_GEOMETRY')
    for name in donor['files']:
        files.pop('rtl/'+name)
    files.update({'rtl/'+name:text.encode() for name, text in production['files'].items()})
    oracle = corpus()
    oracle_raw = (json.dumps(oracle, indent=2)+'\n').encode()
    asset = 'reference-assets/r10-healthy-prp-n256.json'
    files[asset], files[HEADER] = oracle_raw, header(production, oracle, branch)
    files[CPP], files[SELF] = (ROOT/CPP).read_bytes(), (ROOT/SELF).read_bytes()
    text = files[CPP].decode()
    need(text.count('DUT d(&context)') == 1 and text.index('gfn16_runtime::configure(context,argc,argv)') <
         text.index('DUT d(&context)') and 'gfn16_runtime::matches(context,d)' in text, 'RUNTIME_BEFORE_EVERY_MODEL')
    for name, pin in production['source_sha256'].items():
        raw = (ROOT/name).read_bytes()
        need(sha(raw) == pin, 'R10_SOURCE_CLOSURE')
        files['lineage/'+name] = raw
    build = copy.deepcopy(manifest['build'])
    build.update(top=production['top'], sv_sources=['rtl/'+name for name in production['rtl_sources']], cpp_source=CPP,
                 parameters=dict(production['parameters'], EPOCH_SEED0=65534, EPOCH_SEED1=42))
    modes = ('negative-comparator', 'negative-schedule') if controls else ('normal',)
    steps = [dict(name='r10-'+branch+'-healthy-prp-'+mode, argv=['{exe}']+([] if mode == 'normal' else ['--'+mode]),
        expected_returncode=0 if mode == 'normal' else 1,
        validator=dict(source=SELF, function='validate', config=dict(branch=branch, mode=mode, oracle_sha256=sha(oracle_raw)),
                       assets=dict(oracle=asset))) for mode in modes]
    snapshot = {name:sha(raw) for name, raw in files.items() if name.endswith('.sv')}
    candidate = 's4-p16-c2-r10-'+branch+'-prp-'+('controls' if controls else 'normal')
    manifest.update(source_root='UNBOUND', output_parent='UNBOUND', build=build, steps=steps,
        sources={name:sha(raw) for name,raw in files.items()}, test_role='deliberate_fault' if controls else 'normal',
        rtl_readiness=dict(schema='gfn16-candidate-rtl-ready-v1', candidate_id=candidate, source_snapshot=snapshot,
            candidate_source_sha256=sha(json.dumps(snapshot, sort_keys=True, separators=(',',':')).encode()), rtl_ready_at_utc=READY))
    # Old exact normal metadata is provenance, never this new recipe's contract.
    ancestry = {key:manifest.pop(key) for key in list(manifest) if key not in
        ('schema','status','source_root','output_parent','sources','build','probe','steps','test_role','rtl_readiness')}
    manifest['healthy_prp'] = dict(branch=branch, label=LABELS[branch], n=N, p=P, cases=8, sentinel_cases=2,
        production_top=production['top'], production_generated_sha256=production['generated_sha256'],
        source_sha256=production['source_sha256'], captured_lean_manifest_sha256=DONOR_MANIFEST,
        captured_lean_bundle_sha256=DONOR_BUNDLE, donor_normal_metadata_provenance=ancestry,
        full_exponent_not_short_pattern=True, host_gl_implemented=False, rollback_implemented=False,
        fault_immunity_inherited=False, native_qualified=False, promotion_allowed=False)
    return manifest, files, production


def prepare(output, branch, controls=False):
    from fpga.tools import candidate_ladder, native_class_package_v2 as package
    out = Path(output).resolve()
    need(out.is_relative_to(ROOT) and not out.exists() and not any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')), 'FRESH_UNPAUSED')
    manifest, files, production = role(branch, controls)
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
    logical_id = manifest['rtl_readiness']['candidate_id']+'-q1-v1'
    variants = []
    for pair in ('01','23'):
        profile = 'gcp-c4d-static'+pair+'-v1'
        worker = logical_id.removesuffix('-q1-v1')+'-'+pair+'-v1'
        packet = out/('packet-'+pair)
        result = package.prepare(out/'manifest.json', source, profile, worker, 'run', packet, out/'host-hours.json')
        native = json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'), sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'], manifest_sha256=sha((packet/'manifest.json').read_bytes()),
            worker_id=worker, profile=profile, native_root=native['native_root'], runner='tools/native_class_package_v2.py',
            runner_sha256=sha((ROOT/'tools/native_class_package_v2.py').read_bytes()), stager=str(ROOT/'tools/native_package_v4.py'),
            stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()), stager_dependencies=[dict(path=str(ROOT/p),sha256=sha((ROOT/p).read_bytes()))
            for p in ('tools/native_package_v3.py','tools/native_package_v2.py')], max_seconds=3700))
    ticket = dict(schema='gfn16-global-ticket-v1', id=logical_id, owner='independent-review',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'), priority='P1', kind='sim', needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1', allowed_hosts=['gfn16-pilot-c4d','aethia'],
        resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4), minimum_ram_gib=4,
        minimum_ram_rationale='Own N256 healthy full exponent PRP trial, unchanged small58 graph; no fullN runtime/clock or protected detector inheritance.',
        est_minutes=30,promotion_bound=False,test_role=manifest['test_role'],rtl_readiness=manifest['rtl_readiness'],packages=variants)
    if controls:
        ticket.update(after=['s4-p16-c2-r10-'+branch+'-prp-normal-q1-v1'], on='PASS_expected_contracts')
    elif branch == 'lean':
        ticket.update(after=['s4-p16-c2-combo-r10-aw8-normal-q1-v1'], on='PASS_expected_contracts')
    dump(out/'global-ticket.json', ticket)
    return dict(id=logical_id, ticket=str(out/'global-ticket.json'), production_rtl=58, label=LABELS[branch], status='PREPARED_NOT_NATIVE')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--branch', choices=LABELS, required=True)
    parser.add_argument('--controls', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.branch, args.controls), indent=2))
