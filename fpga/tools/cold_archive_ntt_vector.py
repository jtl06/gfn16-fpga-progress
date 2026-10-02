"""Verified cold archive of one exact inactive experiment; no broad cleanup."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tarfile

ROOT=Path('/home/jtl/gfn-fpga-lab/agent-work/ntt-vector')
STAGE=Path('/home/jtl/gfn-fpga-lab/fpga/artifacts/cold-archives/ntt-vector-20260930')


def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def inactive():
    for p in Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name)==os.getpid():continue
        try:
            values=[(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace'),
                    str((p/'cwd').resolve()),str((p/'exe').resolve())]
        except (OSError,ProcessLookupError):continue
        if any(str(ROOT) in x for x in values):raise ValueError('active reference: '+p.name)


def files():
    if ROOT.resolve()!=ROOT or not ROOT.is_dir():raise ValueError('unexpected source root')
    result={}
    for p in sorted(ROOT.rglob('*')):
        if p.is_symlink() or not (p.is_dir() or p.is_file()):raise ValueError('special/link entry')
        if p.is_file():
            s=p.stat()
            result[str(p.relative_to(ROOT))]=dict(sha256=sha(p),size=s.st_size,
                inode=s.st_ino,mtime_ns=s.st_mtime_ns)
    if not result:raise ValueError('empty source')
    return result


def verify(archive,manifest):
    m=json.loads(manifest.read_text());seen={}
    if m['source_root']!=str(ROOT) or sha(archive)!=m['archive_sha256']:
        raise ValueError('archive/root mismatch')
    with tarfile.open(archive,'r:gz') as t:
        for member in t:
            path=Path(member.name)
            if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0]!='ntt-vector':
                raise ValueError('unsafe archive path')
            if member.isdir():continue
            if not member.isfile():raise ValueError('archive contains nonregular file')
            name=str(Path(*path.parts[1:]))
            if name in seen:raise ValueError('duplicate archive member')
            stream=t.extractfile(member)
            seen[name]=dict(sha256=hashlib.file_digest(stream,'sha256').hexdigest(),size=member.size)
    expected={n:{k:v[k] for k in ('sha256','size')} for n,v in m['files'].items()}
    if seen!=expected:raise ValueError('archive file-set/content mismatch')
    return dict(status='all_archive_members_verified',host=platform.node(),
        archive=str(archive.resolve()),manifest_sha256=sha(manifest),archive_sha256=sha(archive),
        files=len(seen),original_bytes=sum(x['size'] for x in seen.values()),verified_at=datetime.now(timezone.utc).isoformat())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('pack','verify','remove-source'))
    parser.add_argument('--archive',type=Path)
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--receipt',type=Path)
    args=parser.parse_args()
    if args.mode=='verify':
        print(json.dumps(verify(args.archive,args.manifest)));return
    if not platform.node().startswith('aethia'):raise ValueError('source actions only on aethia')
    if args.mode=='pack':
        inactive();before=files();STAGE.mkdir(parents=True,exist_ok=False)
        archive=STAGE/'ntt-vector.tar.gz';manifest=STAGE/'manifest.json'
        subprocess.run(['tar','-czf',str(archive),'-C',str(ROOT.parent),ROOT.name],check=True)
        if files()!=before:raise ValueError('source changed during archive')
        inactive()
        manifest.write_text(json.dumps(dict(source_root=str(ROOT),files=before,
            archive_sha256=sha(archive)),indent=2)+'\n')
        print(json.dumps(verify(archive,manifest)));return
    archive=STAGE/'ntt-vector.tar.gz';manifest=STAGE/'manifest.json'
    local=verify(archive,manifest);remote=json.loads(args.receipt.read_text())
    if (remote.get('host')!='gfn16-pilot-c4' or remote.get('status')!='all_archive_members_verified'
        or any(remote.get(k)!=local[k] for k in ('manifest_sha256','archive_sha256','files','original_bytes'))):
        raise ValueError('missing matching GCP verification receipt')
    m=json.loads(manifest.read_text());inactive()
    if files()!=m['files']:raise ValueError('source changed since copy')
    # Exact enumerated regular files only, then empty subdirectories. Keep root
    # with an archive locator; the staging archive remains as an extra copy.
    for name,record in m['files'].items():
        p=ROOT/name;s=p.stat()
        if (s.st_ino,s.st_size,s.st_mtime_ns)!=(record['inode'],record['size'],record['mtime_ns']):
            raise ValueError('source changed before removal')
        p.unlink()
    for d in sorted((p for p in ROOT.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):d.rmdir()
    locator=dict(status='archived_to_gcp',verification=remote,
                 local_staging_archive=str(archive),restore='Extract verified tar archive under agent-work to restore ntt-vector.')
    (ROOT/'ARCHIVED.json').write_text(json.dumps(locator,indent=2)+'\n')
    print(json.dumps(dict(status=locator['status'],files_removed=local['files'],bytes_removed=local['original_bytes'])))


if __name__=='__main__':main()
