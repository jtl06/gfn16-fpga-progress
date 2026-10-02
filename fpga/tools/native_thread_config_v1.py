"""Pure thread/configuration and physical allocation checks for native jobs.

No execution or reservation. The caller still owns atomic physical-core locks,
live topology/quota checks, lint, tool pins and finite process/resource bounds.
Existing single-thread launchers and manifests are deliberately unchanged.
"""
import copy
import json
import re

THREADS = (1, 2, 4, 8)
MACRO = 'GFN16_RUNTIME_THREADS'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def thread_count(value):
    need(type(value) is int and value in THREADS, 'typed supported runtime threads')
    return value


def expected_probe(threads):
    threads = thread_count(threads)
    return dict(context_threads=threads, model_threads=threads, expected_threads=threads)


def configure_build(build, threads=1):
    """Return a detached successor build; runtime threads never alter -j2."""
    threads = thread_count(threads)
    result = copy.deepcopy(build)
    aw = result['parameters'].get('AW')
    need(aw is None or type(aw) is int and 1 <= aw <= 16, 'typed supported AW')
    need(aw is None or aw > 8 or threads == 1, 'short AW5/AW8 batches stay one-thread')
    flags = result['cflags']
    need(type(flags) is list and all(type(flag) is str for flag in flags), 'typed compiler flags')
    need(not any(re.search(r'(?:^|\s)-[DU](?:GFN16_RUNTIME_THREADS|CORE27_[A-Z_0-9]*RUNTIME_THREADS)(?:=|\s|$)', flag)
                 for flag in flags), 'no existing runtime macro override')
    result['runtime_threads'] = threads
    result['cflags'].append(f'-D{MACRO}={threads}')
    return result


def validate_build(build, probe):
    threads = thread_count(build['runtime_threads'])
    aw = build['parameters'].get('AW')
    need(aw is None or type(aw) is int and 1 <= aw <= 16, 'typed supported AW')
    need(aw is None or aw > 8 or threads == 1, 'short AW5/AW8 batches stay one-thread')
    flags = build['cflags']
    need(type(flags) is list and all(type(flag) is str for flag in flags), 'typed compiler flags')
    # Accept exactly one numeric runtime macro. A second -D/-U, even embedded
    # in a cflags element, invalidates the build identity rather than winning.
    overrides = re.findall(r'(?:^|\s)(-[DU](?:GFN16_RUNTIME_THREADS|CORE27_[A-Z_0-9]*RUNTIME_THREADS)(?:[^\s]*))', ' '.join(flags))
    need(overrides == [f'-D{MACRO}={threads}'], 'exact runtime context macro')
    need(type(probe) is dict and probe == expected_probe(threads)
         and all(type(value) is int for value in probe.values()), 'exact typed model/context probe')
    return threads


def validate_allocation(allocation, threads):
    """SMT siblings do not count as separate eligible simulation cores."""
    threads = thread_count(threads)
    cpus, cores = allocation['cpus'], allocation['physical_cores']
    need(type(cpus) is list and cpus and all(type(cpu) is int and cpu >= 0 for cpu in cpus)
         and cpus == sorted(set(cpus)), 'ordered distinct logical CPU allocation')
    need(type(cores) is list and len(cores) == len(cpus)
         and all(type(core) is list and len(core) == 2
                 and all(type(value) is int and value >= 0 for value in core) for core in cores)
         and len(set(map(tuple, cores))) == len(cores), 'one logical CPU per distinct physical core')
    need(threads <= len(cores), 'runtime threads exceed allocated physical cores')
    workers = allocation['compile_workers']
    need(type(workers) is int and workers == 2 and workers <= len(cores), 'fixed two compiler workers fit allocation')
    quota = allocation['cpu_quota_percent']
    need(type(quota) is int and 100 * max(threads, workers) <= quota <= 100 * len(cores), 'CPU quota covers threads/workers within allocation')
    memory = allocation['memory_bytes']
    # The launcher host profile owns its permitted ceiling. Thread selection
    # must neither silently enlarge it nor replace the host admission policy.
    need(type(memory) is int and memory > 0, 'typed finite memory allocation')
    return copy.deepcopy(allocation)


def verilator_flags(build):
    """Compiler concurrency and model threading are independent build inputs."""
    return ['--cc', '--exe', '--build', '-j', '2', '--threads', str(thread_count(build['runtime_threads']))]


def check_probe(stdout, threads):
    try:
        actual = json.loads(stdout)
    except (ValueError, TypeError) as error:
        raise ValueError('invalid executable runtime probe') from error
    need(actual == expected_probe(threads) and all(type(value) is int for value in actual.values()),
         'executable model/context mismatch')
    return actual
