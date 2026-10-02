"""Pure per-host interpreter/compiler/runtime schema and read-only file pins.

Profile paths are explicit. Isolated compilers/modules require their complete
declared regular-file inventory plus exact symlink states; a wrapper hash alone
does not identify its compiler or linked dependencies. No installation occurs.
"""
import hashlib
import os
from pathlib import Path
import re
import stat


def need(ok, why):
    if not ok:
        raise ValueError(why)


def path_value(value):
    need(type(value) is str and '\0' not in value, 'typed runtime path')
    path = Path(value)
    need(path.is_absolute() and str(path) == value and '..' not in path.parts, 'explicit absolute runtime path')
    return value


def configure(profile):
    result = dict(profile)
    for name, default in (('compiler_path','/usr/bin/x86_64-linux-gnu-g++-15'),
                          ('compiler_alias','/usr/bin/g++'), ('python_path','/usr/bin/python3.14'),
                          ('make_path','/usr/bin/make'), ('taskset_path','/usr/bin/taskset')):
        result[name] = path_value(result.get(name, default))
    path_value(result['verilator_dir'])
    result.setdefault('env_path', result['verilator_dir']+':/usr/bin:/bin')
    need(type(result['env_path']) is str and result['env_path'], 'explicit runtime PATH')
    for value in result['env_path'].split(':'):
        path_value(value)
    modules = result.get('python_module_paths', [])
    need(type(modules) is list and len(modules) == len(set(modules)), 'distinct module path list')
    result['python_module_paths'] = [path_value(value) for value in modules]
    files = result.get('toolchain_files_sha256', {})
    links = result.get('toolchain_symlinks', {})
    need(type(files) is dict and type(links) is dict and len(files)+len(links) <= 65536, 'bounded runtime inventory')
    for name, digest in files.items():
        path_value(name)
        need(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest), 'exact runtime file hash')
    for name, target in links.items():
        path_value(name)
        need(type(target) is str and target and len(target) <= 4096 and '\0' not in target, 'exact symlink target')
    need(not set(files) & set(links), 'file/symlink inventory overlap')
    result['toolchain_files_sha256'] = dict(files)
    result['toolchain_symlinks'] = dict(links)
    need(not modules or files, 'module dependencies need an exact file inventory')
    result['tool_paths'] = dict(verilator=result['verilator_dir']+'/verilator',
        verilator_bin=result['verilator_dir']+'/verilator_bin', compiler=result['compiler_path'],
        compiler_alias=result['compiler_alias'], python=result['python_path'],
        make=result['make_path'], taskset=result['taskset_path'])
    return result


def verify_files(profile):
    """Rehash declared dependencies before/after commands, outside timed runs."""
    profile = configure(profile)
    checked_bytes = 0
    for name, expected in profile['toolchain_files_sha256'].items():
        path = Path(name)
        before = path.stat(follow_symlinks=False)
        need(stat.S_ISREG(before.st_mode), 'regular runtime inventory file')
        with path.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        after = path.stat(follow_symlinks=False)
        need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns) ==
             (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns), 'runtime file changed while hashing')
        need(actual == expected, 'runtime dependency drift: '+name)
        checked_bytes += after.st_size
    for name, expected in profile['toolchain_symlinks'].items():
        # Optional SDK symlinks may refer to unused OS components. Bind their
        # text/state without assuming every unused target must exist.
        need(Path(name).is_symlink() and os.readlink(name) == expected, 'runtime symlink drift: '+name)
    return dict(schema='native-runtime-file-check-v1', status='exact_declared_files_and_symlink_states',
        regular_files=len(profile['toolchain_files_sha256']), symlinks=len(profile['toolchain_symlinks']),
        checked_bytes=checked_bytes, python_module_paths=profile['python_module_paths'])
