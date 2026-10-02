"""Read-only AWS simulation onboarding inventory; never installs or compiles.

Send this source over the existing authenticated SSH channel on stdin. It only
reads distro/package/tool/topology state and runs bounded version/apt-cache
queries. Results are observations, not reservations or native admission.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess


HOST = 'gfn16-aws-m8i'
PACKAGES = ('verilator', 'libfl2', 'libsystemc', 'libsystemc-dev', 'libc6',
            'libstdc++6', 'perl', 'python3.12', 'g++-13', 'make', 'binutils',
            'zlib1g', 'ccache', 'help2man', 'flex', 'bison')
CANDIDATES = tuple(Path(p) for p in (
    '/usr/bin/verilator', '/usr/bin/verilator_bin',
    '/usr/local/bin/verilator', '/usr/local/bin/verilator_bin',
    '/home/ubuntu/.local/bin/verilator', '/home/ubuntu/.local/bin/verilator_bin',
    '/home/ubuntu/gfn16-worker/tools/verilator/usr/bin/verilator',
    '/home/ubuntu/gfn16-worker/tools/verilator/usr/bin/verilator_bin',
    '/home/ubuntu/gfn16-worker/tools/verilator/bin/verilator',
    '/home/ubuntu/gfn16-worker/tools/verilator/bin/verilator_bin',
    '/opt/verilator/bin/verilator', '/opt/verilator/bin/verilator_bin'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def command(argv):
    completed = subprocess.run(argv, capture_output=True, text=True, timeout=20,
                               env=dict(PATH='/usr/bin:/bin', LC_ALL='C', LANG='C'))
    return dict(argv=argv, returncode=completed.returncode,
                stdout=completed.stdout, stderr=completed.stderr)


def file_info(path):
    if not path.exists():
        return dict(path=str(path), exists=False)
    resolved = path.resolve()
    info = dict(path=str(path), exists=True, resolved=str(resolved),
                regular=resolved.is_file())
    if resolved.is_file():
        info.update(bytes=resolved.stat().st_size, sha256=sha(resolved))
    return info


def inventory():
    if socket.gethostname() != HOST or os.getuid() == 0:
        raise ValueError('approved AWS worker, non-root ubuntu required')
    apt = {}
    for package in PACKAGES:
        apt[package] = dict(policy=command(['/usr/bin/apt-cache', 'policy', package]),
                            show=command(['/usr/bin/apt-cache', 'show', package]))
    tool_paths = ('/usr/bin/x86_64-linux-gnu-g++-13', '/usr/bin/g++',
                  '/usr/bin/python3.12', '/usr/bin/python3', '/usr/bin/make',
                  '/usr/bin/taskset', '/usr/bin/perl', '/usr/bin/ld',
                  '/usr/bin/ar', '/usr/bin/as', '/usr/bin/dpkg-deb', '/usr/bin/apt-get')
    known_dirs = {}
    for name in ('/home/ubuntu/gfn16-worker/tools', '/home/ubuntu/.local/bin',
                 '/home/ubuntu/tools', '/opt/verilator'):
        path = Path(name)
        known_dirs[name] = sorted(child.name for child in path.iterdir()) if path.is_dir() else None
    cores = []
    for cpu in range(16):
        path = Path('/sys/devices/system/cpu') / f'cpu{cpu}/topology'
        if path.is_dir():
            cores.append(dict(cpu=cpu, package=int((path/'physical_package_id').read_text()),
                              core=int((path/'core_id').read_text()),
                              siblings=(path/'thread_siblings_list').read_text().strip()))
    return dict(schema='aws-simulation-readonly-inventory-v1',
                status='observed_not_admitted_no_install_no_native_execution',
                observed_at=datetime.now(timezone.utc).isoformat(), host=HOST, uid=os.getuid(),
                os_release=Path('/etc/os-release').read_text(),
                uname=command(['/usr/bin/uname', '-a']),
                dpkg=command(['/usr/bin/dpkg-query', '-W', '-f=${Package}\t${Version}\t${db:Status-Abbrev}\n', *PACKAGES]),
                apt=apt, verilator_dependencies=command(['/usr/bin/apt-cache', 'depends', 'verilator']),
                path_tools={name:shutil.which(name) for name in ('verilator', 'verilator_bin', 'g++', 'python3', 'make', 'taskset')},
                files=[file_info(Path(name)) for name in tool_paths],
                versions={name:command([name, '--version']) for name in
                          ('/usr/bin/g++', '/usr/bin/python3.12', '/usr/bin/make', '/usr/bin/taskset', '/usr/bin/perl')},
                candidate_files=[file_info(path) for path in CANDIDATES], known_directory_children=known_dirs,
                cpus=cores, affinity=sorted(os.sched_getaffinity(0)),
                meminfo=Path('/proc/meminfo').read_text(),
                free_bytes={name:shutil.disk_usage(name).free for name in ('/home/ubuntu/gfn16-worker', '/dev/shm')},
                apt_index_files=[dict(name=p.name, bytes=p.stat().st_size, mtime=p.stat().st_mtime)
                                 for p in Path('/var/lib/apt/lists').iterdir() if p.is_file()],
                limitations=['Known-path probe only, not exhaustive search.',
                             'Existing apt indexes only; no apt update/download/install.',
                             'No compiler/model/Quartus process started; observations are not reservations.'])


if __name__ == '__main__':
    print(json.dumps(inventory(), indent=2))
