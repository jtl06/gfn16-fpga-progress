"""Read-only broad artifact metadata inventory; writes one fresh tmpfs receipt.

No deletion/archive/compression. Nanosecond integers saved natively by Python;
copy the receipt byte-for-byte. Cache subtrees are counted separately, not
classified as trim-able. This does not attest that all candidates are idle.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import stat

ROOT=Path('/home/jtl/gfn-fpga-lab/agent-work')
OUTPUT=Path('/dev/shm/aethia-broad-cleanup-inventory-v1.json')
CUT=1790726400000000000  # 2026-09-30 00:00 UTC; old does not mean disposable.


def main():
    if socket.gethostname()!='aethia' or ROOT.resolve()!=ROOT:
        raise RuntimeError('exact aethia root only')
    totals={};rows=[];caches=[];reports={};symlinks=[]
    for directory,children,files in os.walk(ROOT):
        parent=Path(directory);family=parent.relative_to(ROOT).parts[0] if parent!=ROOT else '.'
        bucket=totals.setdefault(family,dict(allocated=0,regular_bytes=0,files=0,extensions={}))
        for child in children[:]:
            path=parent/child
            if path.is_symlink():children.remove(child);symlinks.append(str(path));continue
            if child.startswith('executable-cache'):
                children.remove(child)
                info=dict(root=str(path),entries=[],allocated=0)
                for d,sub,names in os.walk(path):
                    sub[:]=[n for n in sub if not (Path(d)/n).is_symlink()]
                    for name in names:
                        p=Path(d)/name;s=p.lstat()
                        if not stat.S_ISREG(s.st_mode):continue
                        info['allocated']+=s.st_blocks*512
                        if name=='manifest.json' and p.parent.parent.name=='objects':
                            raw=p.read_bytes();m=json.loads(raw)
                            info['entries'].append(dict(path=str(p.parent),key=m.get('key'),manifest_sha256=hashlib.sha256(raw).hexdigest(),executable_sha256=m.get('executable_sha256'),output_files=len(m.get('outputs',{}).get('files',{})),output_bytes=sum(r['size'] for r in m.get('outputs',{}).get('files',{}).values()),mtime_ns=s.st_mtime_ns))
                caches.append(info)
        for name in files:
            path=parent/name;s=path.lstat()
            if not stat.S_ISREG(s.st_mode):
                symlinks.append(str(path));continue
            extension=path.suffix or '(no suffix)';allocated=s.st_blocks*512
            bucket['allocated']+=allocated;bucket['regular_bytes']+=s.st_size;bucket['files']+=1
            x=bucket['extensions'].setdefault(extension,dict(files=0,bytes=0,allocated=0));x['files']+=1;x['bytes']+=s.st_size;x['allocated']+=allocated
            if name=='report.json':
                try:
                    raw=path.read_bytes();m=json.loads(raw)
                    reports[str(path)]=dict(status=m.get('status'),sha256=hashlib.sha256(raw).hexdigest(),artifact_keys=list(m.get('artifacts',{})),generated_keys=list(m.get('generated_source_sha256',{})))
                except (ValueError,OSError):reports[str(path)]=dict(status='unparsed')
            if extension not in ('.gch','.o','.a'):continue
            record=dict(path=str(path),size=s.st_size,allocated=allocated,device=s.st_dev,inode=s.st_ino,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=s.st_mode,nlink=s.st_nlink,uid=s.st_uid,older_than_cutoff=s.st_mtime_ns<CUT)
            if extension=='.gch':
                with path.open('rb') as stream:record['gcc_pch_magic']=stream.read(4)==b'gpch'
                header_name=name.rsplit('.',2)[0]
                header=parent/header_name
                record['generated_header']=str(header) if header.is_file() else None
                prefix=name.split('__pch.h.',1)[0]
                exe=parent/prefix
                record['retained_executable']=str(exe) if exe.is_file() and exe.stat().st_mode&0o111 else None
            rows.append(record)
    value=dict(schema=1,status='metadata_only_not_deletion_admission',asof_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),root=str(ROOT),cutoff_utc='2026-09-30T00:00:00Z',families=totals,caches=caches,candidates=rows,reports=reports,symlink_or_nonregular_paths=symlinks,limitations=['Allocated bytes of regular files only; directory blocks excluded. Cache bytes are separate from family non-cache totals.','No source/output content hashes except small reports and cache manifests. No compiler lock or consumer-idle admission.','PCH/object/library extension and age are metadata, not permission to remove. All manifest-indexed/active/current prerequisite objects must be excluded.'])
    raw=(json.dumps(value,indent=2)+'\n').encode()
    fd=os.open(OUTPUT,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    print(json.dumps(dict(status=value['status'],inventory=str(OUTPUT),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),candidate_files=len(rows),family_noncache_allocated=sum(x['allocated'] for x in totals.values()),cache_allocated=sum(x['allocated'] for x in caches))))


if __name__=='__main__':main()
