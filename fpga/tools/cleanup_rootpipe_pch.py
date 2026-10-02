"""Remove only six regenerable PCH caches from this task's completed full gate.

Not a replacement for the sudo-only legacy cleanup: no older experiment or
object/library/executable is eligible. Uses the shared compile lock and requires
the exact owning scope inactive, pinned passing report and executable hashes.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

ROOT=Path('/home/jtl/gfn-fpga-lab/agent-work/ntt27-rootpipe-full/fpga/artifacts/full-v1')
LOCK=Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')
RECEIPT=Path('/home/jtl/gfn-fpga-lab/fpga/tools/rootpipe-full-pch-cleanup-v1.json')
REPORT_SHA='285fa5fe19835ffd61a49fee951fb65e356e952cf9a11a8304e25a8c3a764ee0'
PREFIX='Vgenefer_ntt_banked27_rootpipe_engine'
SIZES={1:(82648714,83918908),2:(82648494,83918712),3:(82648322,83918884)}

def require(value,message):
    if not value:raise RuntimeError(message)

def identity(path):
    s=path.lstat()
    require(stat.S_ISREG(s.st_mode) and not path.is_symlink(),'not a regular file: '+str(path))
    return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_nlink,s.st_uid)

def digest(path):
    before=identity(path)
    with path.open('rb') as f:result=hashlib.file_digest(f,'sha256').hexdigest()
    require(identity(path)==before,'file changed during hashing')
    return result

def scope_inactive():
    result=subprocess.run(['systemctl','--user','show','gfn-ntt27-rootpipe-full-v1.scope',
                           '-p','ActiveState','--value'],capture_output=True,text=True,check=True)
    require(result.stdout.strip()=='inactive','full-gate scope is not inactive')

def snapshot(excluded):
    result={}
    for path in sorted(ROOT.rglob('*')):
        require(not path.is_symlink(),'symlink in completed build tree')
        if path.is_file() and path not in excluded:result[str(path)]=digest(path)
    return result

def run(apply=False):
    require(ROOT.resolve()==ROOT,'noncanonical full-gate path')
    with LOCK.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        scope_inactive()
        require(digest(ROOT/'report.json')==REPORT_SHA,'full report changed')
        report=json.loads((ROOT/'report.json').read_text())
        require(report['status']=='passed' and len(report['builds'])==3,'full gate incomplete')
        for build in report['builds']:
            require(digest(Path(build['executable']))==build['executable_sha256'],'model executable changed')
        targets=[]
        for field,sizes in SIZES.items():
            parent=ROOT/f'build-ntt27-rootpipe-p{field}-aw16-l64'
            require(parent.resolve()==parent,'noncanonical build directory')
            for kind,size in zip(('slow','fast'),sizes):
                path=parent/(PREFIX+'__pch.h.'+kind+'.gch');info=identity(path)
                require(info[2]==size and info[6]==1 and info[7]==os.getuid() and not(info[5]&0o111),'PCH identity mismatch')
                with path.open('rb') as f:require(f.read(4)==b'gpch','not a GCC precompiled header')
                targets.append(dict(path=str(path),identity=info,sha256=digest(path)))
        excluded={Path(row['path']) for row in targets};protected=snapshot(excluded)
        result=dict(status='inventoried_not_removed',report_sha256=REPORT_SHA,tool_sha256=digest(Path(__file__)),
            targets=targets,bytes=sum(row['identity'][2] for row in targets),protected_sha256=protected,
            recovery='Regenerate only PCH caches from retained generated headers/toolchain; model executables and all objects/libraries are retained.')
        if not apply:return result
        require(not RECEIPT.exists(),'cleanup already recorded; do not retry blindly')
        scope_inactive();removed=[]
        with RECEIPT.open('x') as receipt:
            try:
                for row in targets:
                    path=Path(row['path']);require(path.resolve()==path,'cache path changed')
                    require(tuple(row['identity'])==identity(path),'cache changed before removal')
                    path.unlink();removed.append(str(path))
                require(snapshot(set())==protected,'retained file hashes changed')
                result['status']='removed_six_pch_caches_retained_hashes_verified'
            except BaseException as exc:
                result.update(status='failed_or_partial',error=repr(exc));raise
            finally:
                result['removed']=removed
                json.dump(result,receipt,indent=2);receipt.write('\n');receipt.flush();os.fsync(receipt.fileno())
        return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true')
    args=parser.parse_args();result=run(args.apply)
    print(json.dumps({k:result[k] for k in ('status','bytes','recovery')},indent=2))
