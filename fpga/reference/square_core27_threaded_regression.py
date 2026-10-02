"""Opt-in exact-context threads1/8 for future atomic27 correctness regressions.

Frozen RTL, oracle, bench and prior harnesses are inputs, never edited. Only
executables are cached; every runtime probe and bigint oracle executes afresh.
"""
import argparse
import hashlib
import json
from math import prod
import os
from pathlib import Path
import platform
import re
import resource
import shlex
import shutil
import signal
import subprocess
import sys
import time
from .build_cache import BuildProduct, BuildSpec
from .rns_reference import RADIX, RNSPrime
from .square_core27_regression import write_vectors
from .square_core27_recovery import segments
from .square_core_regression import cache_context

TOP = 'genefer_square_core27'
NAMES = ['genefer_montgomery_mul32_pipe', 'genefer_montgomery_mul27_sparse_pipe',
         'genefer_digit_reduce27_pipe', 'genefer_sdp_ram32', 'genefer_ntt_banked27_engine',
         'genefer_ntt_banked27_host_engine', 'genefer_mod64_pipe', 'genefer_crt3_27_pipe',
         'genefer_carry_transfer_tree', 'genefer_sp_ram', 'genefer_div_recip_narrow',
         'genefer_carry_prefix_vector_pipe_v2', TOP]
DEFECTS = [
    ('raw-truncate', '.digit(carry_words[h][31:0])', ".digit({5'b0,carry_words[h][26:0]})"),
    ('convert-radix', '.rhs(R2[f])', ".rhs(32'd1)"),
    ('conversion-word', '.digit(carry_words[h][31:0])', '.digit(carry_words[0][31:0])'),
    ('root-order', '.GENERATOR(G[f])', ".GENERATOR(32'd1)"),
    ('inverse-phase', "step==3 ? 2'd2 : 2'd3", "step==3 ? 2'd1 : 2'd3"),
    ('double', 'double_reg ? (coefficient_words[h] <<< 1) : coefficient_words[h]', 'coefficient_words[h]'),
    ('coefficient-row', "AW'(issue_count) : AW'(write_count);", "AW'(issue_count) : AW'(write_count+IO_STEP);"),
    ('digit-base', "carry_words[h]>=$signed({64'd0,base_reg})", "carry_words[h]>$signed({64'd0,base_reg})"),
    ('cache-reset', 'root_phases_loaded<=0; root_cache_hits<=0; root_cache_valid<=0;',
     'root_phases_loaded<=0; root_cache_hits<=0; root_cache_valid<=15;'),
    ('cache-reload', 'ROOT_CACHE && root_cache_valid[0]', "1'b0"),
    ('immediate-start', 'IDLE: if(start) begin', 'IDLE: if(start && !done) begin'),
    ('reducer-error', 'assign reduction_error[f]=|reduce_error_words[f];',
     'assign reduction_error[f]=(|reduce_error_words[f]) || (state==CONVERT && convert_input_valid);'),
    ('wrong-r2', "32'd45971250,32'd50081300,32'd63576045", "32'd45971250,32'd50081300,32'd63576046"),
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_configuration(aw, lanes, threads, ordered_sources, mutation=False):
    if type(threads) is not int or threads not in (1, 8):
        raise ValueError('runtime threads must be exactly1 or8')
    if type(aw) is not int or not 1 <= aw <= 16 or lanes not in (16, 64):
        raise ValueError('unsupported atomic27 profile')
    cflags = f'-DCORE27_RUNTIME_THREADS={threads}' + (' -O0' if mutation else '')
    flags = ['--cc', '--exe', '--build', '-j', '2', '--threads', str(threads),
             '--top-module', TOP, f'-GAW={aw}', f'-GNTT_LANES={lanes}', '-CFLAGS', cflags]
    return dict(flags=flags, runtime_threads=threads, context_threads=threads,
                model_threads=threads, compile_workers=2, memory_limit_bytes=6 << 30,
                ordered_sources=list(map(str, ordered_sources)),
                build_directory='<private-stage>', executable='V' + TOP)


def validate_configuration(config):
    threads = config['runtime_threads']
    if type(threads) is not int or threads not in (1, 8):
        raise ValueError('invalid cached runtime count')
    if config['context_threads'] != threads or config['model_threads'] != threads:
        raise ValueError('context/model/runtime mismatch')
    flags = config['flags']
    if flags.count('--threads') != 1 or flags[flags.index('--threads') + 1] != str(threads):
        raise ValueError('Verilator thread flag mismatch')
    macros = re.findall(r'(?:^|\s)-DCORE27_RUNTIME_THREADS=(\S+)', ' '.join(flags))
    if macros != [str(threads)]:
        raise ValueError('context macro mismatch')
    if config['compile_workers'] != 2 or flags.count('-j') != 1 or flags[flags.index('-j') + 1] != '2':
        raise ValueError('compile workers changed with runtime threads')
    if config['memory_limit_bytes'] != 6 << 30:
        raise ValueError('memory cap changed with runtime threads')


def check_probe(output, expected):
    try:
        actual = json.loads(output)
    except (ValueError, TypeError) as error:
        raise ValueError('invalid runtime-thread probe') from error
    wanted = {name: expected for name in ('context_threads', 'model_threads', 'expected_threads')}
    if actual != wanted or any(type(value) is not int for value in actual.values()):
        raise ValueError('executable thread identity mismatch')


def independent_profile(core):
    assert RADIX == 1 << 32
    basis = [RNSPrime(f'P27_{i}', p, pow(p, -1, RADIX), RADIX % p, RADIX * RADIX % p, g)
             for i, (p, g) in enumerate(((104857601, 3), (69206017, 5), (67239937, 10)))]
    for prime in basis:
        prime.validate()
        for aw in range(1, 17):
            prime.primitive_root(2 << aw)
    maximum = 2 * 65536 * 999999999**2
    modulus = prod(prime.p for prime in basis)
    assert modulus > 2 * maximum
    for label, attribute in (('P', 'p'), ('Q', 'q'), ('R2', 'r2'), ('G', 'generator')):
        line = next(line for line in core.read_text().splitlines() if f'{label}[0:2]' in line)
        assert list(map(int, re.findall(r"32'd(\d+)", line))) == [getattr(p, attribute) for p in basis]
    return maximum, modulus


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--aw', type=int, nargs='+', default=[1, 5, 16])
    parser.add_argument('--lanes', type=int, choices=[16, 64], default=16)
    parser.add_argument('--runtime-threads', type=int, choices=[1, 8], default=1)
    parser.add_argument('--build-cache', type=Path)
    parser.add_argument('--compile-lock', type=Path)
    parser.add_argument('--seed', type=int, default=20260929)
    parser.add_argument('--mutations', action='store_true')
    parser.add_argument('--thread-contract-tests', action='store_true')
    args = parser.parse_args()
    if platform.node() != 'aethia':
        raise RuntimeError('aethia only')
    if any(not 1 <= aw <= 16 for aw in args.aw) or len(set(args.aw)) != len(args.aw):
        raise ValueError('AW values must be distinct and within1..16')
    if len(os.sched_getaffinity(0)) < args.runtime_threads:
        raise RuntimeError('runtime thread count exceeds eligible CPU count')
    resource.setrlimit(resource.RLIMIT_AS, (6 << 30, 6 << 30))
    root = Path(__file__).resolve().parents[1]
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    sources = [root / 'rtl/kernel' / (name + '.sv') for name in NAMES]
    wrapper = root / 'rtl/tb/square_core27_threaded.cpp'
    bench = root / 'rtl/tb/square_core27.cpp'
    helpers = [Path(__file__), root / 'reference/square_core27_regression.py',
               root / 'reference/square_core27_recovery.py', root / 'reference/square_core_regression.py',
               root / 'reference/build_cache.py', root / 'reference/rns_reference.py',
               root / 'tests/test_core27_runtime_threads.py']
    originals = {str(path.relative_to(root)): digest(path) for path in [*sources, wrapper, bench, *helpers]}
    maximum, modulus = independent_profile(sources[-1])
    report = dict(status='running', host=platform.node(), radix_bits=32,
                  ancestor_sha256='c6dad925fe58c17074722aabfee1d757232552465ecf0026fcc078373e08d5db',
                  profiles=[[args.lanes, 16]], runtime_threads=args.runtime_threads,
                  context_threads=args.runtime_threads, model_threads=args.runtime_threads,
                  compile_workers=2, memory_limit_bytes=6 << 30, command_timeout_seconds=600,
                  runtime_affinity=sorted(os.sched_getaffinity(0)), max_doubled_coefficient=maximum,
                  crt_modulus=modulus, sources=originals, mutation_sources={}, vectors={},
                  steps=[], build_cache=[], builds=[], metrics=[], segment_provenance=[])
    def run(name, command, reject=None):
        before = time.monotonic()
        process = subprocess.Popen(command, cwd=root, text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        timed_out = False
        try:
            output, _ = process.communicate(timeout=600)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            output, _ = process.communicate()
        log = out / (name + '.log')
        log.write_text(output)
        report['steps'].append(dict(name=name, command=command, returncode=process.returncode,
            seconds=time.monotonic()-before, timed_out=timed_out, rejection=reject is not None,
            evidence_log=str(log)))
        print(name, process.returncode, output[-650:], flush=True)
        if timed_out:
            raise RuntimeError(name + ' hit unchanged600-second cap')
        if reject is None:
            if process.returncode:
                raise RuntimeError(name + ' failed')
        elif not process.returncode or not any(message in output for message in reject):
            raise RuntimeError(name + ' rejection escaped')
        return output
    cache = None
    def build(name, aw, lanes=None, selected=None, mutation=False):
        actual = sources if selected is None else selected
        ordered = [*actual, wrapper]
        config = build_configuration(aw, lanes or args.lanes, args.runtime_threads, ordered, mutation)
        config['cwd'] = str(root)
        validate_configuration(config)
        def compile_into(target):
            if aw == 16 and shutil.disk_usage(out).free < 10 << 30:
                raise RuntimeError('no new full-N build below10 GiB free disk')
            command = ['verilator', *config['flags'], '--Mdir', str(target), *map(str, ordered)]
            if args.compile_lock:
                command = ['flock', '--timeout', '600', str(args.compile_lock.resolve()), *command]
            run(name, command)
        if cache is None:
            directory = out / name
            compile_into(directory)
            executable = directory / ('V' + TOP)
        else:
            tracked = [*ordered, bench, *helpers]
            spec = BuildSpec.capture(sources={f'source_{i:02}': path for i, path in enumerate(tracked)},
                                     configuration=config, toolchain=toolchain, environment=environment)
            def cached_compile(target):
                compile_into(target)
                dependencies = set()
                for path in target.glob('*.d'):
                    for line in path.read_text().replace('\\\n', ' ').splitlines():
                        if ':' not in line:
                            continue
                        for word in shlex.split(line.split(':', 1)[1]):
                            dependency = Path(word)
                            dependencies.add(dependency if dependency.is_absolute() else target / dependency)
                return BuildProduct('V' + TOP, tuple(dependencies))
            result = cache.obtain(spec, cached_compile)
            if result.key != spec.key:
                raise RuntimeError('cache identity mismatch')
            validate_configuration(spec.inputs['configuration'])
            executable = result.executable
            report['build_cache'].append(dict(name=name, key=result.key, status=result.cache_status,
                runtime_threads=args.runtime_threads, context_threads=args.runtime_threads,
                executable_sha256=result.executable_sha256, manifest=str(result.manifest)))
        report['builds'].append(dict(name=name, configuration=config, executable=str(executable),
                                    executable_sha256=digest(executable)))
        return str(executable)
    def probe(name, executable):
        check_probe(run(name, [executable, '--runtime-probe']), args.runtime_threads)
    def metrics(output, aw):
        for line in output.splitlines():
            if ' cycles=' not in line:
                continue
            values = {key: int(value) for key, value in re.findall(
                r'(cycles|conversion|roots|ntt|crt|carry|passes|base|cache_before|root_loads|root_hits|readback)=(\d+)', line)}
            if values['cycles'] != sum(values[key] for key in ('conversion', 'roots', 'ntt', 'crt', 'carry')):
                raise RuntimeError('phase accounting mismatch')
            report['metrics'].append(dict(ntt_lanes=args.lanes, io_lanes=16, aw=aw,
                                          case=line.split()[0], **values))
    try:
        if args.thread_contract_tests:
            run('runtime-thread-unit-tests', [sys.executable, '-m', 'unittest', 'tests.test_core27_runtime_threads', '-v'])
        if args.build_cache:
            cache, toolchain, environment = cache_context(args.build_cache)
        for aw in args.aw:
            vectors = out / f'vectors-aw{aw}.txt'
            report['vectors'][str(aw)] = write_vectors(vectors, aw, args.seed, True)
            executable = build(f'build-aw{aw}', aw)
            probe(f'probe-aw{aw}', executable)
            if args.thread_contract_tests:
                opposite = '8' if args.runtime_threads == 1 else '1'
                run(f'reject-context-aw{aw}', [executable, '--probe-context', opposite],
                    ['"context_threads":8', 'VerilatedContext has 1 threads'])
                run(f'reject-context-domain-aw{aw}', [executable, '--probe-context', '2'],
                    ['unsupported probe context'])
            if aw == 16:
                lines, parts, case_ids, commands = segments(vectors.read_bytes())
                observed = []
                for index, (start, end, payload) in enumerate(parts):
                    piece = out / f'vectors-aw16-segment{index}.txt'
                    piece.write_bytes(payload)
                    report['segment_provenance'].append(dict(index=index, sha256=digest(piece),
                        original_lines=[start+1, end], transaction_ids=[i+1 for i in commands if start <= i < end]))
                    output = run(f'test-aw16-segment{index}', [executable, str(piece), 'cache'])
                    metrics(output, aw)
                    observed.extend(line.split()[0] for line in output.splitlines() if ' cycles=' in line)
                if observed != case_ids:
                    raise RuntimeError('segmentation changed completed case IDs')
            else:
                metrics(run(f'test-aw{aw}', [executable, str(vectors), 'cache']), aw)
        if args.mutations:
            vectors = out / 'mutation-vectors.txt'
            write_vectors(vectors, 5, args.seed, True)
            original_lines = vectors.read_text().splitlines()
            at = next(i for i, line in enumerate(original_lines) if line.startswith('LOAD_KEEP no-host-chain '))
            chain = out / 'mutation-immediate-chain.txt'
            chain.write_text('\n'.join([original_lines[0], *original_lines[at:]]) + '\n')
            diagnostics = ['mismatch', 'accepted', 'quarantine', 'lane skew', 'word skew',
                           'residue mask skew', 'noncanonical', 'unsupported sparse', 'invalid sparse']
            for name, old, new in DEFECTS:
                text = sources[-1].read_text()
                if text.count(old) != 1:
                    raise ValueError('mutation anchor ' + name)
                changed = out / ('mutant-' + name + '.sv')
                changed.write_text(text.replace(old, new))
                report['mutation_sources'][str(changed)] = digest(changed)
                executable = build('build-mutant-' + name, 5, 16, [*sources[:-1], changed], True)
                # Probe constructs a model but does not evaluate RTL, so initial
                # arithmetic assertions remain part of the actual fault run.
                probe('probe-mutant-' + name, executable)
                run('reject-' + name, [executable, str(chain if name=='immediate-start' else vectors), 'cache'], diagnostics)
            oldcrt = root / 'rtl/kernel/genefer_crt3_pipe.sv'
            changed = out / 'mutant-old-crt.sv'
            changed.write_text(sources[-1].read_text().replace('genefer_crt3_27_pipe crt', 'genefer_crt3_pipe crt'))
            report['mutation_sources'].update({str(changed): digest(changed), str(oldcrt): digest(oldcrt)})
            executable = build('build-mutant-old-crt', 5, 16, [*sources[:-1], oldcrt, changed], True)
            probe('probe-mutant-old-crt', executable)
            run('reject-old-crt', [executable, str(vectors), 'cache'], diagnostics)
            quarter = out / 'mutation-quarter-vectors.txt'
            write_vectors(quarter, 7, args.seed, True)
            control = build('build-quarter-control', 7, 64)
            probe('probe-quarter-control', control)
            run('test-quarter-control', [control, str(quarter), 'cache'])
            host = sources[5]
            if host.read_text().count('read_group<=host_group;') != 1:
                raise ValueError('quarter anchor')
            changed = out / 'mutant-host-quarter.sv'
            changed.write_text(host.read_text().replace('read_group<=host_group;', 'read_group<=0;'))
            report['mutation_sources'][str(changed)] = digest(changed)
            executable = build('build-mutant-host-quarter', 7, 64,
                               [changed if path == host else path for path in sources], True)
            probe('probe-mutant-host-quarter', executable)
            run('reject-host-quarter', [executable, str(quarter), 'cache'], diagnostics)
        for name, expected in originals.items():
            if digest(root / name) != expected:
                raise ValueError('source changed during gate: ' + name)
        report['status'] = 'passed'
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
