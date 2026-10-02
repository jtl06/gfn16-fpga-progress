"""Bounded, exact-wheel auxiliary runtime for independent native references.

No job launcher, VM lifecycle, system package mutation or user-site reliance.
Install only a source-pinned CPython3.14 Linux x86_64 wheel into a fresh isolated
import root; retain wheel/origin metadata and hash every regular file. A shared
host profile must independently admit this complete inventory before replay.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import sys
from urllib.parse import urlparse
from urllib.request import urlopen
import zipfile

sys.dont_write_bytecode = True
VERSION = '2.3.1'
WHEEL = 'gmpy2-2.3.1-cp314-cp314-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl'
URL = 'https://files.pythonhosted.org/packages/76/6c/06c868cb552637a796e4a583c025c63c10efd1c1192a5101bd97312a5756/'+WHEEL
WHEEL_SHA = '8749196c8bcd51612d989f5e509ea77d5c97c40b57eda9a863938facbe2b9eab'
MAX_ARCHIVE = 10 << 20
MAX_EXPANDED = 32 << 20
MAX_FILES = 128


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def wheel_files(raw):
    """Pure archive gate; extraction/import cannot run before this completes."""
    need(type(raw) is bytes and 0 < len(raw) <= MAX_ARCHIVE, 'bounded wheel archive')
    result, total = {}, 0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for entry in archive.infolist():
            name = PurePosixPath(entry.filename)
            normalized = str(name)+'/' if entry.is_dir() else str(name)
            need(not name.is_absolute() and '..' not in name.parts and normalized == entry.filename
                and entry.filename not in ('', '.') and '\\' not in entry.filename, 'safe wheel member')
            mode = entry.external_attr >> 16
            need(not stat.S_ISLNK(mode) and (stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR)), 'regular wheel member')
            need(not entry.flag_bits & 1, 'unencrypted wheel member')
            need(name.parts[0] in ('gmpy2', 'gmpy2.libs', 'gmpy2-'+VERSION+'.dist-info'), 'exact gmpy2 package topology')
            if entry.is_dir():
                continue
            total += entry.file_size
            need(total <= MAX_EXPANDED and len(result) < MAX_FILES and entry.filename not in result, 'bounded unique wheel members')
            value = archive.read(entry)
            need(len(value) == entry.file_size, 'wheel member extent')
            result[entry.filename] = value
    need(result and 'gmpy2/__init__.py' in result and any(name.endswith('.so') for name in result), 'native gmpy2 closure')
    need('gmpy2-'+VERSION+'.dist-info/WHEEL' in result and 'gmpy2-'+VERSION+'.dist-info/METADATA' in result,
         'wheel metadata closure')
    metadata = result['gmpy2-'+VERSION+'.dist-info/METADATA'].decode()
    tags = result['gmpy2-'+VERSION+'.dist-info/WHEEL'].decode()
    need(re.search(r'^Name: gmpy2$', metadata, re.M) and re.search(r'^Version: '+re.escape(VERSION)+'$', metadata, re.M),
         'exact wheel package/version')
    need('Tag: cp314-cp314-manylinux_2_17_x86_64' in tags and 'Root-Is-Purelib: false' in tags,
         'exact CPython/native platform tag')
    return result


def dump(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2); stream.write('\n')


def install(target, allowed_parent, host, python_sha):
    need(platform.system() == 'Linux' and platform.machine() == 'x86_64'
        and sys.version_info[:2] == (3, 14), 'CPython3.14 Linux x86_64 only')
    need(platform.node() == host, 'exact reference host')
    interpreter = Path(sys.executable).resolve()
    need(re.fullmatch('[0-9a-f]{64}', python_sha) and sha(interpreter) == python_sha, 'exact admitted interpreter')
    target, allowed_parent = Path(target), Path(allowed_parent)
    need(allowed_parent.is_absolute() and allowed_parent.resolve() == allowed_parent
        and target.is_absolute() and target.parent == allowed_parent
        and target.name == 'gmpy2-'+VERSION+'-v1' and not target.exists() and not target.is_symlink(), 'fresh exact runtime target')
    for ancestor in [allowed_parent, *allowed_parent.parents]:
        need(not ancestor.is_symlink(), 'no runtime parent symlinks')
    wheel_path = allowed_parent/(target.name+'.whl')
    manifest_path = allowed_parent/(target.name+'-manifest.json')
    need(not wheel_path.exists() and not manifest_path.exists(), 'fresh immutable wheel/manifest')
    need(urlparse(URL).scheme == 'https' and urlparse(URL).netloc == 'files.pythonhosted.org', 'official wheel origin')
    with urlopen(URL, timeout=45) as response:
        need(response.geturl() == URL, 'exact wheel endpoint')
        raw = response.read(MAX_ARCHIVE+1)
    need(len(raw) <= MAX_ARCHIVE and hashlib.sha256(raw).hexdigest() == WHEEL_SHA, 'official wheel digest')
    files = wheel_files(raw)
    allowed_parent.mkdir(parents=True, exist_ok=True)
    with wheel_path.open('xb') as stream:
        stream.write(raw)
    target.mkdir()
    for name, content in files.items():
        path = target/name; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(content)
    origin = dict(schema='native-gmpy2-wheel-origin-v1', package='gmpy2', version=VERSION, wheel=WHEEL,
        url=URL, wheel_sha256=WHEEL_SHA, wheel_bytes=len(raw), expanded_bytes=sum(map(len, files.values())),
        pypi_source='https://pypi.org/project/gmpy2/2.3.1/', python_path=str(interpreter), python_sha256=python_sha,
        host=host, installer_sha256=sha(Path(__file__)), no_system_or_user_site_mutation=True)
    dump(target/'wheel-origin.json', origin)
    sys.path.insert(0, str(target))
    import gmpy2
    need(gmpy2.version() == VERSION and Path(gmpy2.__file__).is_relative_to(target), 'exact isolated import origin/version')
    # Scalar sanity only, unrelated to full-size arithmetic or native RTL.
    need(gmpy2.mpz(1234567)**2 % 1000000007 == 155666821, 'gmpy2 scalar sanity')
    inventory = {str(path):sha(path) for path in target.rglob('*') if path.is_file()}
    inventory[str(wheel_path)] = sha(wheel_path)
    need(all(not path.is_symlink() and path.stat().st_nlink == 1 for path in target.rglob('*') if path.is_file()),
         'regular immutable runtime closure')
    result = dict(schema='native-python-module-runtime-v1', status='installed_dependency_requires_shared_profile_admission',
        host=host, python_path=str(interpreter), python_sha256=python_sha,
        python_module_paths=[str(target)], toolchain_files_sha256=inventory,
        package='gmpy2', package_version=gmpy2.version(), gmp_version=gmpy2.mp_version(),
        import_origin=str(gmpy2.__file__), origin=origin, native_rtl_qualification=False)
    dump(manifest_path, result)
    return dict(status=result['status'], manifest=str(manifest_path), manifest_sha256=sha(manifest_path),
        python_module_paths=result['python_module_paths'], files=len(inventory), package_version=gmpy2.version())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, required=True); parser.add_argument('--allowed-parent', type=Path, required=True)
    parser.add_argument('--host', required=True); parser.add_argument('--python-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(install(args.target, args.allowed_parent, args.host, args.python_sha256), indent=2))
