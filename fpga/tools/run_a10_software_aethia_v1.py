"""Additive bounded A10 Python-only envelope; never compiles or dispatches.

External main admission supplies the exact manifest SHA and systemd/taskset
caps. Preserve failures; no frozen runner/model edits and no compile lock.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import resource
import subprocess
import sys
import tempfile
import time

BASE = Path('/home/jtl/gfn-fpga-lab/agent-work/merged-negacyclic27-software')
SOURCE = BASE / 'snapshot-v1/fpga'
ORIGINAL_MANIFEST = 'docs/briefs/replies/2026-09-30-B20260930A-A10-software-gate-preparation-v1.json'
ORIGINAL_SHA = '5bfb1b92a8ac82b3aeafa7dacb424856f30566ba97ceb1949dd68c3e6dafeade'
SELF = 'tools/run_a10_software_aethia_v1.py'
RUNNER = 'tools/run_merged_negacyclic27_software_gate.py'
PYTHON = Path('/usr/bin/python3.14')
PYTHON_SHA = '52e0a13e60a981d8c4b6478be2ba5176f69da07948a056bf49cf6f077e30cb41'
CPUS = [0, 2]
MEMORY = 6 << 30
TIMEOUT = 1200


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check_sources(root, pins):
    need(root.is_dir() and root.resolve() == root, 'canonical source root')
    actual = set()
    for path in root.rglob('*'):
        need(not path.is_symlink(), 'source symlink')
        if path.is_file():
            actual.add(str(path.relative_to(root)))
    need(actual == set(pins), 'exact source closure')
    for name, digest in pins.items():
        p = PurePosixPath(name)
        need(not p.is_absolute() and '..' not in p.parts and str(p) == name, 'safe source name')
        path = root / name
        need(path.stat().st_nlink == 1 and sha(path) == digest, 'source pin: ' + name)


def limits(cpus=CPUS):
    need(sorted(os.sched_getaffinity(0)) == cpus, 'exact effective CPU0/2 affinity')
    cores = []
    for cpu in cpus:
        topo = Path('/sys/devices/system/cpu') / f'cpu{cpu}/topology'
        cores.append([int((topo / name).read_text()) for name in ('physical_package_id', 'core_id')])
    need(len(set(map(tuple, cores))) == 2, 'two distinct physical cores')
    group = next(line.split('::', 1)[1] for line in Path('/proc/self/cgroup').read_text().splitlines()
                 if line.startswith('0::'))
    directory = Path('/sys/fs/cgroup') / group.lstrip('/')
    quota = (directory / 'cpu.max').read_text().split()
    memory = (directory / 'memory.max').read_text().strip()
    swap = (directory / 'memory.swap.max').read_text().strip()
    need(len(quota) == 2 and quota[0] != 'max' and 0 < int(quota[0]) <= 2 * int(quota[1]), 'finite <=200% CPU')
    need(memory != 'max' and 0 < int(memory) <= MEMORY and swap == '0', 'finite <=6GiB/noSwap')
    return dict(affinity=cpus, physical_cores=cores, cgroup=group, cpu_max=quota,
                memory_max_bytes=int(memory), memory_swap_max_bytes=0)


def validate(path, digest):
    need(platform.system() == 'Linux' and platform.node() == 'aethia', 'aethia only, before numeric work')
    need(path.is_file() and not path.is_symlink() and sha(path) == digest, 'approved deployment manifest SHA')
    manifest = json.loads(path.read_text())
    need(manifest['schema'] == 'a10-aethia-software-envelope-v1' and manifest['status'] == 'prepared_not_executed'
         and manifest['host'] == 'aethia' and manifest['shared_compile_lock'] is False
         and manifest['HDL_or_native_compiler'] is False and manifest['promotion_allowed'] is False,
         'deployment schema/status')
    need(manifest['source_root'] == str(SOURCE) and manifest['output_parent'] == str(BASE)
         and manifest['cpus'] == CPUS and manifest['memory_max_bytes'] == MEMORY
         and manifest['cpu_quota_percent'] == 200 and manifest['swap_max_bytes'] == 0
         and manifest['timeout_seconds'] == TIMEOUT, 'exact software-only deployment bounds')
    need(manifest['original_manifest_sha256'] == ORIGINAL_SHA
         and manifest['original_manifest'] == ORIGINAL_MANIFEST, 'unchanged original software gate')
    need(manifest['python_path'] == str(PYTHON) and manifest['python_sha256'] == PYTHON_SHA, 'pinned Python-only profile')
    need(Path(__file__).resolve() == SOURCE / SELF and not path.resolve().is_relative_to(SOURCE), 'envelope placement')
    check_sources(SOURCE, manifest['sources'])
    need(not (SOURCE / 'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    need(sha(SOURCE / ORIGINAL_MANIFEST) == ORIGINAL_SHA, 'original manifest pin')
    need(PYTHON.is_file() and Path(sys.executable).resolve() == PYTHON.resolve() and sha(PYTHON) == PYTHON_SHA,
         'exact aethia Python3.14 payload')
    need(BASE.is_dir() and BASE.resolve() == BASE, 'canonical existing output parent')
    return manifest, limits()


def run(path, digest):
    manifest, observed = validate(path, digest)
    output = Path(tempfile.mkdtemp(prefix='artifacts-aw16-v1-', dir=BASE))
    command = [str(PYTHON), '-I', '-B', str(SOURCE / RUNNER), '--manifest', str(SOURCE / ORIGINAL_MANIFEST),
               '--manifest-sha', ORIGINAL_SHA, '--output', str(output / 'gate')]
    context = dict(schema='a10-software-execution-context-v1', started_at=datetime.now(timezone.utc).isoformat(),
                   manifest_sha256=digest, original_manifest_sha256=ORIGINAL_SHA, sources=manifest['sources'],
                   python_sha256=PYTHON_SHA, limits=observed, command=command, software_only=True,
                   shared_compile_lock_acquired=False, HDL_or_compiler_started=False)
    (output / 'context.json').write_text(json.dumps(context, indent=2) + '\n')
    result = dict(status='failed', command=command, context_sha256=sha(output / 'context.json'),
                  source_manifest_sha256=digest, output=str(output), promotion_allowed=False)
    started = time.monotonic()
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (16 << 20, 16 << 20))
        env = dict(PATH='/usr/bin:/bin', PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1',
                   LC_ALL='C', LANG='C', OMP_NUM_THREADS='1')
        with (output / 'stdout.log').open('wb') as stdout, (output / 'stderr.log').open('wb') as stderr:
            child = subprocess.run(command, stdout=stdout, stderr=stderr, env=env, timeout=TIMEOUT, check=False)
        result['returncode'] = child.returncode
        need(child.returncode == 0, 'software gate nonzero terminal')
        report = json.loads((output / 'gate/receipt.json').read_text())
        need(report['status'] == 'passed_software_arithmetic_only' and report['manifest_sha256'] == ORIGINAL_SHA,
             'exact successful frozen gate receipt')
        need(len(report['cases']) == 12 and all(c['status'] == 'passed' and c['fields'] == 3
             and c['residues_checked'] == 3 * 65536 and c['digits_checked'] == 65536 for c in report['cases']),
             'full twelve-case all-field coverage')
        need(len(report['negative_controls']) == 27 and all(n['status'] == 'detected'
             for n in report['negative_controls']), 'typed negative coverage')
        check_sources(SOURCE, manifest['sources'])
        result['status'] = 'passed_A10_AW16_Python_arithmetic_only'
    except Exception as error:
        result['error'] = str(error)
        raise
    finally:
        result['elapsed_seconds'] = time.monotonic() - started
        result['finished_at'] = datetime.now(timezone.utc).isoformat()
        result['artifact_sha256'] = {str(p.relative_to(output)): sha(p) for p in output.rglob('*') if p.is_file()}
        (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha', required=True)
    args = parser.parse_args()
    run(args.manifest, args.manifest_sha)
