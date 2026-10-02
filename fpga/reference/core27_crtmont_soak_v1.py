"""Exact-state CRTMont soak inputs and independent boundary replay.

This module does not execute HDL, dispatch jobs, or provision workers. Full-size
integer work is Linux-only and requires gmpy2. The Python-small backend is only
for AW<=8 tooling tests and cannot qualify a native gate. Chunk coverage and an
uninterrupted RTL chain are different evidence classes throughout this file.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/core27_crtmont_soak_v1.py'
BENCH = 'rtl/tb/core27_crtmont_soak_v1.cpp'
HEADER = 'rtl/tb/native_runtime_context_v1.h'
TEST = 'tests/test_core27_crtmont_soak_v1.py'
TOP = 'genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont'
PARENT = 'results/throughput-20260929/core27-rootfused-crtmont64-aws-fit-v1'
PARENT_SHA = '93af1da3453947be920e73ad3f9ead17da3a8249966c7d7db5353f4502f6ece3'
AUDIT = 'results/throughput-20260929/crtmont-96-selected-v1/independent-review-v1.json'
AUDIT_SHA = 'fe70997804d364f0b79058cc00f233e6be01552226568f31aca42bf2bae5708e'
QSF_SHA = '12fdd3fa0053f0d36be2a94cd78a1984ff9d7647daf0eaaec22a5f14ae91e96f'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def text_sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def make_plan(aw=16, squares=1000, chunk_squares=100, checkpoint_every=100,
              seed=20261001, base=604832956, initial='dense'):
    """Only bounded metadata is computed here; safe even for AW16 on a Mac."""
    require(type(aw) is int and 5 <= aw <= 16, 'SOAK_AW_RANGE')
    require(type(base) is int and 2*(1 << aw)+5 <= base <= 1000000000, 'SOAK_BASE_PROFILE')
    require(type(squares) is int and 1 <= squares <= 4096, 'SOAK_FINITE_SQUARES')
    require(type(chunk_squares) is int and 1 <= chunk_squares <= squares, 'SOAK_CHUNK_SIZE')
    require(type(checkpoint_every) is int and 1 <= checkpoint_every <= squares, 'SOAK_CHECKPOINT_PERIOD')
    require(type(seed) is int and 0 <= seed < 1 << 64, 'SOAK_SEED_RANGE')
    require(initial in ('dense', 'zero', 'one', 'minus-one'), 'SOAK_INITIAL_KIND')
    bits = ''.join(str(hashlib.sha256(f'GFNSOAK1-bit:{seed}:{i}'.encode()).digest()[0] & 1)
                   for i in range(squares))
    # Always include normal and double operations in a chain of at least two.
    bits = ('01'+bits[2:]) if squares >= 2 else '0'
    chunks = [dict(index=i//chunk_squares, start=i, end=min(i+chunk_squares, squares))
              for i in range(0, squares, chunk_squares)]
    checkpoints = sorted({0, squares, *range(checkpoint_every, squares, checkpoint_every),
                          *(c['start'] for c in chunks), *(c['end'] for c in chunks)})
    require(aw <= 8 or len(checkpoints) <= 64, 'SOAK_FULL_REFERENCE_CHECKPOINT_CAP')
    spec = dict(schema='crtmont-soak-plan-v1', lineage='promoted-crtmont',
        parent_manifest_sha256=PARENT_SHA, parent_audit_sha256=AUDIT_SHA,
        profile=dict(aw=aw, n=1 << aw, base=base, ntt_lanes=64,
                     carry='inherited-precision', base_floor=2*(1 << aw)+5),
        seed=seed, initial=initial, initial_algorithm='sha256-per-base-digit-v1',
        double_algorithm='sha256-per-operation-low-bit-v1-first-bits-01',
        squares=squares, chunk_squares=chunk_squares, checkpoint_every=checkpoint_every,
        double_bits=bits, checkpoints=checkpoints, chunks=chunks)
    spec['case_id'] = hashlib.sha256(canonical(spec)).hexdigest()
    return spec


def check_plan(plan):
    expected = make_plan(aw=plan['profile']['aw'], squares=plan['squares'],
        chunk_squares=plan['chunk_squares'], checkpoint_every=plan['checkpoint_every'],
        seed=plan['seed'], base=plan['profile']['base'], initial=plan['initial'])
    require(plan == expected, 'SOAK_EXACT_PLAN_IDENTITY')
    return plan


def parent_sources():
    """Read-only identity gate on the promoted, archived sixteen-source parent."""
    parent = ROOT/PARENT
    require(sha(parent/'manifest.json') == PARENT_SHA and sha(parent/'probe.qsf') == QSF_SHA,
            'SOAK_PROMOTED_PARENT_IDENTITY')
    require(sha(ROOT/AUDIT) == AUDIT_SHA, 'SOAK_PROMOTED_AUDIT_IDENTITY')
    manifest = json.loads((parent/'manifest.json').read_text())
    audit = json.loads((ROOT/AUDIT).read_text())
    require(audit['status'] == 'passed_independent_local_archive_review_scoped_internal_sta_crtmont96'
        and audit['source_manifest_sha256'] == PARENT_SHA
        and audit['source_sha256'] == manifest['source_sha256'], 'SOAK_PROMOTED_AUDIT_BINDING')
    order = re.findall(r'^set_global_assignment -name SYSTEMVERILOG_FILE rtl/(\S+)$',
                       (parent/'probe.qsf').read_text(), re.M)
    require(len(order) == 16 and set(order) == set(manifest['source_sha256']), 'SOAK_RTL_CLOSURE')
    pins = {}
    for name in order:
        relative = 'rtl/kernel/'+name
        digest = manifest['source_sha256'][name]
        require(sha(parent/'rtl'/name) == digest == sha(ROOT/relative), 'SOAK_RTL_DRIFT '+name)
        pins[relative] = digest
    return order, pins


def backend(aw, engine):
    require(engine in ('gmpy2', 'python-small-only'), 'SOAK_ORACLE_ENGINE')
    require(aw <= 8 or platform.system() == 'Linux', 'SOAK_FULL_INTEGER_LINUX_ONLY')
    if engine == 'python-small-only':
        require(aw <= 8, 'SOAK_SMALL_BACKEND_EXTENT')
        return int, dict(engine=engine, native_qualification_allowed=False)
    import gmpy2
    return gmpy2.mpz, dict(engine='gmpy2', version=gmpy2.version(),
        gmp_version=gmpy2.mp_version(), module_sha256=sha(gmpy2.__file__),
        python_sha256=sha(Path(sys.executable).resolve()),
        module_files_sha256={name:sha(module.__file__) for name, module in sorted(sys.modules.items())
            if (name == 'gmpy2' or name.startswith('gmpy2.')) and getattr(module, '__file__', None)},
        platform=platform.system(), native_qualification_allowed=platform.system() == 'Linux')


def initial_digits(plan):
    n, base, seed = plan['profile']['n'], plan['profile']['base'], plan['seed']
    if plan['initial'] != 'dense':
        return [dict(zero=0, one=1, **{'minus-one': -1})[plan['initial']]]+[0]*(n-1)
    return [int.from_bytes(hashlib.sha256(f'GFNSOAK1-digit:{seed}:{i}'.encode()).digest()[:8], 'big') % base
            for i in range(n)]


def digit_tools(base, n, integer):
    """Balanced radix conversion keeps full-N reference generation practical."""
    powers = {1: integer(base)}
    width = 2
    while width <= n:
        powers[width] = powers[width//2]*powers[width//2]
        width *= 2
    modulus = powers[n]+1

    def decode(values):
        require(len(values) == n and all(type(v) is int for v in values), 'SOAK_DIGIT_EXTENT')
        require(values == [-1]+[0]*(n-1) or all(0 <= v < base for v in values), 'SOAK_CANONICAL_ENCODING')
        def join(start, count):
            if count == 1:
                return integer(values[start])
            half = count//2
            return join(start, half)+powers[half]*join(start+half, half)
        return join(0, n) % modulus

    def encode(value):
        require(0 <= value < modulus, 'SOAK_RESIDUE_RANGE')
        if value == modulus-1:
            return [-1]+[0]*(n-1)
        def split(x, count):
            if count == 1:
                return [int(x)]
            half = count//2
            high, low = divmod(x, powers[half])
            return split(low, half)+split(high, half)
        return split(value, n)
    return modulus, encode, decode


def residue_sha(value):
    value = int(value)
    return hashlib.sha256(value.to_bytes(max(1, (value.bit_length()+7)//8), 'big')).hexdigest()


def compute_states(plan, engine, end, checkpoints):
    """Compute one prefix; only materialize boundaries needed by this replay."""
    check_plan(plan)
    require(type(end) is int and 1 <= end <= plan['squares'] and checkpoints
        and set(checkpoints) <= set(plan['checkpoints']) and min(checkpoints) >= 0 and max(checkpoints) <= end,
        'SOAK_REFERENCE_PREFIX')
    integer, provenance = backend(plan['profile']['aw'], engine)
    modulus, encode, decode = digit_tools(plan['profile']['base'], plan['profile']['n'], integer)
    value = decode(initial_digits(plan))
    states = {0: dict(step=0, digits=encode(value), residue_sha256=residue_sha(value))} if 0 in checkpoints else {}
    initial_value = value
    double_exponent = 0
    for step, bit in enumerate(plan['double_bits'][:end], 1):
        value = value*value*(2 if bit == '1' else 1) % modulus
        double_exponent = 2*double_exponent+int(bit)
        if step in checkpoints:
            values = encode(value)
            require(decode(values) == value, 'SOAK_ORACLE_RADIX_ROUNDTRIP')
            states[step] = dict(step=step, digits=values, residue_sha256=residue_sha(value))
    # Small tooling cases have an additional exponent-form check. Avoid an
    # unnecessary second 1000-square full-N workload in the production oracle.
    direct_checked = plan['profile']['aw'] <= 8
    if direct_checked:
        direct = pow(initial_value, 1 << end, modulus)*pow(integer(2), double_exponent, modulus) % modulus
        require(direct == value, 'SOAK_INDEPENDENT_SCHEDULE_CHECK')
    provenance.update(method='x <- x*x*2**bit modulo base**n+1; no NTT/RNS/carry model',
        schedule_exponent_crosscheck=direct_checked, modulus_sha256=residue_sha(modulus))
    return states, provenance


def corpus(plan, engine='gmpy2'):
    """Generate every exact chunk start/end from one independent integer chain."""
    states, provenance = compute_states(plan, engine, plan['squares'], plan['checkpoints'])
    result = {}
    segments = [('continuous', 0, plan['squares'], 'continuous')]
    segments.extend((f"chunk-{c['index']:02d}", c['start'], c['end'], 'chunk') for c in plan['chunks'])
    for name, start, end, mode in segments:
        checks = [states[k] for k in plan['checkpoints'] if start <= k <= end]
        bits = plan['double_bits'][start:end]
        lines = [f"GFNSOAK1 {plan['profile']['aw']} {plan['profile']['base']} {start} {end} {len(checks)} {mode} {plan['case_id']}",
                 'BITS '+bits]
        for check in checks:
            lines.append('CHECK '+str(check['step'])+' '+' '.join(map(str, check['digits'])))
        text = '\n'.join(lines)+'\n'
        oracle = dict(schema='crtmont-soak-segment-v1', status='generated_reference_not_native_evidence',
            plan=plan, oracle=provenance, segment=dict(name=name, mode=mode, start=start, end=end,
                operations=end-start, doubles=bits.count('1'), double_bits=bits, checkpoints=checks,
                reset_count=1, loaded_digits=plan['profile']['n']), corpus_sha256=text_sha(text))
        result[name] = (text, oracle)
    return result


def generate(output, plan, engine='gmpy2'):
    require(not (ROOT/'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    output = Path(output).resolve()
    require(not output.exists(), 'SOAK_FRESH_REFERENCE_OUTPUT')
    # The platform/backend guard precedes any full-size work or output creation.
    backend(plan['profile']['aw'], engine)
    begin = time.monotonic()
    items = corpus(plan, engine)
    _, parent_pins = parent_sources()
    output.mkdir(parents=True)
    files = {}
    for name, (text, oracle) in items.items():
        oracle['parent_source_sha256'] = parent_pins
        for suffix, content in (('.txt', text), ('.json', json.dumps(oracle, indent=2)+'\n')):
            path = output/(name+suffix)
            with path.open('x') as stream:
                stream.write(content)
            files[path.name] = sha(path)
    with (output/'plan.json').open('x') as stream:
        stream.write(json.dumps(plan, indent=2)+'\n')
    files['plan.json'] = sha(output/'plan.json')
    receipt = dict(schema='crtmont-soak-reference-generation-v1', status='reference_generated_not_executed',
        files=files, case_id=plan['case_id'], seconds=time.monotonic()-begin,
        generator_sha256=sha(ROOT/SELF), parent_source_sha256=parent_pins,
        oracle=items['continuous'][1]['oracle'],
        gates=dict(chunked_arithmetic_coverage='not_run', uninterrupted_1000_square_rtl='not_run'),
        limitation='Exact reference inputs only. Chunked RTL never replaces the uninterrupted RTL gate.')
    with (output/'generation.json').open('x') as stream:
        stream.write(json.dumps(receipt, indent=2)+'\n')
    return receipt


def check_oracle(oracle):
    require(oracle['schema'] == 'crtmont-soak-segment-v1'
            and oracle['status'] == 'generated_reference_not_native_evidence', 'SOAK_ORACLE_SCHEMA')
    plan = check_plan(oracle['plan'])
    segment = oracle['segment']
    start, end = segment['start'], segment['end']
    expected = [('continuous', 0, plan['squares'], 'continuous')]+[
        (f"chunk-{c['index']:02d}", c['start'], c['end'], 'chunk') for c in plan['chunks']]
    require((segment['name'], start, end, segment['mode']) in expected, 'SOAK_SEGMENT_IDENTITY')
    bits = plan['double_bits'][start:end]
    require(segment['double_bits'] == bits and segment['operations'] == end-start
        and segment['doubles'] == bits.count('1') and segment['reset_count'] == 1
        and segment['loaded_digits'] == plan['profile']['n'], 'SOAK_SEGMENT_ACCOUNTING')
    require([c['step'] for c in segment['checkpoints']] == [k for k in plan['checkpoints'] if start <= k <= end],
            'SOAK_ALL_BOUNDARIES_REQUIRED')
    return plan, segment


def validate_rows(stdout, stderr, returncode, config, oracle):
    """Pure log contract, also usable by scalar tooling tests without gmpy2.

    Only validate() is the native adapter: it first demands and recomputes the
    independent gmpy2 reference. Passing this parser alone is not a native gate.
    """
    plan, segment = check_oracle(oracle)
    require(set(config) == {'negative'} and config['negative'] in ('none', 'boundary', 'loaded-state'),
            'SOAK_VALIDATOR_CONFIG')
    require(stdout.endswith('\n'), 'SOAK_LOG_TERMINATION')
    rows = []
    for line in stdout.splitlines():
        prefix, separator, payload = line.partition(' ')
        require(separator and prefix in ('SOAK_STEP', 'SOAK_CHECK', 'SOAK_PASS'), 'SOAK_LOG_SCHEMA')
        rows.append((prefix, json.loads(payload)))
    cursor, total_cycles, checks, operations, doubles = 0, 0, 0, 0, 0
    negative = config['negative']
    target = segment['start'] if negative == 'loaded-state' else segment['checkpoints'][1]['step']
    for check in segment['checkpoints']:
        while operations < check['step']-segment['start']:
            require(cursor < len(rows) and rows[cursor][0] == 'SOAK_STEP', 'SOAK_OPERATION_COVERAGE')
            row = rows[cursor][1]
            step = segment['start']+operations+1
            bit = int(segment['double_bits'][operations])
            keys = {'case_id', 'step', 'bit', 'cycles', 'conversion', 'roots', 'ntt', 'crt', 'carry', 'profile_loads', 'profile_hits'}
            require(set(row) == keys and row['case_id'] == plan['case_id'] and row['step'] == step
                and row['bit'] == bit and all(type(row[k]) is int for k in keys-{'case_id'}), 'SOAK_OPERATION_IDENTITY')
            require(0 < row['cycles'] <= 65536+64*plan['profile']['n']
                and all(row[k] >= 0 for k in ('conversion', 'roots', 'ntt', 'crt', 'carry'))
                and row['cycles'] == sum(row[k] for k in ('conversion', 'roots', 'ntt', 'crt', 'carry')),
                'SOAK_CYCLE_ACCOUNTING')
            require((row['profile_loads'], row['profile_hits']) == ((1, 0) if operations == 0 else (0, 1)),
                    'SOAK_PERSISTENT_PROFILE_CACHE')
            total_cycles += row['cycles']; operations += 1; doubles += bit; cursor += 1
        require(cursor < len(rows) and rows[cursor][0] == 'SOAK_CHECK', 'SOAK_CHECKPOINT_COVERAGE')
        row = rows[cursor][1]
        require(set(row) == {'case_id', 'step', 'digits'} and row['case_id'] == plan['case_id']
            and row['step'] == check['step'] and type(row['step']) is int
            and all(type(v) is int for v in row['digits']), 'SOAK_CHECKPOINT_IDENTITY')
        expected_digits = check['digits']
        if negative == 'loaded-state' and check['step'] == target:
            expected_digits = list(expected_digits)
            expected_digits[0] = 0 if expected_digits[0] == -1 else (expected_digits[0]+1) % plan['profile']['base']
        require(row['digits'] == expected_digits, 'SOAK_EXACT_BOUNDARY_RESIDUE')
        cursor += 1; checks += 1
        if negative != 'none' and check['step'] == target:
            require(cursor == len(rows) and returncode == 1
                and stderr == f'SOAK_BOUNDARY_MISMATCH step={target} digit=0\n', 'SOAK_NEGATIVE_BOUNDARY_CONTRACT')
            return dict(status='passed_matched_soak_negative', negative=negative,
                case_id=plan['case_id'], step=target, native_qualification_allowed=False,
                limitation='Host loaded-state or comparator control; not an RTL arithmetic mutant.')
    expected_footer = dict(case_id=plan['case_id'], mode=segment['mode'], start=segment['start'], end=segment['end'],
        operations=operations, doubles=doubles, readbacks=checks, cycles=total_cycles,
        resets=1, loaded_digits=plan['profile']['n'], cold=1, warm=operations-1)
    require(returncode == 0 and stderr == '' and cursor+1 == len(rows)
        and rows[cursor] == ('SOAK_PASS', expected_footer)
        and all(type(v) is int for k, v in rows[cursor][1].items() if k not in ('case_id', 'mode')), 'SOAK_FINAL_ACCOUNTING')
    continuous_gate = segment['mode'] == 'continuous' and plan['profile']['aw'] == 16 and operations >= 1000
    return dict(status='passed_soak_segment_boundary_replay', case_id=plan['case_id'], segment=segment['name'],
        operations=operations, doubles=doubles, readbacks=checks, cycles=total_cycles,
        evidence_class='uninterrupted_full_n_rtl_soak' if continuous_gate else (
            'checkpoint_chunk_arithmetic_coverage' if segment['mode'] == 'chunk' else 'short_native_soak_smoke'),
        checkpoint_residue_sha256={str(c['step']):c['residue_sha256'] for c in segment['checkpoints']},
        continuous_chain_log_contract=continuous_gate, uninterrupted_1000_square_rtl=False,
        native_qualification_allowed=False, promotion_allowed=False,
        limitation='Log contract only until validate() completes gmpy2 replay and the shared worker source/tool/resource evidence is checked.')


def validate(stdout, stderr, returncode, config, assets):
    """Shared native packager adapter; assets are source-pinned text bytes."""
    require(set(config) == {'negative'} and config['negative'] in ('none', 'boundary', 'loaded-state'),
            'SOAK_VALIDATOR_CONFIG')
    require(set(assets) == {'oracle'}, 'SOAK_VALIDATOR_ASSETS')
    oracle = json.loads(assets['oracle'])
    plan, segment = check_oracle(oracle)
    require(oracle['oracle']['engine'] == 'gmpy2' and oracle['oracle']['native_qualification_allowed']
        and oracle['oracle']['platform'] == 'Linux', 'SOAK_NATIVE_GMPY2_REFERENCE_REQUIRED')
    # Recompute every boundary independently instead of accepting the packaged
    # expected arrays as the oracle. The independent reviewer repeats this too.
    wanted = [check['step'] for check in segment['checkpoints']]
    # Replay only the necessary prefix, encoding this segment's boundaries.
    # It derives a chunk's start from x0; it does not trust a loaded checkpoint.
    states, provenance = compute_states(plan, 'gmpy2', segment['end'], wanted)
    require([states[k] for k in wanted] == segment['checkpoints'], 'SOAK_REFERENCE_BOUNDARY_REPLAY')
    require(provenance == oracle['oracle'], 'SOAK_EXACT_REFERENCE_TOOL_IDENTITY')
    result = validate_rows(stdout, stderr, returncode, config, oracle)
    result.update(independent_gmpy2_boundary_replay=True, oracle_sha256=text_sha(assets['oracle']),
                  normal_log_sha256=text_sha(stdout), parent_manifest_sha256=PARENT_SHA)
    if config['negative'] == 'none':
        result['native_qualification_allowed'] = True
        result['uninterrupted_1000_square_rtl'] = result['continuous_chain_log_contract']
    return result


def combine_chunks(plan, results):
    """Account for every chunk; cannot convert chunk receipts into a soak pass."""
    check_plan(plan)
    require(len(results) == len(plan['chunks']), 'SOAK_ALL_CHUNKS_REQUIRED')
    by_name = {row['segment']:row for row in results}
    require(len(by_name) == len(results), 'SOAK_DUPLICATE_CHUNK')
    boundary_hashes = {}
    for chunk in plan['chunks']:
        name = f"chunk-{chunk['index']:02d}"
        require(name in by_name, 'SOAK_CHUNK_COVERAGE')
        row = by_name[name]
        require(row['status'] == 'passed_soak_segment_boundary_replay' and row['case_id'] == plan['case_id']
            and row['evidence_class'] == 'checkpoint_chunk_arithmetic_coverage'
            and row['independent_gmpy2_boundary_replay'] is True and row['uninterrupted_1000_square_rtl'] is False
            and row['native_qualification_allowed'] is True
            and row['parent_manifest_sha256'] == PARENT_SHA
            and row['operations'] == chunk['end']-chunk['start'], 'SOAK_CHUNK_REPLAY_CONTRACT')
        keys = [str(k) for k in plan['checkpoints'] if chunk['start'] <= k <= chunk['end']]
        require(sorted(row['checkpoint_residue_sha256'], key=int) == keys, 'SOAK_CHUNK_BOUNDARIES')
        for step, digest in row['checkpoint_residue_sha256'].items():
            require(re.fullmatch('[0-9a-f]{64}', digest) and (step not in boundary_hashes or boundary_hashes[step] == digest),
                    'SOAK_ADJACENT_CHUNK_STATE_IDENTITY')
            boundary_hashes[step] = digest
    return dict(status='passed_chunked_arithmetic_chain_coverage', case_id=plan['case_id'], chunks=len(results),
        operations=sum(row['operations'] for row in results), boundary_residue_sha256=boundary_hashes,
        uninterrupted_1000_square_rtl=False, continuous_gate='still_required', promotion_allowed=False,
        limitation='Every independently loaded chunk boundary agrees. Persistent controller/cache/counter bugs require the separate uninterrupted RTL run.')


def stage_segment(reference_dir, name, output, host, remote_root, runtime_threads=1):
    """Make a packageable closed snapshot, then use tools/native_package_v1.py."""
    require(not (ROOT/'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    reference_dir, output = Path(reference_dir).resolve(), Path(output).resolve()
    require(not output.exists(), 'SOAK_FRESH_STAGE')
    require(type(runtime_threads) is int and runtime_threads in (1, 2, 4, 8), 'SOAK_RUNTIME_THREADS')
    require(re.fullmatch(r'(continuous|chunk-[0-9]{2,4})', name), 'SOAK_SEGMENT_NAME')
    generation = json.loads((reference_dir/'generation.json').read_text())
    require(generation['generator_sha256'] == sha(ROOT/SELF), 'SOAK_GENERATOR_IDENTITY')
    for file, digest in generation['files'].items():
        require(sha(reference_dir/file) == digest, 'SOAK_REFERENCE_FILE_DRIFT')
    oracle = json.loads((reference_dir/(name+'.json')).read_text())
    plan, segment = check_oracle(oracle)
    require(generation['case_id'] == plan['case_id'] and text_sha((reference_dir/(name+'.txt')).read_text()) == oracle['corpus_sha256'],
            'SOAK_CORPUS_CASE_BINDING')
    require(oracle['oracle']['engine'] == 'gmpy2' and oracle['oracle']['native_qualification_allowed'], 'SOAK_NATIVE_REFERENCE_ONLY')
    require(plan['profile']['aw'] > 8 or runtime_threads == 1, 'SOAK_SHORT_AW_SINGLE_THREAD')
    require(Path(remote_root).is_absolute() and '..' not in Path(remote_root).parts, 'SOAK_REMOTE_ROOT')
    order, pins = parent_sources()
    require(oracle['parent_source_sha256'] == pins == generation['parent_source_sha256'], 'SOAK_REFERENCE_PARENT_BINDING')
    for file in (SELF, BENCH, HEADER, TEST):
        pins[file] = sha(ROOT/file)
    source = output/'source/fpga'
    source.mkdir(parents=True)
    for file, digest in pins.items():
        require(not (ROOT/file).is_symlink(), 'SOAK_SOURCE_SYMLINK')
        target = source/file; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/file, target); require(sha(target) == digest, 'SOAK_CAPTURE_DRIFT')
    require(all(sha(ROOT/file) == digest for file, digest in pins.items()), 'SOAK_LIVE_SOURCE_DRIFT')
    for suffix in ('.txt', '.json'):
        file = 'soak/'+name+suffix
        target = source/file; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(reference_dir/(name+suffix), target); pins[file] = sha(target)
    validator = dict(source=SELF, function='validate', config=dict(negative='none'), assets={'oracle':'soak/'+name+'.json'})
    steps = []
    for label, negative in (('normal', 'none'), ('negative-boundary', 'boundary'), ('negative-loaded-state', 'loaded-state')):
        argv = ['{exe}', '{root}/soak/'+name+'.txt']
        if negative != 'none':
            argv.append('--negative-'+negative)
        contract = json.loads(json.dumps(validator)); contract['config']['negative'] = negative
        steps.append(dict(name='soak-'+label, argv=argv, expected_returncode=0 if negative == 'none' else 1, validator=contract))
    manifest = dict(schema='native-source-gate-v1', status='prepared_not_executed', host=host,
        source_root=remote_root+'/snapshot/fpga', output_parent=remote_root, sources=pins,
        build=dict(top=TOP, sv_sources=['rtl/kernel/'+file for file in order], cpp_source=BENCH,
            parameters=dict(AW=plan['profile']['aw'], NTT_LANES=64),
            runtime_threads=runtime_threads,
            cflags=['-std=c++17', '-Werror=return-type', f"-DGFN16_SOAK_AW={plan['profile']['aw']}",
                    f'-DGFN16_RUNTIME_THREADS={runtime_threads}']),
        probe=dict(argv=['{exe}', '--runtime-probe'], expected_json=dict(context_threads=runtime_threads,
            model_threads=runtime_threads, expected_threads=runtime_threads)), steps=steps,
        model_threads=runtime_threads, parent_manifest_sha256=PARENT_SHA, parent_audit_sha256=AUDIT_SHA,
        soak=dict(case_id=plan['case_id'], seed=plan['seed'], profile=plan['profile'], segment=segment['name'],
            reference_generation_sha256=sha(reference_dir/'generation.json'),
            requested_gate='uninterrupted_1000_square_rtl' if segment['mode'] == 'continuous' and segment['operations'] >= 1000
                and plan['profile']['aw'] == 16 else 'chunked_arithmetic_coverage' if segment['mode'] == 'chunk' else 'short_smoke'),
        scope='Exact promoted CRTMont parent, generic load/square/readback host driver. No RTL change, no T5b promotion.')
    with (output/'manifest.json').open('x') as stream:
        stream.write(json.dumps(manifest, indent=2)+'\n')
    receipt = dict(status='staged_not_dispatched', manifest_sha256=sha(output/'manifest.json'), sources=pins,
        case_id=plan['case_id'], segment=name, source_root=str(source),
        limitations=['Use the shared packager and admitted host/slot profile; this function grants no spending or dispatch authority.',
            'AW16 runtime/cost/resource contract and native short gate must pass before long or parallel tickets.',
            'Chunked arithmetic coverage and uninterrupted >=1000 squares are separate required gates.'])
    with (output/'stage.json').open('x') as stream:
        stream.write(json.dumps(receipt, indent=2)+'\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    plan_parser = commands.add_parser('plan')
    generate_parser = commands.add_parser('generate')
    for sub in (plan_parser, generate_parser):
        sub.add_argument('--aw', type=int, default=16); sub.add_argument('--squares', type=int, default=1000)
        sub.add_argument('--chunk-squares', type=int, default=100); sub.add_argument('--checkpoint-every', type=int, default=100)
        sub.add_argument('--seed', type=int, default=20261001); sub.add_argument('--base', type=int, default=604832956)
        sub.add_argument('--initial', choices=['dense', 'zero', 'one', 'minus-one'], default='dense')
    generate_parser.add_argument('--output', type=Path, required=True)
    generate_parser.add_argument('--engine', choices=['gmpy2', 'python-small-only'], default='gmpy2')
    stage = commands.add_parser('stage')
    stage.add_argument('--references', type=Path, required=True); stage.add_argument('--segment', required=True)
    stage.add_argument('--output', type=Path, required=True); stage.add_argument('--host', required=True)
    stage.add_argument('--remote-root', required=True); stage.add_argument('--runtime-threads', type=int, default=1)
    args = parser.parse_args()
    if args.command in ('plan', 'generate'):
        plan = make_plan(args.aw, args.squares, args.chunk_squares, args.checkpoint_every, args.seed, args.base, args.initial)
        result = plan if args.command == 'plan' else generate(args.output, plan, args.engine)
    else:
        result = stage_segment(args.references, args.segment, args.output, args.host, args.remote_root, args.runtime_threads)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
