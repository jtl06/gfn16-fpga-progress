"""Bounded rootless Ubuntu Verilator extraction, only after main admission.

No dpkg installation, maintainer script, service action, compiler or simulation.
The exact observed distro package is downloaded once, validated and retained.
Only runtime files are materialized; unused docs/pkgconfig remain in retained
package/tar evidence. Extracted tool identities do not admit a native queue.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import resource
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import time
import urllib.request


HOST = 'gfn16-aws-m8i'
WORKER = Path('/home/ubuntu/gfn16-worker')
DEST = WORKER/'tools/verilator-5.020-ubuntu2404-v1'
URL = 'http://us-east-1.ec2.archive.ubuntu.com/ubuntu/pool/universe/v/verilator/verilator_5.020-1_amd64.deb'
PACKAGE_NAME = 'verilator_5.020-1_amd64.deb'
PACKAGE_BYTES = 6940528
PACKAGE_SHA = 'bb74ca8c32c73eb903ee91da64c8b58cfbe095c229967a95782108afb67bb3ca'
DPKG = Path('/usr/bin/dpkg-deb')
DPKG_SHA = 'fc9dde782ca8309b65ab92e61d13318bf463cd1aa71daa8967b87b81b48b63d2'
MEMORY = 1<<30
MAX_ALLOCATION = 128<<20
MAX_TAR = 64<<20
MAX_FILES = 8192
DEADLINE_SECONDS = 300
CPU = [4]
TOOLS = {
    'compiler': ('/usr/bin/x86_64-linux-gnu-g++-13', '1353e9bdd29a7295c7226bf6c63abccce056d8cac31f112e5cdbecc3f28c2769'),
    'python': ('/usr/bin/python3.12', 'e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f'),
    'make': ('/usr/bin/make', 'd78b8f1d099fbcfb6f2f49ab87223b9b68fb3956642f92d6ec6de812e8afa965'),
    'taskset': ('/usr/bin/taskset', 'a431738fadddc2e2326c8ab81843e72f4011658379381aef1502a6ddb1c1115b'),
    'perl': ('/usr/bin/perl', '47bdc8a342556c1d140084417ef6cacd79a3362e4b6cc1e4754df55bdf1e3683'),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def canonical(path, owner=None):
    require(path.is_absolute(), 'absolute path required')
    for part in [path, *path.parents]:
        require(not part.is_symlink(), 'symlink ancestor: '+str(part))
    require(path.resolve() == path, 'canonical path required')
    if owner is not None and path.exists():
        require(path.stat().st_uid == owner and not path.stat().st_mode & 0o022,
                'destination parent ownership/non-writable permissions')


def fresh_destination(destination=DEST, uid=None):
    require(destination == DEST, 'only exact versioned tool destination')
    canonical(destination)
    require(not destination.exists(), 'fresh destination; failures cannot be retried in place')
    require(WORKER.is_dir(), 'existing approved worker root')
    canonical(WORKER, uid)
    if destination.parent.exists():
        require(destination.parent.is_dir(), 'tools parent directory')
        canonical(destination.parent, uid)


def validate_limits(cpu_max, memory_max, swap_max, affinity, cores):
    quota = cpu_max.split()
    require(len(quota) == 2 and quota[0] != 'max'
            and 0 < int(quota[0]) <= int(quota[1]) and int(quota[1]) > 0,
            'finite aggregate CPU <=100%')
    require(memory_max != 'max' and 0 < int(memory_max) <= MEMORY,
            'finite aggregate memory <=1GiB')
    require(swap_max == '0', 'zero aggregate swap')
    require(affinity == CPU and cores[4] not in {cores[c] for c in range(4)},
            'CPU4 physically disjoint from fit slot0-3')
    return dict(cpu_max=quota, memory_max_bytes=int(memory_max), swap_max_bytes=0,
                affinity=affinity, physical_core=list(cores[4]))


def live_limits():
    group = next(row.split('::',1)[1] for row in Path('/proc/self/cgroup').read_text().splitlines()
                 if row.startswith('0::'))
    path = Path('/sys/fs/cgroup')/group.lstrip('/')
    cores = {}
    for cpu in range(5):
        top = Path('/sys/devices/system/cpu')/f'cpu{cpu}/topology'
        cores[cpu] = tuple(int((top/key).read_text()) for key in ('physical_package_id','core_id'))
    result = validate_limits((path/'cpu.max').read_text().strip(),
                             (path/'memory.max').read_text().strip(),
                             (path/'memory.swap.max').read_text().strip(),
                             sorted(os.sched_getaffinity(0)), cores)
    result['cgroup'] = group
    return result


def verify_package(path):
    require(path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1
            and path.stat().st_size == PACKAGE_BYTES and sha(path) == PACKAGE_SHA,
            'exact Ubuntu package size/SHA/type')


def ar_inventory(path):
    """Validate the Debian ar container before any dpkg-deb decompression."""
    result = {}
    with path.open('rb') as stream:
        require(stream.read(8) == b'!<arch>\n', 'Debian ar magic')
        while header := stream.read(60):
            require(len(header) == 60 and header[58:] == b'`\n', 'ar header/trailer')
            name = header[:16].decode('ascii').strip().removesuffix('/')
            require(name not in result and re.fullmatch(r'(debian-binary|(control|data)\.tar\.(gz|xz|zst|bz2))',name),
                    'unique standard Debian ar members')
            size = int(header[48:58].strip())
            require(0 < size <= PACKAGE_BYTES, 'bounded ar member')
            data = stream.read(size)
            require(len(data) == size, 'complete ar member')
            result[name] = dict(bytes=size, sha256=hashlib.sha256(data).hexdigest())
            if name == 'debian-binary':
                require(data == b'2.0\n', 'Debian format2.0')
            if size % 2:
                require(stream.read(1) == b'\n', 'ar alignment')
    require(len(result) == 3 and 'debian-binary' in result
            and sum(n.startswith('control.tar.') for n in result) == 1
            and sum(n.startswith('data.tar.') for n in result) == 1, 'exact three-member Debian archive')
    return result


def member_name(raw):
    require(type(raw) is str and '\x00' not in raw, 'tar member text')
    if raw in ('.','./'):
        return '.'
    name = raw[2:] if raw.startswith('./') else raw
    name = name.removesuffix('/')
    pure = PurePosixPath(name)
    require(name and not pure.is_absolute() and '..' not in pure.parts
            and str(pure) == name, 'safe canonical tar member path')
    return name


def runtime_name(name):
    return name in ('.','usr','usr/bin','usr/share','usr/share/verilator') or name.startswith(('usr/bin/','usr/share/verilator/'))


def validate_tar(path, control=False):
    require(path.stat().st_size <= MAX_TAR, 'bounded uncompressed tar')
    rows = {}
    total = 0
    with tarfile.open(path, 'r:') as archive:
        for member in archive:
            name = member_name(member.name)
            require(name not in rows and len(rows) < MAX_FILES, 'unique bounded tar members')
            allowed = (tarfile.REGTYPE,tarfile.AREGTYPE,tarfile.DIRTYPE) + (() if control else (tarfile.SYMTYPE,))
            require(member.type in allowed and not getattr(member,'sparse',None),
                    'only regular/directory/runtime-safe-symlink tar types; no hardlinks/devices/FIFO')
            require(not member.mode & 0o7000 and 0 <= member.size <= MAX_TAR,
                    'no special modes; bounded member bytes')
            total += member.size
            require(total <= MAX_TAR, 'bounded aggregate tar data')
            if name == '.':
                require(member.isdir(), 'root member must be directory')
            selected = not control and runtime_name(name)
            if selected and not member.issym():
                require(not member.mode & 0o022, 'non-writable installed runtime permissions')
            row = dict(type='directory' if member.isdir() else 'file' if member.isfile() else 'symlink',
                       bytes=member.size, mode=member.mode & 0o777, extracted=selected)
            if member.issym():
                require(member.linkname and '\x00' not in member.linkname, 'symlink target text')
                row['target'] = member.linkname
                if selected:
                    require(not PurePosixPath(member.linkname).is_absolute(), 'no absolute runtime symlink')
                    target = posixpath.normpath(posixpath.join(posixpath.dirname(name),member.linkname))
                    require(not target.startswith('../') and target != '..' and runtime_name(target),
                            'runtime symlink remains in selected rootless tree')
                    row['resolved_target'] = target
            if member.isfile():
                row['sha256'] = hashlib.file_digest(archive.extractfile(member),'sha256').hexdigest()
            rows[name] = row
    # Reject any member descending through a symlink/file, including excluded docs.
    for name,row in rows.items():
        for ancestor in PurePosixPath(name).parents:
            parent = str(ancestor)
            require(parent not in rows or rows[parent]['type'] == 'directory', 'tar parent type collision')
        if row['type'] == 'symlink' and row['extracted']:
            target = rows.get(row['resolved_target'])
            require(target and target['extracted'] and target['type'] in ('file','directory'),
                    'runtime symlink target must be a selected non-symlink member')
    return rows


def validate_control(path, rows):
    require('control' in rows and rows['control']['type'] == 'file', 'Debian control file')
    with tarfile.open(path,'r:') as archive:
        member = next(m for m in archive if member_name(m.name) == 'control')
        text = archive.extractfile(member).read().decode()
    fields = dict(row.split(': ',1) for row in text.splitlines() if ': ' in row and not row[0].isspace())
    require(fields.get('Package') == 'verilator' and fields.get('Version') == '5.020-1'
            and fields.get('Architecture') == 'amd64', 'exact control package/version/architecture')
    return fields


def extract_runtime(path, rows, destination, guard):
    """Manual whitelist extraction, exclusive file creation, no tar.extractall."""
    for name,row in sorted(rows.items(),key=lambda item:(len(PurePosixPath(item[0]).parts),item[0])):
        if row['extracted'] and row['type'] == 'directory' and name != '.':
            guard()
            target = destination/name
            target.mkdir(mode=0o755,parents=True,exist_ok=True)
            canonical(target)
    with tarfile.open(path,'r:') as archive:
        for member in archive:
            name = member_name(member.name); row = rows[name]
            if row['extracted'] and row['type'] == 'file':
                guard(); target = destination/name
                target.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
                canonical(target.parent)
                with target.open('xb') as output:
                    shutil.copyfileobj(archive.extractfile(member),output,1<<20)
                target.chmod(row['mode'])
                require(sha(target) == row['sha256'], 'extracted file SHA')
    for name,row in rows.items():
        if row['extracted'] and row['type'] == 'symlink':
            guard(); target = destination/name
            canonical(target.parent)
            require(not target.exists() and not target.is_symlink(), 'fresh runtime link')
            target.symlink_to(row['target'])
            require(target.resolve().is_relative_to(destination), 'resolved rootless link containment')


def allocation(root):
    return sum(p.lstat().st_blocks*512 for p in root.rglob('*'))


def verify_extracted(rows, destination):
    expected_files = {name:row for name,row in rows.items() if row['extracted'] and row['type'] == 'file'}
    expected_links = {name:row for name,row in rows.items() if row['extracted'] and row['type'] == 'symlink'}
    files = {}; links = {}
    for path in destination.rglob('*'):
        name = str(path.relative_to(destination))
        if name == 'onboarding-evidence' or name.startswith('onboarding-evidence/'):
            continue
        if path.is_symlink():
            links[name] = os.readlink(path)
        elif path.is_file():
            require(path.stat().st_nlink == 1, 'no extracted hardlinks')
            files[name] = sha(path)
            require(name in expected_files and path.stat().st_mode & 0o777 == expected_files[name]['mode'],
                    'exact extracted permissions')
        else:
            require(path.is_dir(), 'only runtime regular files/directories/links')
    require(files == {name:row['sha256'] for name,row in expected_files.items()}
            and links == {name:row['target'] for name,row in expected_links.items()},
            'exact terminal runtime file/link closure')
    for name in links:
        require((destination/name).resolve().is_relative_to(destination), 'terminal runtime link containment')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError('package redirect refused; only exact observed mirror URL')


def download(path, guard):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect)
    with opener.open(URL,timeout=15) as response, path.open('xb') as output:
        require(response.geturl() == URL and response.status == 200, 'exact package URL/status')
        length = response.headers.get('Content-Length')
        require(length is None or int(length) == PACKAGE_BYTES, 'package Content-Length')
        count = 0
        while chunk := response.read(1<<20):
            guard(); count += len(chunk)
            require(count <= PACKAGE_BYTES, 'download byte ceiling')
            output.write(chunk)
    verify_package(path)


def decompress(kind, package, evidence, guard, steps):
    output = evidence/(kind+'.tar')
    error = evidence/(kind+'.stderr.log')
    argv = [str(DPKG),'--ctrl-tarfile' if kind == 'control' else '--fsys-tarfile',str(package)]
    with output.open('xb') as out, error.open('xb') as err:
        child = subprocess.Popen(argv,stdout=out,stderr=err,stdin=subprocess.DEVNULL,
                                 start_new_session=True,env=dict(PATH='/usr/bin:/bin',LC_ALL='C',LANG='C'))
        try:
            while child.poll() is None:
                guard(); require(output.stat().st_size <= MAX_TAR, 'decompression byte ceiling')
                time.sleep(.05)
            require(child.returncode == 0, 'dpkg-deb decompression return code')
        finally:
            if child.poll() is None:
                os.killpg(child.pid,signal.SIGKILL); child.wait()
            steps.append(dict(argv=argv,returncode=child.returncode,
                              output_sha256=sha(output),stderr_sha256=sha(error)))
    return output


def execute(self_sha):
    source = Path(__file__).resolve()
    require(re.fullmatch('[0-9a-f]{64}',self_sha or '') and sha(source) == self_sha,
            'externally reviewed helper SHA')
    require(socket.gethostname() == HOST and os.getuid() == 1000 and os.geteuid() == 1000,
            'approved AWS worker non-root ubuntu only')
    require(sys.flags.isolated == 1, 'isolated Python -I required')
    require('VERSION_ID="24.04"' in Path('/etc/os-release').read_text(), 'Ubuntu24.04')
    require(Path(sys.executable).resolve() == Path(TOOLS['python'][0]), 'explicit Python3.12')
    for path,digest in [*TOOLS.values(),(str(DPKG),DPKG_SHA)]:
        require(sha(Path(path)) == digest, 'installed executable SHA: '+path)
    limits = live_limits()
    fresh_destination(uid=os.getuid())
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_AS,(MEMORY,MEMORY))
    resource.setrlimit(resource.RLIMIT_FSIZE,(MAX_TAR,MAX_TAR))
    DEST.parent.mkdir(mode=0o755,exist_ok=True)
    canonical(DEST.parent,os.getuid())
    DEST.mkdir(mode=0o755)
    evidence = DEST/'onboarding-evidence'; evidence.mkdir()
    shutil.copyfile(source,evidence/'extract_aws_verilator_v1.py')
    started = time.monotonic()
    report = dict(schema='aws-rootless-verilator-extraction-v1',status='running',host=HOST,
                  started_at=datetime.now(timezone.utc).isoformat(),helper_sha256=self_sha,
                  package_url=URL,package_sha256=PACKAGE_SHA,package_bytes=PACKAGE_BYTES,
                  destination=str(DEST),limits=limits,steps=[],
                  policy='Rootless runtime-only extraction; no install scripts/services/sudo/compilation/simulation/deletion.',
                  native_queue_admitted=False,promotion_allowed=False)

    def save():
        (evidence/'report.json').write_text(json.dumps(report,indent=2)+'\n')

    def guard():
        require(time.monotonic()-started < DEADLINE_SECONDS, '300s total deadline')
        require(allocation(DEST) <= MAX_ALLOCATION, '128MiB total extraction/evidence allocation')
        require(shutil.disk_usage(DEST).free >= 10<<30, 'durable free floor10GiB')
        mem = dict(row.split(':',1) for row in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024 >= 8<<30, 'host memory floor8GiB')
        require(sha(source) == self_sha and sha(DPKG) == DPKG_SHA, 'helper/decompressor drift')

    def interrupted(number, frame):
        raise RuntimeError('bounded extraction signal '+str(number))

    prior = {number:signal.signal(number,interrupted) for number in (signal.SIGTERM,signal.SIGALRM)}
    signal.alarm(DEADLINE_SECONDS)
    try:
        save(); guard()
        package = evidence/PACKAGE_NAME
        download(package,guard)
        report['ar_members'] = ar_inventory(package); save()
        control = decompress('control',package,evidence,guard,report['steps'])
        control_rows = validate_tar(control,control=True)
        report['control'] = validate_control(control,control_rows)
        report['control_members'] = control_rows; save()
        data = decompress('data',package,evidence,guard,report['steps'])
        rows = validate_tar(data)
        report['package_members'] = rows; save()
        extract_runtime(data,rows,DEST,guard)
        require(all(name in rows and rows[name]['type'] == 'file' and rows[name]['extracted']
                    for name in ('usr/bin/verilator','usr/bin/verilator_bin','usr/share/verilator/include/verilated.h',
                                 'usr/share/verilator/include/verilated.cpp')),
                'complete required Verilator wrapper/native/runtime header/source')
        report['extracted_files'] = {name:row['sha256'] for name,row in rows.items()
                                     if row['extracted'] and row['type'] == 'file'}
        report['extracted_symlinks'] = {name:row['target'] for name,row in rows.items()
                                        if row['extracted'] and row['type'] == 'symlink'}
        report['candidate_profile'] = dict(
            name='aws-ubuntu2404-verilator5020-gcc13-python312-v1',host=HOST,
            package_sha256=PACKAGE_SHA,tools={name:dict(path=path,sha256=digest) for name,(path,digest) in TOOLS.items()},
            verilator={name:dict(path=str(DEST/'usr/bin'/name),sha256=sha(DEST/'usr/bin'/name))
                       for name in ('verilator','verilator_bin')},
            verilator_root=str(DEST/'usr/share/verilator'),extracted_file_sha256=report['extracted_files'],
            scope='Package/tool inventory only; no native ABI/thread/oracle or queue admission; no cross-host ELF/cache.')
        verify_package(package); guard(); live_limits()
        verify_extracted(rows,DEST)
        report['status'] = 'extracted_exact_package_tool_inventory_pending_native_admission'
    except BaseException as exc:
        report['status'] = 'failed_rootless_extraction_retained'; report['error'] = repr(exc)
        raise
    finally:
        signal.alarm(0)
        report['elapsed_seconds'] = time.monotonic()-started
        report['allocated_bytes'] = allocation(DEST)
        report['evidence_files'] = {str(p.relative_to(evidence)):sha(p) for p in evidence.rglob('*')
                                    if p.is_file() and p.name != 'report.json'}
        save()
        for number,handler in prior.items():
            signal.signal(number,handler)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--helper-sha256',required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.helper_sha256),indent=2))
