"""Exact-scope legacy object cleanup: inventory first, explicit frozen-SHA apply.

This new tool does not replace cleanup_ntt_vector_objects.py. Only the three
approved legacy experiments are eligible; vector and folded are excluded.
No directories, source, executable, log, report or cache entries are removed.
All retained files in the three artifact roots are hashed before and after.
Run on the owning Linux host with complete /proc visibility. No sudo or remote
commands are invoked. Apply takes the existing cooperative compiler lock;
uncooperative filesystem/process changes cannot be made atomic by /proc scans.
No deletion is performed without --apply-sha256 matching a saved inventory.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat

APPROVED_SHA256='2cd250649181258c424b239966d75ed4d3c774cceb67b08fa847adaa6b18d5dd'
EXPERIMENTS=('ntt27','ntt27-routepipe','ntt-wide')
BASE=Path('/home/jtl/gfn-fpga-lab/agent-work')
EXPECTED_BUILDS=84
EXPECTED_BYTES=14_140_462_060
SUFFIXES={'.o','.a','.gch'}
COMPILE_LOCK=BASE/'square-core/fpga/artifacts/compile.lock'


def require(ok,message):
    if not ok:raise ValueError(message)


def stamp():return datetime.now(timezone.utc).isoformat()


def sha(data):return hashlib.sha256(data).hexdigest()


def identity_stat(s):
    return dict(device=s.st_dev,inode=s.st_ino,nlink=s.st_nlink,size=s.st_size,
                mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=s.st_mode)


def identity(path):
    s=path.lstat()
    require(stat.S_ISREG(s.st_mode),'nonregular/symlink file: '+str(path))
    return identity_stat(s)


def digest(path):
    before=identity(path)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:
        require(identity_stat(os.fstat(f.fileno()))==before,'file changed before hash')
        result=hashlib.file_digest(f,'sha256').hexdigest()
        require(identity_stat(os.fstat(f.fileno()))==before,'file changed during hash')
    require(identity(path)==before,'file replaced during hash')
    return result


def canonical_path(path):
    require(path.is_absolute() and str(path)==str(path.resolve()),'noncanonical/symlink path: '+str(path))


def scope(candidates):
    canonical_path(candidates)
    require(digest(candidates)==APPROVED_SHA256,'agent inventory SHA mismatch')
    raw=json.loads(candidates.read_text())
    require(raw.get('allowed_generated_suffixes')==['.o','.a','.gch'],'unexpected suffix policy')
    selected=[e for e in raw['experiments'] if e['experiment'] in EXPERIMENTS]
    require(sorted(e['experiment'] for e in selected)==sorted(EXPERIMENTS),'missing/duplicate approved experiment')
    roots=[];reports={};builds={}
    for experiment in selected:
        root=BASE/experiment['experiment']/'fpga/artifacts'
        require(experiment['recommended'] is True and experiment['artifact_root']==str(root),'root not approved')
        roots.append(str(root))
        for name,group in experiment['passed_report_groups'].items():
            report=Path(name)
            require(report.name=='report.json' and report.is_relative_to(root),'report outside scope')
            require(group['status']=='passed','audited report not passed')
            require(name not in reports,'duplicate report')
            reports[name]=group
            for build in group['build_directories']:
                p=Path(build)
                require(p.parent==report.parent and p.name.startswith('build-'),'build outside exact report group')
                require(build not in builds,'duplicate build')
                builds[build]=name
    require(len(builds)==EXPECTED_BUILDS,'approved build count differs')
    require(sum(g['bytes'] for g in reports.values())==EXPECTED_BYTES,'approved byte total differs')
    return dict(candidate_sha256=APPROVED_SHA256,roots=sorted(roots),reports=reports,builds=builds)


def inactive(roots,proc=Path('/proc')):
    require(proc.is_dir(),'Linux /proc required')
    targets=tuple(roots)
    for p in proc.iterdir():
        if not p.name.isdigit() or int(p.name)==os.getpid():continue
        try:
            command=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            # Kernel threads and zombies have no user-space command or cwd.
            # A blank command alone is not enough to skip an existing cwd.
            try:cwd=os.readlink(p/'cwd')
            except FileNotFoundError:
                if not command:continue
                raise
            executable=os.readlink(p/'exe')
        except FileNotFoundError:
            if not p.exists():continue  # Normal exit during /proc enumeration.
            raise ValueError('opaque live process '+p.name)
        except PermissionError as exc:
            raise ValueError('insufficient /proc visibility for process '+p.name) from exc
        for root in targets:
            if root in command or any(value==root or value.startswith(root+'/')
                                      for value in (cwd,executable.removesuffix(' (deleted)'))):
                raise ValueError('artifact root referenced by active process '+p.name)


def directory_identity(path):
    canonical_path(path);s=path.lstat()
    require(stat.S_ISDIR(s.st_mode),'non-directory in artifact tree')
    return dict(device=s.st_dev,inode=s.st_ino,mode=s.st_mode)


def executable(path,metadata):
    if metadata['mode'] & 0o111:return True
    with path.open('rb') as f:header=f.read(20)
    # A renamed ELF executable/shared image is protected even without +x.
    if header[:4]==b'\x7fELF' and len(header)>=18 and header[5] in (1,2):
        return int.from_bytes(header[16:18],'little' if header[5]==1 else 'big') in (2,3)
    return False


def scan(approved,removed=False):
    inactive(approved['roots']);objects=[];protected={};directories={};seen_builds=set()
    report_counts={name:dict(bytes=0,files=0) for name in approved['reports']}
    for name,group in approved['reports'].items():
        report=Path(name)
        require(digest(report)==group['report_sha256'],'passed report SHA changed: '+name)
        data=json.loads(report.read_text())
        require(data.get('status')=='passed','gate is not currently passed: '+name)
    for root_name in approved['roots']:
        root=Path(root_name);directories[str(root)]=directory_identity(root)
        for path in sorted(root.rglob('*')):
            require(not path.is_symlink(),'symlink in artifact root: '+str(path))
            if path.is_dir():
                directories[str(path)]=directory_identity(path)
                if str(path) in approved['builds']:seen_builds.add(str(path))
                continue
            meta=identity(path)
            disposable=(str(path.parent) in approved['builds'] and path.suffix in SUFFIXES
                        and not executable(path,meta))
            if disposable:
                require(meta['nlink']==1,'shared compiler object: '+str(path))
                require(identity(path)==meta,'object changed during classification')
                objects.append(dict(path=str(path),**meta))
                count=report_counts[approved['builds'][str(path.parent)]]
                count['bytes']+=meta['size'];count['files']+=1
            else:
                protected[str(path)]=dict(sha256=digest(path),identity=meta)
                require(identity(path)==meta,'retained file changed during inventory')
    require(seen_builds==set(approved['builds']),'missing approved build directory')
    for report,counts in report_counts.items():
        expected=approved['reports'][report]
        require(counts==dict(bytes=0,files=0) if removed else
                counts==dict(bytes=expected['bytes'],files=expected['files']),
                'exact object inventory differs: '+report)
        for name in expected['retained_executable_names']:
            for build in expected['build_directories']:
                require(str(Path(build)/name) in protected,'retained executable missing: '+build+'/'+name)
    inactive(approved['roots'])
    return dict(objects=objects,protected=protected,directories=directories)


def inventory(candidates):
    approved=scope(candidates);snapshot=scan(approved)
    # Repeat cheap identities/sets after all retained-file hashes; full scan
    # repeats at apply. This catches changes during a long inventory pass.
    for row in snapshot['objects']:
        require(identity(Path(row['path']))=={k:v for k,v in row.items() if k!='path'},'object changed during inventory')
    return dict(schema_version=1,status='inventoried_not_removed',created_at=stamp(),
                tool_sha256=digest(Path(__file__).resolve()),approved_scope=approved,**snapshot,
                recovery='Only rebuildable compiler objects are eligible; retained binaries, sources, logs and cache remain.',
                race_limit='Requires a quiet artifact tree; cooperative compiler lock and repeated proc/identity checks do not stop uncooperative writers.')


def outside(path,roots):
    canonical_path(path.parent)
    require(not any(path.is_relative_to(Path(root)) for root in roots),'audit/manifest must be outside artifact roots')


@contextmanager
def compiler_lock():
    canonical_path(COMPILE_LOCK)
    # Existing lock only: no creation or changes to compiler tooling.
    fd=os.open(COMPILE_LOCK,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally:os.close(fd)


def remove_exact(row,directories,roots):
    path=Path(row['path']);parent=path.parent
    require(directory_identity(parent)==directories[str(parent)],'build directory replaced')
    fd=os.open(parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        s=os.fstat(fd)
        require(dict(device=s.st_dev,inode=s.st_ino,mode=s.st_mode)==directories[str(parent)],'opened wrong build directory')
        inactive(roots)
        current=os.stat(path.name,dir_fd=fd,follow_symlinks=False)
        require(identity_stat(current)=={k:v for k,v in row.items() if k!='path'},'object identity changed before unlink')
        require(directory_identity(parent)==directories[str(parent)],'build moved before unlink')
        os.unlink(path.name,dir_fd=fd)
    finally:os.close(fd)


def apply(candidates,manifest,frozen_sha):
    require(len(frozen_sha)==64 and all(c in '0123456789abcdef' for c in frozen_sha),'invalid frozen manifest SHA')
    canonical_path(manifest)
    require(digest(manifest)==frozen_sha,'frozen manifest SHA changed')
    record=json.loads(manifest.read_text());approved=scope(candidates)
    require(record.get('schema_version')==1 and record.get('status')=='inventoried_not_removed','not an inventory manifest')
    require(record.get('tool_sha256')==digest(Path(__file__).resolve()),'cleanup tool changed since inventory')
    require(record['approved_scope']==approved,'approved scope changed')
    outside(manifest,approved['roots'])
    journal=manifest.with_name(manifest.name+'.apply.jsonl');outside(journal,approved['roots'])
    with compiler_lock():
        fresh=scan(approved)
        for key in ('objects','protected','directories'):
            require(fresh[key]==record[key],'pre-apply snapshot changed: '+key)
        require(digest(manifest)==frozen_sha,'manifest changed during prevalidation')
        # Exclusive journal creation prevents a retry from concealing partial
        # cleanup. No automatic resume: inspect a failed journal first.
        with journal.open('x') as audit:
            def event(value):
                audit.write(json.dumps(dict(at=stamp(),**value),sort_keys=True)+'\n')
                audit.flush();os.fsync(audit.fileno())
            removed=[]
            event(dict(status='removal_started',manifest_sha256=frozen_sha,scope_sha256=APPROVED_SHA256))
            try:
                for row in record['objects']:
                    remove_exact(row,record['directories'],approved['roots'])
                    removed.append(row['path'])
                    event(dict(status='object_removed',path=row['path'],bytes=row['size']))
                post=scan(approved,removed=True)
                require(post['protected']==record['protected'],'retained files/identities changed after removal')
                require(post['directories']==record['directories'],'directory set/identities changed after removal')
                require(digest(manifest)==frozen_sha,'manifest changed during apply')
                result=dict(status='completed_all_retained_hashes_verified',manifest_sha256=frozen_sha,
                            files_removed=len(removed),bytes_removed=sum(r['size'] for r in record['objects']),
                            protected_files=len(post['protected']),journal=str(journal))
                event(result);return result
            except BaseException as exc:
                event(dict(status='stopped_partial_or_failed',removed_count=len(removed),reason=str(exc)))
                raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--apply-sha256')
    args=parser.parse_args()
    if args.apply_sha256:
        print(json.dumps(apply(args.candidates,args.manifest,args.apply_sha256)));return
    record=inventory(args.candidates)
    outside(args.manifest,record['approved_scope']['roots'])
    with args.manifest.open('x') as f:
        json.dump(record,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    print(json.dumps(dict(status=record['status'],builds=len(record['approved_scope']['builds']),
                         files=len(record['objects']),bytes=sum(r['size'] for r in record['objects']),
                         protected_files=len(record['protected']),manifest_sha256=digest(args.manifest))))


if __name__=='__main__':main()
