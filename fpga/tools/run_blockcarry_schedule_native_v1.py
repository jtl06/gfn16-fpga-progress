"""Fresh, pinned CPU-only full-size block-carry model run on aethia."""
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import socket
import subprocess
import sys
import tarfile
import time

ROOT = Path('/home/jtl/gfn-fpga-lab/agent-work/stream-ntt-blockcarry-schedule-v1')
MANIFEST = '7ce9d2f6800de4c18107508e301767dbcd4b9e5189c2a884c5085951fa4eeb45'
ARCHIVE = '7face42c24c6b3aa69946007425177860cf56dbbd2c0d1cb2094bdd13c36f1ff'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    require(socket.gethostname() == 'aethia' and ROOT.resolve() == ROOT, 'aethia canonical root')
    require(sorted(os.sched_getaffinity(0)) == [4], 'one physical CPU4 allocation')
    group = next(x.split('::', 1)[1] for x in Path('/proc/self/cgroup').read_text().splitlines() if x.startswith('0::'))
    cgroup = Path('/sys/fs/cgroup') / group.lstrip('/')
    quota = (cgroup / 'cpu.max').read_text().split()
    memory = (cgroup / 'memory.max').read_text().strip()
    require(quota[0] != 'max' and 0 < int(quota[0]) <= int(quota[1]), 'CPU quota')
    require(memory != 'max' and 0 < int(memory) <= 2 << 30, 'aggregate memory cap')
    require(shutil.disk_usage(ROOT).free >= (10 << 30) + (32 << 20), 'disk floor/reservation')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    stage = ROOT / 'stage-v1'
    require(sha(stage / 'manifest.json') == MANIFEST and sha(stage / 'source.tar.gz') == ARCHIVE, 'stage identity')
    manifest = json.loads((stage / 'manifest.json').read_text())
    expected = manifest['files']
    require(len(expected) == manifest['expected_file_count'] == 9, 'nine-file closure')
    source = ROOT / 'source-v1'
    output = ROOT / 'result-v1'
    require(not source.exists() and not source.is_symlink() and not output.exists() and not output.is_symlink(), 'fresh outputs only')
    payload = {}
    with tarfile.open(stage / 'source.tar.gz', 'r:gz') as archive:
        members = archive.getmembers()
        require(len(members) == 9 and {m.name for m in members} == set(expected), 'archive closure')
        for member in members:
            name = Path(member.name)
            require(member.isfile() and not name.is_absolute() and '..' not in name.parts and member.size <= 65536, 'regular bounded source')
            data = archive.extractfile(member).read()
            require(len(data) == expected[member.name]['bytes'] and hashlib.sha256(data).hexdigest() == expected[member.name]['sha256'], 'member identity')
            payload[member.name] = data
    source.mkdir()
    for name, data in payload.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
    output.mkdir()
    command = [sys.executable, '-I', '-S', '-B', str(source / 'fpga/tools/stream_ntt_blockcarry_model_gate.py'),
               '--n', '65536', '--parallel', '8', '--run-full-joined', '--max-seconds', '900']
    record = dict(status='running',host=socket.gethostname(),affinity=[4],cgroup=group,
                  cpu_max=quota,memory_max=memory,command=command,manifest_sha256=MANIFEST,
                  archive_sha256=ARCHIVE,launcher_sha256=sha(Path(__file__)),
                  python_sha256=sha(Path(sys.executable).resolve()),python_version=sys.version,
                  source_sha256={n:v['sha256'] for n,v in expected.items()})
    (output / 'context.json').write_text(json.dumps(record,indent=2)+'\n')
    started = time.monotonic()
    try:
        with (output / 'stdout.json').open('x') as stdout, (output / 'stderr.log').open('x') as stderr:
            run = subprocess.run(command,cwd=source,stdout=stdout,stderr=stderr,timeout=930,
                                 env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        record['returncode'] = run.returncode
        require(run.returncode == 0, 'model returned nonzero; retained stdout/stderr')
        result = json.loads((output / 'stdout.json').read_text())
        require(result['status'] == 'PASS' and result['n'] == 65536 and result['p'] == 8 and len(result['cases']) == 4, 'complete requested model gate')
        require(all(c['status'] == 'PASS' for c in result['cases']) and result['queued_events']['epochs_checked'] == 2, 'arithmetic and two-epoch event checks')
        record['status'] = 'passed_fullN_joined_model_not_RTL'
    except BaseException as error:
        record.update(status='failed_or_incomplete',error=repr(error))
        raise
    finally:
        record['elapsed_seconds'] = time.monotonic() - started
        record['sources_unchanged'] = all(sha(source / n) == v['sha256'] for n,v in expected.items())
        record['stage_unchanged'] = sha(stage / 'manifest.json') == MANIFEST and sha(stage / 'source.tar.gz') == ARCHIVE
        record['artifacts'] = {p.name:sha(p) for p in output.iterdir() if p.is_file()}
        if not record['sources_unchanged'] or not record['stage_unchanged']:
            record['status'] = 'failed_or_incomplete'
        with (output / 'receipt.json').open('x') as stream:
            json.dump(record,stream,indent=2)
            stream.write('\n')
    require(record['status'] == 'passed_fullN_joined_model_not_RTL', 'final provenance guard')
    print(json.dumps({k:record[k] for k in ('status','elapsed_seconds','returncode','sources_unchanged')}))


if __name__ == '__main__':
    main()
