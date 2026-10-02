"""Add safe self-staging for frozen shared-v1 packets; never launches a job.

V1 stays byte-identical. Stage is repeatable only for a completed, hash-identical
capture, never retries a partial stage, and never erases results or run claims.
Future threaded/profile plumbing is deliberately separate from this milestone.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path,PurePosixPath
import pwd
import re
import shutil
import socket
import stat
import tarfile

HERE=Path(__file__).resolve().parent
SHARED_SHA='7bae7c05f7a3a5a83c55f9eb4f9dc33476b3051841661da8a45627d20424e10b'
PACKAGE_SHA='1ae024a4efe23410758f6cd17507dc1941d809803c539ee84bb2565f069a0219'
MAX_ARCHIVE=512<<20
MAX_TOTAL=1<<30
MAX_FILE=256<<20
MAX_FILES=20000
GIB=1<<30


def need(ok,why):
    if not ok:raise ValueError(why)


def digest(raw):return hashlib.sha256(raw).hexdigest()


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def pin(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{64}',value),'SHA256 pin')
    return value


def relative(name):
    need(type(name) is str and name not in ('','.') and str(PurePosixPath(name))==name
         and not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts,'safe relative member')
    return name


def regular(path):
    need(path.is_absolute() and path.resolve()==path and path.is_file() and not path.is_symlink()
         and path.stat().st_nlink==1,'canonical single-link input')


def members(archive):
    result={};total=0
    for member in archive:
        name=relative(member.name)
        need(member.isfile() and not member.issparse() and name not in result,'unique regular archive member')
        need(0<=member.size<=MAX_FILE,'bounded member size');total+=member.size
        need(total<=MAX_TOTAL and len(result)<MAX_FILES,'bounded archive')
        raw=archive.extractfile(member).read(MAX_FILE+1)
        need(len(raw)==member.size,'exact member bytes');result[name]=raw
    return result


def inspect_archive(path,archive_sha,ticket_sha):
    regular(path);pin(archive_sha);pin(ticket_sha)
    need(path.stat().st_size<=MAX_ARCHIVE and sha(path)==archive_sha,'bounded exact archive')
    with tarfile.open(path,'r:gz') as archive:payload=members(archive)
    need(digest(payload['ticket.json'])==ticket_sha,'exact ticket')
    ticket=json.loads(payload['ticket.json']);manifest=json.loads(payload['manifest.json'])
    need(ticket['schema']=='shared-native-ticket-v1' and ticket['failure_policy']=='stop'
         and ticket['promotion_allowed'] is False and ticket['max_seconds']==3700,'bounded v1 ticket')
    need(re.fullmatch('[a-z][a-z0-9-]{0,79}',ticket['id']) and ticket['phase'] in ('lint','run'),'bounded ticket id/phase')
    need(manifest['schema']=='native-source-gate-v1' and manifest['status']=='prepared_not_executed'
         and manifest['phase']==ticket['phase'] and manifest['cpu_profile']==ticket['profile'],'matching manifest')
    need(digest(payload['manifest.json'])==ticket['manifest_sha256']
         and payload['capture/approved-manifest.json']==payload['manifest.json'],'manifest byte identity')
    sources=manifest['sources'];need(type(sources) is dict and sources,'source pins')
    for name,value in sources.items():relative(name);pin(value)
    expected={'ticket.json','manifest.json','capture/approved-manifest.json','capture/capture.json','capture/source.tar.gz'}|{'capture/source/fpga/'+n for n in sources}
    need(set(payload)==expected,'exact outer archive closure')
    for name,value in sources.items():need(digest(payload['capture/source/fpga/'+name])==value,'source byte identity')
    capture=json.loads(payload['capture/capture.json'])
    need(capture['status']=='captured_not_executed' and capture['source_sha256']==sources
         and capture['manifest_sha256']==ticket['manifest_sha256']
         and capture['native_source_root']==manifest['source_root']
         and capture['archive_sha256']==digest(payload['capture/source.tar.gz']),'snapshot receipt identity')
    with tarfile.open(fileobj=io.BytesIO(payload['capture/source.tar.gz']),mode='r:gz') as archive:
        nested=members(archive)
    need({n:digest(v) for n,v in nested.items()}=={'fpga/'+n:v for n,v in sources.items()},'nested source archive identity')
    for name,value in ticket['tools'].items():
        need(sources.get('tools/'+relative(name))==pin(value),'closed helper identity')
    need(sources.get('tools/native_shared_v1.py')==SHARED_SHA
         and sources.get('tools/native_package_v1.py')==PACKAGE_SHA,'known v1 policy/worker')
    # Only now inspect known trusted helper code. No candidate module executes.
    namespace=dict(__name__='_stage_known_shared_v1',__file__=str(HERE/'native_shared_v1.py'))
    exec(compile(payload['capture/source/fpga/tools/native_shared_v1.py'],'[pinned shared-v1 policy]','exec'),namespace)
    need(ticket['profile'] in namespace['PROFILES'],'approved profile')
    profile=namespace['PROFILES'][ticket['profile']]
    root=Path(profile['base'])/'jobs'/ticket['id']
    need(ticket['native_root']==str(root) and manifest['source_root']==str(root/'capture/source/fpga')
         and manifest['output_parent']==str(root/'output') and manifest['host']==profile['host'],'fixed job/source/output placement')
    need(sha(path)==archive_sha,'archive stable after validation')
    return payload,ticket,manifest,profile


def host_check(profile):
    need(socket.gethostname()==profile['host'] and pwd.getpwuid(os.geteuid()).pw_name==profile['user'],'approved staging host/user')


def canonical_directory(path):
    need(path.resolve()==path and not path.is_symlink(),'canonical directory')
    if path.exists():need(path.is_dir() and path.stat().st_uid==os.geteuid(),'own directory')


def shared_file(path):
    canonical_directory(path.parent)
    fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    info=os.fstat(fd)
    need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==os.geteuid(),'own single-link shared lock')
    return fd


def verify_existing(root,payload,archive_sha,ticket_sha):
    receipt=root/'stage-receipt.json';regular(receipt);record=json.loads(receipt.read_text())
    need(record['status']=='staged_exact_inputs' and record['archive_sha256']==archive_sha
         and record['ticket_sha256']==ticket_sha,'completed identical prior stage')
    for name,raw in payload.items():
        path=root/name;regular(path);need(sha(path)==digest(raw),'existing staged input drift')
    source=root/'capture/source/fpga'
    actual=set()
    for path in source.rglob('*'):
        need(not path.is_symlink(),'existing source symlink')
        need(path.is_file() or path.is_dir(),'existing source special node')
        if path.is_file():actual.add(str(path.relative_to(root)))
    need(actual=={n for n in payload if n.startswith('capture/source/fpga/')},'existing source closure')
    canonical_directory(root/'output')
    return dict(record,status='already_staged_exact_inputs',runtime_outputs_preserved=True)


def stage(archive_path,archive_sha,ticket_sha):
    payload,ticket,manifest,profile=inspect_archive(archive_path,archive_sha,ticket_sha)
    host_check(profile);base=Path(profile['base']);root=Path(ticket['native_root'])
    canonical_directory(base);canonical_directory(root)
    need(not (base/'PAUSE').exists(),'host PAUSE')
    existing=base
    while not existing.exists():existing=existing.parent
    need(shutil.disk_usage(existing).free>=10*GIB+sum(map(len,payload.values())),'stage durable floor plus full payload')
    # No destination effects occur before all source/metadata/host checks above.
    base.mkdir(parents=True,exist_ok=True)
    fd=shared_file(base/'.stage.lock')
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        canonical_directory(root.parent);root.parent.mkdir(exist_ok=True)
        if root.exists():return verify_existing(root,payload,archive_sha,ticket_sha)
        root.mkdir()  # Atomic refusal; partial stages are never replaced.
        result=dict(status='staging',archive_sha256=archive_sha,ticket_sha256=ticket_sha,
            stager_sha256=sha(Path(__file__).resolve()),root=str(root),inputs={n:digest(v) for n,v in payload.items()})
        try:
            for name,raw in payload.items():
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('xb') as stream:stream.write(raw)
                need(sha(target)==digest(raw),'staged copy identity')
            (root/'output').mkdir()
            claims=base/'claims';canonical_directory(claims);claims.mkdir(exist_ok=True)
            lock=Path(profile['lock']);lockfd=shared_file(lock);os.close(lockfd)
            need(sha(archive_path)==archive_sha,'archive changed during stage')
            result.update(status='staged_exact_inputs',files=len(payload),bytes=sum(map(len,payload.values())),
                claims_directory=str(claims),compile_lock=str(lock),run_claims_modified=False)
            with (root/'stage-receipt.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
            return result
        except BaseException as error:
            result.update(status='failed_stage_preserved',error=repr(error))
            with (root/'stage-failure.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
            raise
    finally:os.close(fd)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('stage');p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--archive-sha256',required=True);p.add_argument('--ticket-sha256',required=True)
    args=parser.parse_args();print(json.dumps(stage(args.archive,args.archive_sha256,args.ticket_sha256),indent=2))
