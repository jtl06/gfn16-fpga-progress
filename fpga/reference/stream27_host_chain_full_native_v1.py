"""Bounded actual full-N P8 host/T5b native gate, never local full-N math.

Source/ROM emission and small N32/N256 independent checks are coordinator-only.
All HDL/ELF/full-N arithmetic executes exclusively on the admitted dispatcher.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_host_chain_full_native_v1.py'
CPP = 'rtl/tb/stream27_host_chain_full_native_v1.cpp'
REFERENCE = 'rtl/tb/stream27_host_chain_full_reference_v1.h'
NTT = 'rtl/tb/stream27_shared_reference_ntt_v1.h'
HEADER = 'rtl/tb/s4_host_chain_full_config_v1.h'
TEST = 'tests/test_stream27_host_chain_full_native_v1.py'
IDENTIFIER = 's4-aw16-p8-full-host-q1-v1'
DEPENDENCY = 's4-aw8-p8-long-host-q1-v4'
SEED, N, P, BASE = 65534, 65536, 8, 1000000000
PRIMES = ((104857601, 3), (69206017, 5), (67239937, 10))
GEOMETRY = dict(first_digit=16652, warm_interval=16653, carry_done=24847, rows=8192)
ROOT_NAME = 'genefer_stream27_host_chain_aw16_p8_param_v1.sv'
ROOT_SHA = 'ee65a33fdaac06de83c7122f7e95704c835f4c1ee55171f846ac7e553ed30d21'
PHYSICAL = 'artifacts/s4-p8-whole-host-aw16-source-v1/project/manifest.json'
PINS = {
 'reference/stream27_host_chain_param_v2.py': 'bd909f42310a194220c5c20f0a4e3decb3e97bcf142b3ffd5a1b300d0ffc9773',
 'reference/stream27_shared_field_v4.py': 'daa45b2d5c614f8ea2b791f993cc22c5cc1f5e215f307242785542b109e29865',
 NTT: 'c7837ba92829293131efda704dfdde347708641bf9aff46dccbcb87b825ba390',
 CPP: '30cada68746f625d95641e59e49b079b0896e0534a5288f196f95200ea8d4fa7',
 REFERENCE: '88849a77ad7c58fc99f6d56eeded2a772a78fbe2b2da03fabdf7ac71aaf12c54',
 PHYSICAL: '762d765ac2518e19005ca5503e8f6110f55059f8bfdf54200c41894075f113ce',
}
PACKAGE = 'tools/native_class_package_v2.py'
PACKAGE_SHA = '03b6a81aa7d465487da97f854a79e9e43a19c9c637db6178587cfac02476f604'
STAGER = 'tools/native_package_v3.py'
STAGER_SHA = '5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9'
COMPANION = 'tools/native_package_v2.py'
COMPANION_SHA = '3f2186fa5aac8129ac1ad5a161de39cf221925ee95d5de6364a941b199e7279a'
BUDGET_SHA = 'c22ea21b9e978a3ef3d5d3d6688aed68a275eca87e068a96f1585b5cd254c3aa'
NEGATIVE = 'S4_FULL_HOST_AW16_P8_NEGATIVE_ORACLE_REJECT\n'


def need(ok, label):
    if not ok: raise ValueError(label)


def sha(raw): return hashlib.sha256(raw).hexdigest()
def canonical_json(value): return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def verify(root=ROOT):
    for name, pin in PINS.items():
        path = Path(root)/name
        need(path.is_file() and not path.is_symlink() and sha(path.read_bytes()) == pin,
             'S4_FULL_HOST_PARENT_DRIFT '+name)


def counts():
    interval, done = GEOMETRY['warm_interval'], GEOMETRY['carry_done']
    job_cycles = [102+done+2+7*N+4, 3+7*interval+done+2+7*N+4]
    return dict(jobs=2, operations=9, feed_descriptors=7, true_final_rows=2*N//P,
                paired_reads=2*N, copied_words=2*N, partial_reads=1,
                canonical_cycles=12*N, image_copy_cycles=2*(N+3),
                candidate_cycles=sum(job_cycles), fifo_peak=4, full_exchanges=3,
                backpressure_edges=3*interval-4)


def footer_prefix():
    return 'S4_FULL_HOST_PASS aw=16 p=8 '+' '.join(f'{k}={v}' for k, v in counts().items())+' t5b_wait_edges='


def validate(stdout, stderr, returncode, config, assets):
    need(type(config) is dict and set(config) == {'aw', 'p', 'mode'} and
         type(config['aw']) is int and config['aw'] == 16 and
         type(config['p']) is int and config['p'] == 8 and
         config['mode'] in ('normal', 'oracle') and assets == {}, 'S4_FULL_HOST_CONFIG')
    need(type(stdout) is str and type(stderr) is str and type(returncode) is int,
         'S4_FULL_HOST_OUTPUT_TYPES')
    measured = None
    if config['mode'] == 'oracle':
        need((returncode, stdout, stderr) == (1, '', NEGATIVE), 'S4_FULL_HOST_TYPED_ORACLE')
    else:
        match = re.fullmatch(re.escape(footer_prefix())+r'([1-9][0-9]*)\n', stdout, re.ASCII)
        need(returncode == 0 and stderr == '' and bool(match), 'S4_FULL_HOST_TYPED_NORMAL')
        measured = int(match.group(1))
        need(9 <= measured <= 9*(20*N+100000), 'S4_FULL_HOST_T5B_BOUND')
    return dict(status='PASS_expected_contracts', aw=16, p=8, mode=config['mode'],
                counts=counts(), measured_t5b_wait_edges=measured, promotion_allowed=False,
                scope='Two bounded full-N host jobs/nine arithmetic operations; not PRP, physical timing or promotion.')


def small_arguments(words, base):
    need(len(words) in (32, 256) and type(base) is int and 2 <= base <= 1000000000,
         'S4_FULL_HOST_SMALL_REFERENCE_ONLY')


def small_coefficients(words, twice=False):
    """Independent ordinary Python radix2 NTT/CRT, hard bounded to smallN."""
    small_arguments(words, 2)
    residues = []
    for prime, generator in PRIMES:
        def transform(a, inverse):
            n = len(a); j = 0
            for i in range(1, n):
                bit = n//2
                while j & bit: j ^= bit; bit //= 2
                j ^= bit
                if i < j: a[i], a[j] = a[j], a[i]
            length = 2
            while length <= n:
                root = pow(generator, (prime-1)//length, prime)
                if inverse: root = pow(root, prime-2, prime)
                for start in range(0, n, length):
                    weight = 1
                    for index in range(length//2):
                        u = a[start+index]; v = a[start+index+length//2]*weight % prime
                        a[start+index] = (u+v) % prime; a[start+index+length//2] = (u-v) % prime
                        weight = weight*root % prime
                length *= 2
            if inverse:
                scale = pow(n, prime-2, prime); a[:] = [v*scale % prime for v in a]
        psi = pow(generator, (prime-1)//(2*len(words)), prime)
        a = [int(v)*pow(psi, index, prime) % prime for index, v in enumerate(words)]
        transform(a, False); a = [v*v % prime for v in a]; transform(a, True)
        residues.append([v*pow(psi, -index, prime)*(2 if twice else 1) % prime for index, v in enumerate(a)])
    p0, p1, p2 = (p[0] for p in PRIMES); p01 = p0*p1; modulus = p01*p2
    out = []
    for a, b, c in zip(*residues):
        lower = a+p0*((b-a)*pow(p0, -1, p1) % p1)
        value = lower+p01*((c-lower)*pow(p01, -1, p2) % p2)
        out.append(value-modulus if value > modulus//2 else value)
    return out


def small_serial(values, base):
    """Proof of native direct terminal-q reduction, NOT DUT3pass/blockcarry."""
    small_arguments(values, base); n = len(values); bound = 2*n*(base-1); a_bound = bound*(base-1)
    need(a_bound < PRIMES[0][0]*PRIMES[1][0]*PRIMES[2][0]//2 and bound < 2**47,
         'S4_FULL_HOST_REFERENCE_WIDTH')
    digits = []; carry = 0
    for value in values:
        need(abs(value) <= a_bound, 'S4_FULL_HOST_COEF_BOUND')
        carry, digit = divmod(value+carry, base); digits.append(digit)
        need(abs(carry) <= bound, 'S4_FULL_HOST_Q_BOUND')
    carry = -carry
    for index, digit in enumerate(digits): carry, digits[index] = divmod(digit+carry, base)
    need(carry in (-1, 0, 1), 'S4_FULL_HOST_ONE_WRAP')
    if carry == -1:
        if all(d == base-1 for d in digits): return [-1]+[0]*(n-1)
        add = 1
        for index, digit in enumerate(digits): add, digits[index] = divmod(digit+add, base)
        need(add == 0, 'S4_FULL_HOST_NEGATIVE_ADJUST')
    elif carry == 1:
        if not any(digits): return [-1]+[0]*(n-1)
        borrow = -1
        for index, digit in enumerate(digits): borrow, digits[index] = divmod(digit+borrow, base)
        need(borrow == 0, 'S4_FULL_HOST_POSITIVE_ADJUST')
    return digits


def small_whole(values, base):
    small_arguments(values, base); n = len(values)
    value = 0
    for coefficient in reversed(values): value = value*base+coefficient
    value %= base**n+1
    if value == base**n: return [-1]+[0]*(n-1)
    digits = []
    for _ in range(n): value, digit = divmod(value, base); digits.append(digit)
    need(value == 0, 'S4_FULL_HOST_WHOLE_DECODE'); return digits


def small_proof():
    checked = 0
    for n in (32, 256):
        for base in (2, 1000000000):
            for kind in range(3):
                words = []; state = 0x1928eaf1+kind
                for _ in range(n):
                    state = (1664525*state+1013904223) & 0xffffffff; words.append(state % base)
                words[3] = words[-1] = -1; twice = bool(kind & 1)
                direct = [0]*n
                for i, a in enumerate(words):
                    for j, b in enumerate(words): direct[(i+j)%n] += a*b*(1 if i+j < n else -1)*(2 if twice else 1)
                need(small_coefficients(words, twice) == direct, 'S4_FULL_HOST_SMALL_NTT_CRT')
                need(small_serial(direct, base) == small_whole(direct, base), 'S4_FULL_HOST_SMALL_INTEGER')
                for values in ([-1]+[0]*(n-1), [0]*(n-1)+[base]):
                    need(small_serial(values, base) == small_whole(values, base), 'S4_FULL_HOST_SMALL_SPECIAL')
                checked += 1
    return dict(status='PASS_source_small_reference', cases=checked, primes=3, geometries=[32, 256],
                serial_whole_checks=3*checked, full_N_numeric_locally_performed=False)


def role():
    verify()
    from fpga.reference import stream27_host_chain_param_v2 as core
    bundle = core.prepare(N, P, paired=True, contexts=1, allow_full_constants=True)
    standalone = core.prepare(N, P, paired=False, contexts=1, allow_full_constants=True)
    need(all(bundle['files'].get(name) == text for name, text in standalone['files'].items()),
         'S4_FULL_HOST_STANDALONE_PAIR_JOIN')
    need(sha(bundle['files'][ROOT_NAME].encode()) == ROOT_SHA and len(standalone['rtl_sources']) == 49 and
         len(bundle['rtl_sources']) == 60 and all(bundle['geometry'][k] == v for k, v in GEOMETRY.items()),
         'S4_FULL_HOST_EXACT_GEOMETRY_SOURCE')
    physical = json.loads((ROOT/PHYSICAL).read_text())
    need(physical['core_parameters'] == dict(AW=16, P=8, CONTEXTS=1, EPOCH_SEED=SEED) and
         physical['source_sha256'] == standalone['generated_sha256'] and physical['geometry'] == bundle['geometry'],
         'S4_FULL_HOST_EXACT_PHYSICAL_CONFIGURATION_JOIN')
    for name, pin in physical['source_sha256'].items():
        need(sha((ROOT/PHYSICAL).parent.joinpath('rtl', name).read_bytes()) == pin,
             'S4_FULL_HOST_PHYSICAL_SOURCE_BYTES '+name)
    files = {'rtl/'+name: text.encode() for name, text in bundle['files'].items()}
    for name in (CPP, REFERENCE, NTT, SELF, TEST): files[name] = (ROOT/name).read_bytes()
    header = f'''#include "V{bundle['top']}.h"
using DUT=V{bundle['top']};
constexpr unsigned AW=16,P=8,N=65536,BASE=1000000000;
constexpr uint64_t FIRST_DIGIT=16652,INTERVAL=16653,CARRY_DONE=24847,EXPECTED_CYCLES={counts()['candidate_cycles']},T5B_WAIT_LIMIT=20*N+100000;
'''
    # uint64_t is used before the bench's own standard includes.
    files[HEADER] = ('#include <cstdint>\n'+header).encode()
    for name in dict.fromkeys(bundle['source_dependencies']+list(PINS)):
        files['lineage/'+name] = (ROOT/name).read_bytes()
    metadata = dict(epoch_seed=SEED, dense_input='xorshift32 seed0x9135ba27, modulo1e9; signed-1 at17/N-1',
        jobs=[dict(kind='legacy', count=1, cache_hit=False, bits=[0]),
              dict(kind='dependent_feed', count=8, cache_hit=True, bits=[0,1,0,1,1,0,1,0], reload=False)],
        counts=counts(), geometry=bundle['geometry'], host_contract=bundle['host_contract'],
        cycle_contract=bundle['cycle_contract'], source_sha256=bundle['source_sha256'],
        generated_sha256=bundle['generated_sha256'], standalone_top=standalone['top'],
        standalone_generated_sha256=standalone['generated_sha256'], candidate_root_sha256=ROOT_SHA,
        physical_source_manifest=PHYSICAL, physical_source_manifest_sha256=PINS[PHYSICAL],
        pairing='Actual exact promoted T5b sources/NTT_LANES64 and candidate standalone49 byte-identical within paired60.',
        shared_delta=bundle['reset_delta'],
        oracle='Frozen independent iterative three-prime negacyclic NTT, centered signed128 CRT, serial Euclidean carry then direct terminal-q subtraction and at most one modulus adjustment; native small schoolbook/limb selfchecks.',
        source_small_proof=small_proof(), full_N_numeric_locally_performed=False, native_executed=False,
        scope='Two host jobs,9 dependent arithmetic operations,2N final signed96 words; no full-N PRP, all-fields sizing, physical clock or production promotion.')
    manifest = dict(schema='native-source-gate-v1', status='prepared_not_executed',
        source_root='/not-a-dispatch-path/full-host/fpga', output_parent='/not-a-dispatch-path/full-host/output',
        sources={name: sha(raw) for name, raw in files.items()},
        build=dict(top=bundle['top'], sv_sources=['rtl/'+name for name in bundle['rtl_sources']], cpp_source=CPP,
                   parameters=dict(AW=16, P=8, CONTEXTS=1, EPOCH_SEED=SEED),
                   cflags=['-std=c++17','-O2','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'], expected_json=dict(context_threads=1, model_threads=1, expected_threads=1)),
        steps=[dict(name='full-host-'+mode, argv=['{exe}']+([flag] if flag else []), expected_returncode=int(mode == 'oracle'),
                    validator=dict(source=SELF, function='validate', config=dict(aw=16, p=8, mode=mode), assets={}))
               for mode, flag in (('normal', None), ('oracle', '--negative-oracle'))], full_host=metadata)
    return manifest, files


def dump(path, value):
    with path.open('x') as stream: json.dump(value, stream, indent=2); stream.write('\n')


def prepare(output, budget):
    need(not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE', 'queue/PAUSE')), 'S4_FULL_HOST_PAUSE')
    for name, pin in ((PACKAGE, PACKAGE_SHA), (STAGER, STAGER_SHA), (COMPANION, COMPANION_SHA)):
        need(sha((ROOT/name).read_bytes()) == pin, 'S4_FULL_HOST_SHARED_TOOL_DRIFT '+name)
    budget = Path(budget).resolve(); need(sha(budget.read_bytes()) == BUDGET_SHA, 'S4_FULL_HOST_BUDGET_IDENTITY')
    from fpga.tools import native_class_package_v2 as package
    from fpga.tools import native_class_v1 as executor
    output = Path(output).resolve(); need(not output.exists(), 'S4_FULL_HOST_FRESH_OUTPUT')
    manifest, files = role(); source = output/'input/source/fpga'; source.mkdir(parents=True)
    for name, raw in files.items():
        path = source/name; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream: stream.write(raw)
    path = output/'input/manifest.json'; dump(path, manifest); variants = []
    for pair in ('01', '23'):
        profile = 'gcp-c4d-static'+pair+'-v1'; worker = 's4-aw16-p8-full-host-'+pair+'-v1'; packet = output/('packet-'+pair)
        prepared = package.prepare(path, source, profile, worker, 'run', packet, budget)
        variants.append(dict(profile=profile, worker_id=worker, packet=str(packet), archive=str(packet/'package.tar.gz'),
            sha256=prepared['archive_sha256'], ticket_sha256=prepared['ticket_sha256'],
            manifest_sha256=sha((packet/'manifest.json').read_bytes()), native_root=prepared['native_root'],
            build_key=prepared['build_key'], archive_bytes=prepared['archive_bytes'],
            resource_profile_sha256=sha(canonical_json(executor.profile(profile))), runner=PACKAGE, runner_sha256=PACKAGE_SHA,
            stager=str(ROOT/STAGER), stager_sha256=STAGER_SHA,
            stager_dependencies=[dict(path=str(ROOT/COMPANION), sha256=COMPANION_SHA)], max_seconds=3700))
    first, second = [json.loads((Path(v['packet'])/'manifest.json').read_text()) for v in variants]
    need(all(first[k] == second[k] for k in ('sources', 'build', 'probe', 'steps')), 'S4_FULL_HOST_DUAL_IDENTITY')
    result = dict(schema='s4-full-host-dual-v1', status='source_ready_not_dispatched', variants=variants,
                  source_files=len(first['sources']), source_map_sha256=sha(canonical_json(first['sources'])),
                  full_host=manifest['full_host'], select_exactly_one=True, promotion_allowed=False,
                  HDL_or_native_executed=False, full_N_numeric_locally_performed=False)
    dump(output/'preparation.json', result)
    ticket = dict(schema='gfn16-global-ticket-v1', id=IDENTIFIER, owner='canonical-native-bench',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), priority='P1', kind='sim', needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4), minimum_ram_gib=8,
        minimum_ram_rationale='Full-N paired whole host, peak unmeasured; only admitted8GiB profiles, never4GiB.',
        est_minutes=20, promotion_bound=False, packages=variants,
        after=[DEPENDENCY], on='PASS_expected_contracts')
    dump(output/'global-ticket-v1.json', ticket); verify(); return result


def archive_closure(path, expected):
    """Read bytes only; never extract or execute native products."""
    from pathlib import PurePosixPath
    import tarfile
    seen = set()
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive:
            relative = PurePosixPath(member.name)
            need(member.isfile() and not relative.is_absolute() and '..' not in relative.parts and
                 member.name not in seen and member.name in expected, 'S4_FULL_HOST_ARCHIVE_MEMBER')
            seen.add(member.name)
            need(sha(archive.extractfile(member).read()) == expected[member.name], 'S4_FULL_HOST_ARCHIVE_SHA')
    need(seen == set(expected), 'S4_FULL_HOST_ARCHIVE_CLOSURE'); return len(seen)


def replay():
    import gzip
    from fpga.tools import native_gate_receipt_v1 as gate
    from fpga.tools import global_queue_v1 as queue
    verify(); done = json.loads((ROOT/'queue/done'/f'{IDENTIFIER}.json').read_text())
    result, package = done['result'], done['package']; worker = Path(result['evidence'])/'output/native'
    need(result['status'] == 'needs_independent_review' and result['properties']['ExecMainStatus'] == '0' and
         result['properties']['MainPID'] == '0', 'S4_FULL_HOST_ACTUAL_TERMINAL')
    packet = Path(package['archive']).parent; manifest_path = packet/'manifest.json'
    need(gate.sha(manifest_path) == package['manifest_sha256'] and gate.sha(packet/'package.tar.gz') == package['sha256'],
         'S4_FULL_HOST_SELECTED_PACKAGE')
    manifest = json.loads(manifest_path.read_text()); expected, _ = role()
    need(all(manifest['sources'].get(name) == pin for name, pin in expected['sources'].items()) and
         manifest['full_host'] == expected['full_host'] and manifest['build'] == expected['build'] and
         manifest['probe'] == expected['probe'] and manifest['steps'] == expected['steps'], 'S4_FULL_HOST_FROZEN_CANDIDATE_JOIN')
    selected_identity = queue.functional_identity(package)
    originals = [row for row in done['packages'] if row['profile'].startswith('gcp-c4d-static')]
    need(len(originals) == 2 and all(queue.functional_identity(row) == selected_identity for row in originals),
         'S4_FULL_HOST_LAUNCHER_ONLY_SOURCE_JOIN')
    fresh = gate.validate_result(gate.make_contract(IDENTIFIER, manifest_path), worker/'report.json', id=IDENTIFIER)
    saved_gate = ROOT/'queue/evidence'/IDENTIFIER/'gate-receipt.json'
    need(fresh == json.loads(saved_gate.read_text()) and fresh['status'] == 'PASS_expected_contracts',
         'S4_FULL_HOST_MACHINE_GATE_REPLAY')
    report = json.loads((worker/'report.json').read_text())
    need(report['sources'] == manifest['sources'], 'S4_FULL_HOST_NATIVE_SOURCE_MAP')
    typed = []
    for mode in ('normal', 'oracle'):
        row = next(s for s in report['steps'] if s['name'] == 'full-host-'+mode)
        typed.append(validate((worker/row['log']).read_text(), (worker/row['stderr_log']).read_text(),
                              row['returncode'], dict(aw=16, p=8, mode=mode), {}))
    sources = archive_closure(worker/'sources.tar.gz', report['sources'])
    generated = archive_closure(worker/'generated-sources.tar.gz', report['generated_source_sha256'])
    with gzip.open(worker/'model.gz', 'rb') as stream:
        raw = stream.read(); need(raw[:4] == b'\x7fELF' and sha(raw) == report['executable_sha256'], 'S4_FULL_HOST_ELF_BYTES')
    for key in ('lint_admission', 'build_admission'):
        need(not report[key]['fatal_class_counts'] and not report[key]['unknown_class_counts'] and
             not report[key]['error_streams'], 'S4_FULL_HOST_NO_DEFECT_WAIVER')
    return dict(id=IDENTIFIER, status='PASS_owner_exploration_replay',
        report_sha256=gate.sha(worker/'report.json'), gate_sha256=gate.sha(saved_gate),
        archive_sha256=result['archive_sha256'], properties=result['properties'], invocation=result['properties']['InvocationID'],
        sources=sources, generated=generated, artifacts=len(report['artifacts']), executable_sha256=report['executable_sha256'],
        source_join=dict(candidate_sources=len(expected['sources']), selected_sources=len(manifest['sources']),
                         functional_sha256=selected_identity, launcher_only_additions=True),
        candidate_root_sha256=ROOT_SHA, standalone_generated_sha256=manifest['full_host']['standalone_generated_sha256'],
        typed_results=typed, counts=counts(), native_seconds=report['seconds'],
        steps=[dict(name=s['name'], seconds=s['seconds'], returncode=s['returncode']) for s in report['steps']],
        limits=report['limits'], tool_sha256=report['tool_sha256'],
        style_counts=report['lint_admission']['style_class_counts'], promotion_allowed=False,
        numeric_evidence='Native source-pinned actual candidate/T5b versus independent NTT/CRT/direct canonical assertions, all2N final signed96 words; no raw residue-array dump/offline full-N recomputation.',
        scope='Two bounded host jobs/nine operations only; not full-N PRP, exhaustive faults, physical timing or production promotion.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--budget', type=Path)
    parser.add_argument('--replay', action='store_true'); args = parser.parse_args()
    if args.replay:
        result = replay(); dump(args.output, result)
    else:
        need(args.budget is not None, 'S4_FULL_HOST_PREPARE_BUDGET'); result = prepare(args.output, args.budget)
    print(json.dumps(result, indent=2))
