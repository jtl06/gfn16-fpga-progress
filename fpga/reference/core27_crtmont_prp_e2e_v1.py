"""E2E-1 AW5 preparation/oracle on the exact audited crtmont RTL.

Only small Python integers are evaluated here. No HDL/tool/cloud execution.
Python emits the MSB-first exponent schedule, starting at x=1; the native host
bench performs x <- x*x*2**bit with no reload or readback until the final state.
The oracle uses Python's independent three-argument pow, not an NTT/carry model.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/core27_crtmont_prp_e2e_v1.py'
TEST = 'tests/test_core27_crtmont_prp_e2e_v1.py'
BENCH = 'rtl/tb/core27_crtmont_prp_e2e_v1.cpp'
TOP = 'genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont'
PARENT = 'results/throughput-20260929/core27-rootfused-crtmont64-aws-fit-v1'
PARENT_MANIFEST_SHA = '93af1da3453947be920e73ad3f9ead17da3a8249966c7d7db5353f4502f6ece3'
PARENT_QSF_SHA = '12fdd3fa0053f0d36be2a94cd78a1984ff9d7647daf0eaaec22a5f14ae91e96f'
AUDIT = 'results/throughput-20260929/crtmont-96-selected-v1/independent-review-v1.json'
AUDIT_SHA = 'fe70997804d364f0b79058cc00f233e6be01552226568f31aca42bf2bae5708e'
LAUNCHER = 'tools/native_source_gate_v1.py'
LAUNCHER_SHA = '5205f587313a1403fddabff58bbcf4565d27c8219aa2e0c3f4aaa3af2901c2cd'
REMOTE = '/home/jtl/gfn-fpga-lab/agent-work/core27-crtmont-prp-aw5-v1'
# Each label is proven below, never inferred from a PRP result.
SPEC = ((69, 'composite', 2), (70, 'composite', 257),
        (96, 'prime', 5), (112, 'prime', 3), (989233152, 'prime', 5),
        (999999998, 'composite', 1409), (999999999, 'composite', 2),
        (1000000000, 'composite', 193))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def prove_label(base, classification, witness, aw=5):
    require(aw == 5 and type(base) is int and 69 <= base <= 1000000000, 'E2E_AW5_PROFILE_ONLY')
    modulus = base**32 + 1
    require(type(witness) is int and witness > 1, 'E2E_CERTIFICATE_WITNESS')
    if classification == 'composite':
        require(witness < modulus and modulus % witness == 0, 'E2E_COMPOSITE_FACTOR')
        return dict(kind='proper-factor', factor=witness)
    require(classification == 'prime', 'E2E_CERTIFICATE_CLASS')
    odd, power = modulus - 1, 0
    while odd % 2 == 0:
        odd //= 2
        power += 1
    require(odd < 1 << power and pow(witness, (modulus - 1)//2, modulus) == modulus - 1,
            'E2E_PROTH_CERTIFICATE')
    # Proof: for every prime q dividing modulus, the congruence makes the
    # witness's multiplicative order have 2-adic valuation exactly power.
    # Thus q >= 2**power+1 > sqrt(modulus). A composite integer cannot have
    # every prime factor greater than its square root. Hence modulus is prime.
    return dict(kind='Proth-proof', witness=witness, odd_cofactor_hex=hex(odd), power_of_two=power,
                half_exponent_residue_hex=hex(modulus-1))


def encode(value, base):
    modulus = base**32 + 1
    require(0 <= value < modulus, 'E2E_RESIDUE_RANGE')
    if value == modulus - 1:
        return [-1] + [0]*31
    result = []
    for _ in range(32):
        value, digit = divmod(value, base)
        result.append(digit)
    require(value == 0, 'E2E_DIGIT_OVERFLOW')
    return result


def decode(digits, base):
    require(len(digits) == 32 and all(type(v) is int for v in digits), 'E2E_DIGIT_EXTENT')
    require(digits == [-1]+[0]*31 or all(0 <= v < base for v in digits), 'E2E_CANONICAL_ENCODING')
    value = 0
    for digit in reversed(digits):
        value = value*base + digit
    return value % (base**32+1)


def corpus():
    lines = ['GFNPRP1 5 8']; cases = []
    for index, (base, classification, witness) in enumerate(SPEC):
        proof = prove_label(base, classification, witness)
        exponent = base**32; modulus = exponent + 1
        bits = bin(exponent)[2:]
        residue = pow(2, exponent, modulus)
        # A second small-integer implementation checks the host bit schedule,
        # but the expected final residue comes from direct builtin pow above.
        chained = 1
        for bit in bits:
            chained = (chained*chained*(2 if bit == '1' else 1)) % modulus
        require(chained == residue and (classification != 'prime' or residue == 1), 'E2E_ORACLE_SELF_CHECK')
        digits = encode(residue, base)
        require(decode(digits, base) == residue, 'E2E_ORACLE_RADIX_ROUNDTRIP')
        lines.extend((f'CASE {index} {base} {classification} {len(bits)} {bits.count("1")} {bits}',
                      ' '.join(map(str, digits))))
        cases.append(dict(index=index, base=base, classification=classification, certificate=proof,
            exponent_hex=hex(exponent), exponent_bits=bits, operations=len(bits), doubles=bits.count('1'),
            modulus_hex=hex(modulus), expected_residue_hex=hex(residue), expected_digits=digits,
            expected_prp=residue == 1))
    text = '\n'.join(lines)+'\n'
    return text, dict(schema='crtmont-prp-e2e-aw5-v1', aw=5, n=32, cases=cases,
        operations=sum(c['operations'] for c in cases), doubles=sum(c['doubles'] for c in cases),
        final_readbacks=len(cases), prime_cases=3, composite_cases=5,
        corpus_sha256=hashlib.sha256(text.encode()).hexdigest(),
        oracle='Python builtin pow(2, base**32, base**32+1); no RNS/NTT/carry dependency',
        schedule='MSB-first all exponent bits, x0=1; square then conditional double; no intermediate host access')


RESULT = re.compile(r'E2E_RESULT case=(\d+) base=(\d+) class=(prime|composite) steps=(\d+) doubles=(\d+) cycles=(\d+) prp=([01]) digits=(-?\d+(?:,-?\d+){31})')
FOOTER = re.compile(r'E2E_PASS aw=5 cases=(\d+) operations=(\d+) doubles=(\d+) readbacks=(\d+) cycles=(\d+)')


def review_logs(normal, negative, negative_stderr):
    _, oracle = corpus()
    lines = normal.splitlines()
    require(normal.endswith('\n') and len(lines) == 9, 'E2E_LOG_EXTENT')
    measured = []
    for line, case in zip(lines[:8], oracle['cases']):
        m = RESULT.fullmatch(line)
        require(m is not None, 'E2E_RESULT_SCHEMA')
        index, base, classification, steps, doubles, cycles, prp, digits = m.groups()
        require((int(index), int(base), classification, int(steps), int(doubles)) ==
                (case['index'], case['base'], case['classification'], case['operations'], case['doubles']), 'E2E_CASE_COVERAGE')
        values = list(map(int, digits.split(',')))
        residue = decode(values, int(base))
        # Replay direct bigint oracle and certificate; do not trust printed PRP.
        expected = pow(2, int(base)**32, int(base)**32+1)
        require(residue == expected and values == encode(expected, int(base)), 'E2E_FINAL_RESIDUE')
        require(bool(int(prp)) == (residue == 1) and (classification != 'prime' or residue == 1), 'E2E_PRP_LABEL')
        require(case['operations'] <= int(cycles) <= 65536*case['operations'], 'E2E_MEASURED_CYCLE_BOUND')
        measured.append(dict(base=int(base), classification=classification, operations=int(steps),
                             cycles=int(cycles), residue_hex=hex(residue), prp=residue == 1))
    footer = FOOTER.fullmatch(lines[-1])
    require(footer is not None and tuple(map(int, footer.groups())) ==
            (8, oracle['operations'], oracle['doubles'], 8, sum(c['cycles'] for c in measured)), 'E2E_FOOTER_ACCOUNTING')
    require(negative == lines[0]+'\n' and negative_stderr == 'E2E_RESIDUE_MISMATCH case=0 digit=0\n',
            'E2E_MATCHED_NEGATIVE_COMPARATOR')
    return dict(status='passed_small_aw5_prp_residues_and_comparator', cases=measured,
        operations=oracle['operations'], doubles=oracle['doubles'], final_readbacks=8,
        limitations='AW5 crtmont only; comparator negative is not an RTL mutation; no AW8, AW16 soak, T5, A4, clock or throughput qualification.')


def parent_sources():
    parent = ROOT/PARENT
    require(sha(parent/'manifest.json') == PARENT_MANIFEST_SHA and sha(parent/'probe.qsf') == PARENT_QSF_SHA,
            'E2E_AUDITED_PARENT_IDENTITY')
    require(sha(ROOT/AUDIT) == AUDIT_SHA, 'E2E_AUDIT_IDENTITY')
    manifest = json.loads((parent/'manifest.json').read_text())
    audit = json.loads((ROOT/AUDIT).read_text())
    require(audit['status'] == 'passed_independent_local_archive_review_scoped_internal_sta_crtmont96'
            and audit['source_manifest_sha256'] == PARENT_MANIFEST_SHA
            and audit['source_sha256'] == manifest['source_sha256'], 'E2E_AUDITED_SOURCE_BINDING')
    order = re.findall(r'^set_global_assignment -name SYSTEMVERILOG_FILE rtl/(\S+)$', (parent/'probe.qsf').read_text(), re.M)
    require(len(order) == 16 and set(order) == set(manifest['source_sha256']), 'E2E_EXACT_16_RTL_CLOSURE')
    pins = {}
    for name in order:
        relative = 'rtl/kernel/'+name; digest = manifest['source_sha256'][name]
        require(sha(parent/'rtl'/name) == digest == sha(ROOT/relative), 'E2E_LIVE_FROZEN_RTL_EQUALITY '+name)
        pins[relative] = digest
    require(sha(ROOT/LAUNCHER) == LAUNCHER_SHA, 'E2E_FROZEN_LAUNCHER')
    return order, pins


def prepare(output):
    require(not (ROOT/'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    output = Path(output).resolve(); require(not output.exists(), 'E2E_FRESH_PREPARATION')
    order, pins = parent_sources()
    for name in (SELF, TEST, BENCH, LAUNCHER, 'reference/__init__.py'):
        pins[name] = sha(ROOT/name)
    text, oracle = corpus()
    source = output/'source/fpga'; source.mkdir(parents=True)
    for name, digest in pins.items():
        target = source/name; target.parent.mkdir(parents=True, exist_ok=True)
        require(not (ROOT/name).is_symlink(), 'E2E_SOURCE_LINK')
        shutil.copyfile(ROOT/name, target); require(sha(target) == digest, 'E2E_CAPTURE_DRIFT')
    (source/'prp-aw5.txt').write_text(text)
    (source/'prp-oracle.json').write_text(json.dumps(oracle, indent=2)+'\n')
    for name in ('prp-aw5.txt', 'prp-oracle.json'):
        pins[name] = sha(source/name)
    manifest = dict(schema='native-source-gate-v1', status='prepared_not_executed', host='aethia',
        source_root=REMOTE+'/snapshot-v1/fpga', output_parent=REMOTE, sources=pins,
        build=dict(top=TOP, sv_sources=['rtl/kernel/'+name for name in order], cpp_source=BENCH,
                   parameters=dict(AW=5, NTT_LANES=64), cflags=['-std=c++17', '-Werror=return-type']),
        probe=dict(argv=['{exe}', '--runtime-probe'], expected_json=dict(context_threads=1, model_threads=1, expected_threads=1)),
        steps=[dict(name='prp-normal', argv=['{exe}', '{root}/prp-aw5.txt'], expected_returncode=0, expected_stderr=''),
               dict(name='prp-negative-comparator', argv=['{exe}', '{root}/prp-aw5.txt', '--negative-comparator'],
                    expected_returncode=1, expected_stderr='E2E_RESIDUE_MISMATCH case=0 digit=0\n')],
        parent_manifest_sha256=PARENT_MANIFEST_SHA, parent_audit_sha256=AUDIT_SHA,
        post_native_review='reference.core27_crtmont_prp_e2e_v1.review_logs: all 8 exact bigint residues plus matched comparator',
        scope='E2E-1 AW5 only, exact audited crtmont lineage with new host driver; no RTL change or implicit A4 profile')
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    with (output/'source.tar.gz').open('xb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode='w') as tar:
            for name in sorted(pins):
                data = (source/name).read_bytes(); require(hashlib.sha256(data).hexdigest() == pins[name], 'E2E_ARCHIVE_DRIFT')
                info = tarfile.TarInfo('fpga/'+name); info.size = len(data); info.mode = 0o644; info.mtime = 0
                tar.addfile(info, io.BytesIO(data))
    require(all(sha(ROOT/name) == value for name, value in pins.items() if name not in ('prp-aw5.txt', 'prp-oracle.json')), 'E2E_LIVE_SOURCE_DRIFT')
    report = dict(status='prepared_not_executed', manifest_sha256=sha(output/'manifest.json'),
        source_archive_sha256=sha(output/'source.tar.gz'), source_archive_bytes=(output/'source.tar.gz').stat().st_size,
        manifest_bytes=(output/'manifest.json').stat().st_size, sources=pins, corpus=oracle,
        source_root=manifest['source_root'], output_parent=REMOTE, suggested_output=REMOTE+'/aw5-native-v1',
        parent=dict(manifest=PARENT+'/manifest.json', manifest_sha256=PARENT_MANIFEST_SHA,
                    audit=AUDIT, audit_sha256=AUDIT_SHA, unchanged_rtl_files=16),
        limits=dict(host='aethia', cpus=[4,6], memory_bytes=4*(1<<30), cpu_percent=200, swap_bytes=0,
                    command_seconds=1800, overall_seconds=3600, outer_seconds=3700,
                    compile_lock='/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock'),
        dispatch_gate='Main scheduler releases physical cores 2/3 (CPUs4/6 and their siblings), source admission and live resource checks; no automatic dispatch.',
        required_post_native_review=manifest['post_native_review'],
        limitations=['Preparation and Python proofs only; no native execution.',
                    'AW8 needs a separately prepared and proven corpus; AW16 long-chain soak remains separate.',
                    'This does not qualify T5, A4, carry-profile changes, FPGA timing or production readiness.'])
    (output/'preparation.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare', type=Path); group.add_argument('--review-output', type=Path)
    args = parser.parse_args()
    if args.prepare:
        result = prepare(args.prepare)
    else:
        out = args.review_output
        result = review_logs((out/'prp-normal.log').read_text(), (out/'prp-negative-comparator.log').read_text(),
                             (out/'prp-negative-comparator.stderr.log').read_text())
    print(json.dumps(result, indent=2))
