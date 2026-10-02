"""One-shot exact-scope cleanup; retain all non-object content and verify hashes.

Inventory first, then require its SHA256 to remove only enumerated standalone
compiler .o/.a/.gch files. No cache entries, directories, RTL or binaries removed.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import stat

BASE=Path('/home/jtl/gfn-fpga-lab/agent-work/ntt-vector/fpga/artifacts')
TARGETS=[BASE/'vector-full-v1/lanes16',BASE/'vector-full-v1/lanes4',BASE/'vector-quick-v1/lanes4']


def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def inactive():
    for p in Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name)==os.getpid():continue
        try:
            cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            cwd=str((p/'cwd').resolve())
        except (OSError,ProcessLookupError):continue
        if any(str(t) in cmd or cwd==str(t) or cwd.startswith(str(t)+'/') for t in TARGETS):
            raise ValueError('target referenced by active process '+p.name)


def identity(path):
    if path.is_symlink():raise ValueError('symlink not allowed')
    s=path.stat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1:raise ValueError('nonregular/shared file')
    return dict(size=s.st_size,inode=s.st_ino,mtime_ns=s.st_mtime_ns)


def inventory():
    inactive();objects=[];protected={};builds=set()
    for target in TARGETS:
        if target.resolve()!=target or not target.is_dir():raise ValueError('unresolved target')
        if json.loads((target/'report.json').read_text()).get('status')!='passed':
            raise ValueError('target gate not passed')
        for p in sorted(target.rglob('*')):
            if p.is_symlink():raise ValueError('symlink in target')
            if not p.is_file():continue
            relative=p.relative_to(target)
            disposable=(len(relative.parts)==2 and relative.parts[0].startswith('build-')
                        and p.suffix in ('.o','.a','.gch'))
            if disposable:
                objects.append(dict(path=str(p),**identity(p)));builds.add(str(p.parent))
            else:protected[str(p)]=digest(p)
    inactive()
    if len(builds)!=28 or sum(x['size'] for x in objects)!=4342477953:
        raise ValueError('inventory differs from independently audited28-build scope')
    return dict(status='inventoried_not_removed',created_at=datetime.now(timezone.utc).isoformat(),
                targets=list(map(str,TARGETS)),build_directories=sorted(builds),objects=objects,
                protected_sha256=protected,recovery='Compiler objects can be rebuilt; retained executables and evidence remain usable.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--apply-sha256')
    args=parser.parse_args()
    if not args.apply_sha256:
        record=inventory()
        with args.manifest.open('x') as f:json.dump(record,f,indent=2)
        print(json.dumps(dict(status=record['status'],files=len(record['objects']),
            bytes=sum(x['size'] for x in record['objects']),protected=len(record['protected_sha256']),
            manifest_sha256=digest(args.manifest),targets=record['targets'])))
        return
    if digest(args.manifest)!=args.apply_sha256:raise ValueError('manifest changed')
    record=json.loads(args.manifest.read_text())
    fresh=inventory()
    for key in ('targets','build_directories','objects','protected_sha256'):
        if fresh[key]!=record[key]:raise ValueError('inventory/evidence changed: '+key)
    audit=args.manifest.with_name(args.manifest.stem+'-applied.json')
    with audit.open('x') as f:json.dump(dict(status='removal_started',manifest_sha256=args.apply_sha256),f)
    inactive()
    for row in record['objects']:
        p=Path(row['path'])
        if identity(p)!={k:row[k] for k in ('size','inode','mtime_ns')}:raise ValueError('file changed')
        p.unlink()
    for name,h in record['protected_sha256'].items():
        if digest(Path(name))!=h:raise ValueError('retained file changed: '+name)
    result=dict(status='completed_all_retained_hashes_verified',manifest_sha256=args.apply_sha256,
                files_removed=len(record['objects']),bytes_removed=sum(x['size'] for x in record['objects']),
                protected_files=len(record['protected_sha256']),finished_at=datetime.now(timezone.utc).isoformat())
    audit.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
