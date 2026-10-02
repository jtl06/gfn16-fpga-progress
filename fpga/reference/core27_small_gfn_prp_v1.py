"""Reusable AW5 full-PRP oracle/configuration; no HDL or cloud execution.

The immutable baseline eight-case corpus is reproduced using only ordinary
integers. Labels are proved with Proth certificates/proper factors. Expected
residues come from builtin pow, independently of RTL, RNS, NTT and carry code.
Native execution is delegated to the shared source-pinned finite queue tools.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/core27_small_gfn_prp_v1.py'
BENCH = 'rtl/tb/core27_small_gfn_prp_v1.cpp'
TEST = 'tests/test_core27_small_gfn_prp_v1.py'
T5B_TOP = 'genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1'
T5B_SHA = '704f7fed433d724dbc8e56c7b725824ec36cce78d6ce8f021307837d2a96b8e7'
FIT = 'results/throughput-20260929/core27-t5b-provisional64-aws-fit-v1'
FIT_SHA = '1a1a67980f1744be70c0b089dcdf7e20c4cdd8714cbac26bd5798c28abbcc011'
QSF_SHA = '29ec658f30ef789f0ed1da0899300927e3d149c71110a2942360482b9df0d477'
BASELINE_CORPUS_SHA = '41bd7e2aa22416ef2987ad12d9c4dc86ef89176130e77c8df14d42fb85f45131'
SPEC = ((69, 'composite', 2), (70, 'composite', 257),
        (96, 'prime', 5), (112, 'prime', 3), (989233152, 'prime', 5),
        (999999998, 'composite', 1409), (999999999, 'composite', 2),
        (1000000000, 'composite', 193))


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def prove_label(base, classification, witness):
    need(type(base) is int and 69 <= base <= 1000000000, 'E2E_AW5_BASE')
    need(type(witness) is int and witness > 1, 'E2E_CERTIFICATE_WITNESS')
    modulus = base**32+1
    if classification == 'composite':
        need(1 < witness < modulus and modulus % witness == 0, 'E2E_COMPOSITE_FACTOR')
        return dict(kind='proper-factor', factor=witness)
    need(classification == 'prime', 'E2E_CLASSIFICATION')
    odd, power = modulus-1, 0
    while odd % 2 == 0:
        odd //= 2
        power += 1
    need(odd < 1 << power and pow(witness, (modulus-1)//2, modulus) == modulus-1,
         'E2E_PROTH_CERTIFICATE')
    return dict(kind='Proth-proof', witness=witness, odd_cofactor_hex=hex(odd),
                power_of_two=power, half_exponent_residue_hex=hex(modulus-1))


def encode(value, base):
    need(0 <= value < base**32+1, 'E2E_RESIDUE_RANGE')
    if value == base**32:
        return [-1]+[0]*31
    digits = []
    for _ in range(32):
        value, digit = divmod(value, base)
        digits.append(digit)
    need(value == 0, 'E2E_DIGIT_OVERFLOW')
    return digits


def decode(digits, base):
    need(len(digits) == 32 and all(type(v) is int for v in digits), 'E2E_DIGIT_EXTENT')
    need(digits == [-1]+[0]*31 or all(0 <= v < base for v in digits), 'E2E_CANONICAL_ENCODING')
    value = 0
    for digit in reversed(digits):
        value = value*base+digit
    return value % (base**32+1)


def corpus():
    lines, cases = ['GFNPRP1 5 8'], []
    for index, (base, classification, witness) in enumerate(SPEC):
        proof = prove_label(base, classification, witness)
        exponent = base**32
        bits = bin(exponent)[2:]
        expected = pow(2, exponent, exponent+1)
        chained = 1
        for bit in bits:
            chained = chained*chained*(1 << int(bit)) % (exponent+1)
        need(chained == expected and (classification != 'prime' or expected == 1), 'E2E_ORACLE_SCHEDULE')
        digits = encode(expected, base)
        need(decode(digits, base) == expected, 'E2E_RADIX_ROUNDTRIP')
        lines += [f'CASE {index} {base} {classification} {len(bits)} {bits.count("1")} {bits}',
                  ' '.join(map(str, digits))]
        cases.append(dict(index=index, base=base, classification=classification, certificate=proof,
                          exponent_bits=bits, operations=len(bits), doubles=bits.count('1'),
                          expected_residue_hex=hex(expected), expected_digits=digits, expected_prp=expected == 1))
    text = '\n'.join(lines)+'\n'
    need(hashlib.sha256(text.encode()).hexdigest() == BASELINE_CORPUS_SHA, 'E2E_EXACT_BASELINE_CORPUS')
    return text, dict(schema='small-gfn-prp-aw5-v1', aw=5, n=32, cases=cases,
                      operations=sum(c['operations'] for c in cases), doubles=sum(c['doubles'] for c in cases),
                      prime_cases=3, composite_cases=5, final_readbacks=8, corpus_sha256=BASELINE_CORPUS_SHA,
                      oracle='builtin pow(2, b**32, b**32+1); ordinary integers only',
                      schedule='MSB-first all bits; x0=1; square then conditional double; uninterrupted retained RAM')


RESULT = re.compile(r'E2E_RESULT case=(\d+) base=(\d+) class=(prime|composite) steps=(\d+) doubles=(\d+) cycles=(\d+) cold=(\d+) warm=(\d+) conversion=(\d+) roots=(\d+) prp=([01]) digits=(-?\d+(?:,-?\d+){31})')
FOOTER = re.compile(r'E2E_PASS aw=5 cases=(\d+) operations=(\d+) doubles=(\d+) readbacks=(\d+) cycles=(\d+) cold=(\d+) warm=(\d+) conversion=(\d+) roots=(\d+)')
MISMATCH = 'E2E_RESIDUE_MISMATCH case=0 digit=0\n'


def validate(stdout, stderr, returncode, config, assets):
    """Closed shared-queue validator; no native execution or external reads."""
    need(set(config) == {'candidate', 'mode'} and config['candidate'] in ('t5b', 'crtmont'), 'E2E_CONFIG')
    mode = config['mode']
    need(mode in ('normal', 'negative-comparator', 'negative-schedule'), 'E2E_MODE')
    text, oracle = corpus()
    need(set(assets) == {'corpus', 'oracle'} and assets['corpus'] == text
         and json.loads(assets['oracle']) == oracle, 'E2E_CLOSED_ORACLE_ASSETS')
    need(type(returncode) is int and returncode == (0 if mode == 'normal' else 1), 'E2E_PROCESS_EXIT')
    need(stderr == ('' if mode == 'normal' else MISMATCH), 'E2E_TYPED_STDERR')
    lines = stdout.splitlines()
    need(stdout.endswith('\n') and len(lines) == (9 if mode == 'normal' else 1), 'E2E_LOG_EXTENT')
    measured = []
    for line, case in zip(lines[:8 if mode == 'normal' else 1], oracle['cases']):
        match = RESULT.fullmatch(line)
        need(match is not None, 'E2E_RESULT_SCHEMA')
        index, base, label, steps, doubles, cycles, cold, warm, conversion, roots, prp, raw = match.groups()
        doubles_delta = 1 if mode == 'negative-schedule' else 0  # b=69 is odd, final bit changes 1 to 0.
        need((int(index), int(base), label, int(steps), int(doubles)) ==
             (case['index'], case['base'], case['classification'], case['operations'], case['doubles']-doubles_delta),
             'E2E_CASE_SCHEDULE_COVERAGE')
        exponent = int(base)**32
        if mode == 'negative-schedule':
            exponent ^= 1
        expected = pow(2, exponent, int(base)**32+1)
        digits = list(map(int, raw.split(',')))
        need(decode(digits, int(base)) == expected and digits == encode(expected, int(base)), 'E2E_FINAL_RESIDUE')
        need(bool(int(prp)) == (expected == 1) and (label != 'prime' or expected == 1), 'E2E_PRP_LABEL')
        wanted_conversion = 11 if config['candidate'] == 't5b' else 8*int(steps)
        need((int(cold), int(warm), int(conversion), int(roots)) ==
             (1, int(steps)-1, wanted_conversion, 3089), 'E2E_COLD_WARM_COUNTERS')
        need(int(steps) <= int(cycles) <= 65536*int(steps), 'E2E_CYCLE_BOUND')
        measured.append(dict(base=int(base), classification=label, operations=int(steps), doubles=int(doubles),
                             cycles=int(cycles), conversion_cycles=int(conversion), root_cycles=int(roots),
                             residue_hex=hex(expected), prp=expected == 1))
    if mode == 'normal':
        footer = FOOTER.fullmatch(lines[-1])
        need(footer is not None and tuple(map(int, footer.groups())) ==
             (8, oracle['operations'], oracle['doubles'], 8, sum(c['cycles'] for c in measured),
              8, oracle['operations']-8, sum(c['conversion_cycles'] for c in measured), 8*3089), 'E2E_FOOTER_ACCOUNTING')
    else:
        normal_expected = oracle['cases'][0]['expected_digits']
        if mode == 'negative-schedule':
            need(digits != normal_expected and digits[0] != normal_expected[0], 'E2E_NEGATIVE_SCHEDULE_SENSITIVITY')
    return dict(status='passed_'+mode+'_ordinary_integer_prp_contract', candidate=config['candidate'], cases=measured,
                operations=sum(c['operations'] for c in measured), mode=mode, promotion_allowed=False,
                scope='AW5 full PRP only; negatives alter host comparator/schedule, not RTL; no AW16 soak/clock claim')


def lineage():
    parent = ROOT/FIT
    need(sha(parent/'manifest.json') == FIT_SHA and sha(parent/'probe.qsf') == QSF_SHA, 'E2E_FROZEN_T5B_FIT')
    manifest = json.loads((parent/'manifest.json').read_text())
    need(manifest['top'] == T5B_TOP and manifest['promotion_allowed'] is False, 'E2E_CANDIDATE_NOT_PROMOTED')
    order = re.findall(r'^set_global_assignment -name SYSTEMVERILOG_FILE rtl/(\S+)$', (parent/'probe.qsf').read_text(), re.M)
    need(len(order) == 16 and set(order) == set(manifest['source_sha256']), 'E2E_16_RTL_CLOSURE')
    pins = {}
    for name in order:
        relative = 'rtl/kernel/'+name
        digest = manifest['source_sha256'][name]
        need(sha(parent/'rtl'/name) == sha(ROOT/relative) == digest, 'E2E_RTL_DRIFT '+name)
        pins[relative] = digest
    need(pins['rtl/kernel/'+T5B_TOP+'.sv'] == T5B_SHA, 'E2E_EXACT_T5B_CORE')
    return ['rtl/kernel/'+name for name in order], pins


def prepare(output):
    """Emit role data/closed source input, then use shared native_package_v1."""
    output = Path(output).resolve()
    need(not (ROOT/'docs/briefs/PAUSE').exists() and not output.exists(), 'E2E_PAUSE_OR_FRESH_OUTPUT')
    order, pins = lineage()
    for name in (SELF, BENCH, TEST):
        pins[name] = sha(ROOT/name)
    source = output/'source/fpga'
    source.mkdir(parents=True)
    for name, digest in pins.items():
        need(not (ROOT/name).is_symlink(), 'E2E_SOURCE_LINK')
        target = source/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, target)
        need(sha(target) == digest, 'E2E_CAPTURE_DRIFT')
    text, oracle = corpus()
    for name, value in [('prp-aw5.txt', text), ('prp-oracle.json', json.dumps(oracle, indent=2)+'\n')]:
        (source/name).write_text(value)
        pins[name] = sha(source/name)
    steps = []
    for mode in ('normal', 'negative-comparator', 'negative-schedule'):
        argv = ['{exe}', '{root}/prp-aw5.txt']+([] if mode == 'normal' else ['--'+mode])
        steps.append(dict(name='prp-'+mode, argv=argv, expected_returncode=0 if mode == 'normal' else 1,
                          expected_stderr='' if mode == 'normal' else MISMATCH,
                          validator=dict(source=SELF, function='validate', config=dict(candidate='t5b', mode=mode),
                                         assets=dict(corpus='prp-aw5.txt', oracle='prp-oracle.json'))))
    manifest = dict(schema='native-source-gate-v1', status='prepared_not_executed', host='gfn16-pilot-c4d',
                    source_root='/unhosted/fpga', output_parent='/unhosted/output', sources=pins,
                    build=dict(top=T5B_TOP, sv_sources=order, cpp_source=BENCH, parameters=dict(AW=5, NTT_LANES=64),
                               cflags=['-std=c++17', '-Werror=return-type', '-DGFNPRP_T5B=1']),
                    probe=dict(argv=['{exe}', '--runtime-probe'], expected_json=dict(context_threads=1, model_threads=1, expected_threads=1)),
                    steps=steps, parent_manifest_sha256=FIT_SHA, exact_core_sha256=T5B_SHA, promotion_allowed=False,
                    scope='E2E-1 AW5 eight complete PRPs on unchanged actual T5b RTL; host-only typed negatives')
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    need(all(sha(ROOT/name) == digest for name, digest in pins.items() if name not in ('prp-aw5.txt', 'prp-oracle.json')),
         'E2E_TERMINAL_SOURCE_DRIFT')
    result = dict(status='prepared_not_executed', manifest_sha256=sha(output/'manifest.json'), sources=pins,
                  parent_manifest_sha256=FIT_SHA, core_sha256=T5B_SHA, corpus_sha256=BASELINE_CORPUS_SHA,
                  operations=oracle['operations'], doubles=oracle['doubles'], cases=8,
                  prime_cases=3, composite_cases=5, unchanged_rtl_files=16, promotion_allowed=False,
                  next='shared native_package_v1 lint/run phases after launcher smoke and owner slot admission; review exact lint debt before run')
    (output/'preparation.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def review_output(output):
    """Replay each closed contract plus the matched comparator relationship."""
    out = Path(output)
    text, oracle = corpus()
    assets = dict(corpus=text, oracle=json.dumps(oracle))
    results = {}
    for mode in ('normal', 'negative-comparator', 'negative-schedule'):
        stem = 'prp-'+mode
        results[mode] = validate((out/(stem+'.log')).read_text(), (out/(stem+'.stderr.log')).read_text(),
                                 0 if mode == 'normal' else 1, dict(candidate='t5b', mode=mode), assets)
    need((out/'prp-negative-comparator.log').read_text() == (out/'prp-normal.log').read_text().splitlines()[0]+'\n',
         'E2E_MATCHED_COMPARATOR_REPLAY')
    return dict(status='passed_T5b_aw5_full_prp_residues_and_host_negatives_UNPROMOTED', contracts=results,
                promotion_allowed=False, limitation='Value/counter log replay only; independent source/tool/native report/archive review and advisor verification still required')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare', type=Path)
    group.add_argument('--review-output', type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.prepare) if args.prepare else review_output(args.review_output), indent=2))
