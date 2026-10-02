"""Verified POSIX simulator-build cache. This never caches an oracle result.

Callers declare the complete source/include/toolchain closure, actual flags,
and relevant environment. Build callbacks run only on a miss and may return
compiler-discovered dependencies; undeclared dependencies reject publication.
All declared files/trees are rehashed before use and again after a build.
"""
from __future__ import annotations
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import time
from typing import Callable,Mapping,Sequence
import uuid

SCHEMA=1

class CacheError(RuntimeError):pass
class InputsChanged(CacheError):pass
class InvalidArtifact(CacheError):pass
class UntrackedDependency(CacheError):pass

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()

def digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):value.update(block)
    return value.hexdigest()

def file_record(path):
    path=Path(path).absolute()
    if not path.is_file():raise CacheError(f'missing input file: {path}')
    return dict(path=str(path),realpath=str(path.resolve()),sha256=digest(path))

def tree_record(path):
    path=Path(path).absolute()
    if not path.is_dir():raise CacheError(f'missing input tree: {path}')
    files=[];links={}
    if path.is_symlink():links[str(path)]=os.readlink(path)
    for item in sorted(path.rglob('*')):
        if item.is_symlink():links[str(item)]=os.readlink(item)
        if item.is_file():files.append(file_record(item))
    return dict(root=str(path),realpath=str(path.resolve()),files=files,links=links)

def fingerprint_toolchain(commands:Mapping[str,Sequence[str]], *, files=(), trees=()):
    """Fingerprint resolved executables, version/config output, and runtime files.

    Commands must be read-only version/config probes. Include compiler backend,
    linker, runtime headers/libraries and include trees, not merely version text.
    """
    probes={};tracked={}
    for name,command in sorted(commands.items()):
        if not command:raise CacheError('empty toolchain command')
        executable=shutil.which(command[0])
        if executable is None:raise CacheError(f'missing tool: {command[0]}')
        record=file_record(executable);tracked[record['path']]=record
        result=subprocess.run([executable,*command[1:]],capture_output=True,text=True,timeout=30,check=True)
        probes[name]=dict(command=[executable,*command[1:]],stdout=result.stdout,stderr=result.stderr)
    for path in files:
        record=file_record(path);tracked[record['path']]=record
    return dict(probes=probes,files=[tracked[k] for k in sorted(tracked)],trees=[tree_record(p) for p in sorted(map(str,trees))])

@dataclass(frozen=True)
class BuildSpec:
    payload:bytes

    @classmethod
    def capture(cls, *, sources:Mapping[str,Path], configuration, toolchain, environment, include_trees=()):
        source_records={name:file_record(path) for name,path in sorted(sources.items())}
        body=dict(schema=SCHEMA,sources=source_records,configuration=configuration,
                  toolchain=toolchain,environment=dict(environment),include_trees=[tree_record(p) for p in sorted(map(str,include_trees))])
        return cls(canonical(body))

    @property
    def key(self):return hashlib.sha256(self.payload).hexdigest()

    @property
    def inputs(self):return json.loads(self.payload)

    def tracked_paths(self):
        body=self.inputs;records=list(body['sources'].values())+body['toolchain'].get('files',[])
        for tree in body['include_trees']+body['toolchain'].get('trees',[]):records+=tree['files']
        return {r['realpath'] for r in records}

    def assert_unchanged(self):
        body=self.inputs
        for old in list(body['sources'].values())+body['toolchain'].get('files',[]):
            if file_record(old['path'])!=old:raise InputsChanged(f'input changed after key capture: {old["path"]}')
        for old in body['include_trees']+body['toolchain'].get('trees',[]):
            if tree_record(old['root'])!=old:raise InputsChanged(f'input tree changed after key capture: {old["root"]}')

@dataclass(frozen=True)
class BuildProduct:
    executable:str
    dependencies:tuple[Path,...]=()

@dataclass(frozen=True)
class BuildResult:
    key:str
    executable:Path
    executable_sha256:str
    artifact_directory:Path
    cache_status:str
    manifest:Path

def _relative(value):
    path=Path(value)
    if path.is_absolute() or not path.parts or any(p in ('..','.') for p in path.parts):
        raise InvalidArtifact(f'unsafe executable path: {value}')
    return path

def _inventory(root, *, frozen):
    files={};directories=[]
    if root.is_symlink() or not root.is_dir():raise InvalidArtifact('build directory missing or symlinked')
    for path in sorted(root.rglob('*')):
        mode=path.lstat().st_mode
        if stat.S_ISLNK(mode):raise InvalidArtifact(f'symlink output rejected: {path}')
        relative=path.relative_to(root).as_posix()
        if stat.S_ISDIR(mode):directories.append(relative)
        elif stat.S_ISREG(mode):
            permissions=stat.S_IMODE(mode)
            if permissions&0o7000:raise InvalidArtifact('special output permission bits rejected')
            if frozen and permissions&0o222:raise InvalidArtifact('writable cached artifact')
            files[relative]=dict(sha256=digest(path),size=path.stat().st_size,mode=permissions&0o555)
        else:raise InvalidArtifact(f'nonregular build output: {path}')
    return dict(files=files,directories=directories)

def _freeze(root):
    for path in root.rglob('*'):
        path.chmod(stat.S_IMODE(path.stat().st_mode)&0o555)
    # Keep the private container writable until cross-parent rename updates
    # its '..' entry. The published container is frozen while holding its lock.

def _discard_private_stage(path):
    # Only receives this cache's freshly allocated mkdtemp directory.
    if not path.exists():return
    for item in path.rglob('*'):
        if not item.is_symlink():item.chmod(0o700 if item.is_dir() else 0o600)
    path.chmod(0o700);shutil.rmtree(path)

class BuildCache:
    def __init__(self,root, *, log:Callable[[str],None]=print,lock_timeout=300):
        self.root=Path(root).absolute();self.log=log;self.lock_timeout=lock_timeout
        if self.root.is_symlink():raise CacheError('cache root must not be a symlink')
        for name in ('objects','locks','staging','quarantine'):
            path=self.root/name
            if path.is_symlink():raise CacheError('cache control directory must not be a symlink')
            path.mkdir(parents=True,exist_ok=True)

    def _verify(self,spec,entry,status):
        manifest_path=entry/'manifest.json'
        if entry.is_symlink() or manifest_path.is_symlink():raise InvalidArtifact('symlink cache entry')
        manifest=json.loads(manifest_path.read_text())
        if manifest.get('schema')!=SCHEMA:raise InvalidArtifact('unknown cache manifest schema')
        if manifest.get('key')!=spec.key or canonical(manifest.get('inputs'))!=spec.payload:
            raise InvalidArtifact('cache key/input manifest mismatch')
        executable=_relative(manifest['executable']);inventory=_inventory(entry/'build',frozen=True)
        if inventory!=manifest['outputs']:raise InvalidArtifact('cached output inventory/hash mismatch')
        record=inventory['files'].get(executable.as_posix())
        if record is None or not record['mode']&0o111:raise InvalidArtifact('executable missing or not executable')
        if record['sha256']!=manifest['executable_sha256']:raise InvalidArtifact('executable SHA mismatch')
        return BuildResult(spec.key,entry/'build'/executable,record['sha256'],entry/'build',status,manifest_path)

    def obtain(self,spec:BuildSpec,builder:Callable[[Path],BuildProduct]):
        """Return a verified frozen build; always run the oracle separately.

        The builder receives a private empty directory. It must raise on failed
        compilation and return an executable path relative to that directory.
        No correctness PASS, output vectors, or oracle status is accepted here.
        """
        spec.assert_unchanged();entry=self.root/'objects'/spec.key
        with (self.root/'locks'/f'{spec.key}.lock').open('a+b') as lock:
            deadline=time.monotonic()+self.lock_timeout
            while True:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:
                    if time.monotonic()>=deadline:raise CacheError('cache key lock timed out')
                    time.sleep(0.05)
            spec.assert_unchanged()
            repaired=False
            if entry.exists() or entry.is_symlink():
                try:
                    result=self._verify(spec,entry,'hit')
                    self.log(f'[build-cache] hit key={spec.key} executable_sha256={result.executable_sha256}')
                    return result
                except (OSError,ValueError,KeyError,TypeError,InvalidArtifact) as error:
                    quarantine=self.root/'quarantine'/f'{spec.key}-{uuid.uuid4().hex}'
                    old_mode=None
                    if entry.is_dir() and not entry.is_symlink():
                        old_mode=stat.S_IMODE(entry.stat().st_mode);entry.chmod(old_mode|0o200)
                    os.replace(entry,quarantine)
                    if old_mode is not None:quarantine.chmod(old_mode)
                    repaired=True
                    self.log(f'[build-cache] rejected key={spec.key} reason={error}; preserved={quarantine}')
            stage=Path(tempfile.mkdtemp(prefix=spec.key+'-',dir=self.root/'staging'))
            try:
                work=stage/'build';work.mkdir()
                self.log(f'[build-cache] miss key={spec.key}; compiling')
                product=builder(work)
                if not isinstance(product,BuildProduct):raise InvalidArtifact('builder must return BuildProduct')
                relative=_relative(product.executable)
                inventory=_inventory(work,frozen=False)
                record=inventory['files'].get(relative.as_posix())
                if record is None or not record['mode']&0o111:raise InvalidArtifact('successful build did not produce an executable')
                tracked=spec.tracked_paths();work_real=work.resolve()
                for dependency in product.dependencies:
                    resolved=Path(dependency).resolve()
                    if not resolved.is_relative_to(work_real) and str(resolved) not in tracked:
                        raise UntrackedDependency(f'undeclared compiler dependency: {resolved}')
                spec.assert_unchanged()
                manifest=dict(schema=SCHEMA,key=spec.key,inputs=spec.inputs,executable=relative.as_posix(),
                              executable_sha256=record['sha256'],outputs=inventory)
                manifest_path=stage/'manifest.json'
                with manifest_path.open('wb') as stream:
                    stream.write(canonical(manifest));stream.flush();os.fsync(stream.fileno())
                _freeze(stage)
                # Same-filesystem rename publishes complete entries only. The
                # per-key lock prevents duplicate writers and concurrent hits
                # from observing any partial build or publication.
                os.replace(stage,entry)
                entry.chmod(stat.S_IMODE(entry.stat().st_mode)&0o555)
                result=self._verify(spec,entry,'repaired' if repaired else 'built')
                self.log(f'[build-cache] {result.cache_status} key={spec.key} executable_sha256={result.executable_sha256}')
                return result
            finally:_discard_private_stage(stage)
