"""Inventory or remove only six new full-v2 data27 GCC PCH caches.

Default is read-only. --apply requires separate authorization. Never touches the
retained original prefetch models or any executable/object/library/source/log.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import subprocess

ROOT=Path('/home/jtl/gfn-fpga-lab/agent-work/ntt27-prefetch-data27/profiles/full-v2/fpga/artifacts/full-v2')
LOCK=Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')
RECEIPT=Path('/home/jtl/gfn-fpga-lab/fpga/tools/data27-full-pch-cleanup-v1.json')
SCOPE='ntt27-data27-full-v2.scope'
REPORT_SHA='583302236e86b21e1fcd55267f0410be27713be05ba79c1691657f954632fb2b'
PREFIX='Vgenefer_ntt_banked27_prefetch_engine'
PCH_UID=1000
PCH_GID=1000
# Ordered fast, slow: exact byte and allocated-byte counts from read-only inventory.
SIZES={1:((82777003,82780160),(81506940,81510400)),
       2:((82743414,82747392),(81477505,81477632)),
       3:((82743555,82747392),(81477562,81477632))}
EXE_SHAS={1:'a7331dbbdb0cba1efbc2715766f6f73492ebf6710e7880dd089c480f4cb7a47a',
          2:'27ede9ca6f9e17c2e482cd04efb62a08b59f1e6ea80cc2515490fa18e685a5a8',
          3:'d389851f5ab1a21cabbb3ea89862a2649cdd81488fc47d69eccdb9353dec8bd6'}

def require(value,message):
    if not value:raise RuntimeError(message)

def identity(path):
    s=path.lstat()
    require(stat.S_ISREG(s.st_mode) and not path.is_symlink(),'not a regular file: '+str(path))
    return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,
            s.st_mode,s.st_nlink,s.st_uid,s.st_gid,s.st_blocks*512)

def digest(path):
    before=identity(path)
    with path.open('rb') as handle:value=hashlib.file_digest(handle,'sha256').hexdigest()
    require(identity(path)==before,'file changed during hashing: '+str(path))
    return value

def scope_inactive():
    result=subprocess.run(['systemctl','--user','show',SCOPE,'-p','ActiveState','-p','SubState'],
                          capture_output=True,text=True,check=True)
    values=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
    require(values=={'ActiveState':'inactive','SubState':'dead'},'full-v2 scope is not inactive/dead')

def snapshot(excluded):
    result={}
    for path in sorted(ROOT.rglob('*')):
        require(not path.is_symlink(),'symlink in completed tree: '+str(path))
        if path.is_dir():continue
        require(stat.S_ISREG(path.lstat().st_mode),'nonregular entry in completed tree: '+str(path))
        if path not in excluded:result[str(path)]=digest(path)
    return result

def validate_report():
    require(digest(ROOT/'report.json')==REPORT_SHA,'raw full-v2 report changed')
    report=json.loads((ROOT/'report.json').read_text())
    require(report['status']=='passed' and report['inputs_rehashed_after'] and report['whole_integer_crt'],
            'full-v2 correctness gate incomplete')
    require(len(report['steps'])==221 and all(row['passed'] for row in report['steps']),
            'full-v2 steps incomplete')
    require(len(report['matched_cases'])==93,'full-v2 pair coverage incomplete')
    candidates=[row for row in report['executables'] if row['kind']=='candidate']
    require(len(candidates)==3 and {row['field'] for row in candidates}=={1,2,3},'candidate field set changed')
    for row in candidates:
        field=row['field'];path=ROOT/f'build-candidate-p{field}'/PREFIX
        require(row['path']==str(path) and row['sha256']==EXE_SHAS[field],'candidate executable receipt changed')
        require(digest(path)==EXE_SHAS[field],'candidate executable bytes changed')
    # All indexed non-PCH artifacts must still match the final raw report.
    for relative,expected in report['artifact_sha256'].items():
        path=ROOT/relative
        require(not Path(relative).is_absolute() and path.resolve().is_relative_to(ROOT),'invalid indexed artifact path')
        require(digest(path)==expected,'indexed artifact changed: '+relative)

def run(apply=False):
    require(socket.gethostname()=='aethia','cleanup restricted to aethia')
    require(os.getuid()==PCH_UID and os.getgid()==PCH_GID,'cleanup must run as the inventoried owner')
    require(ROOT.resolve()==ROOT and ROOT.is_dir(),'noncanonical full-v2 directory')
    require(not RECEIPT.resolve().is_relative_to(ROOT),'receipt cannot be inside protected tree')
    with LOCK.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        scope_inactive();validate_report()
        targets=[]
        for field,sizes in SIZES.items():
            parent=ROOT/f'build-candidate-p{field}'
            require(parent.resolve()==parent,'noncanonical candidate directory')
            for kind,(size,allocated) in zip(('fast','slow'),sizes):
                path=parent/(PREFIX+'__pch.h.'+kind+'.gch');info=identity(path)
                require(info[2]==size and info[9]==allocated,'PCH size/allocation changed')
                require(info[6]==1 and info[7]==PCH_UID and info[8]==PCH_GID and not(info[5]&0o111),
                        'PCH link/owner/mode changed')
                with path.open('rb') as handle:require(handle.read(4)==b'gpch','not a GCC PCH')
                targets.append({'path':str(path),'identity':info,'sha256':digest(path)})
        excluded={Path(row['path']) for row in targets}
        observed={path for field in (1,2,3) for path in (ROOT/f'build-candidate-p{field}').glob('*.gch')}
        require(len(targets)==6 and observed==excluded,'unexpected candidate PCH file set')
        protected=snapshot(excluded)
        result={'status':'inventoried_not_removed','scope':SCOPE,'report_sha256':REPORT_SHA,
            'tool_sha256':digest(Path(__file__)),'targets':targets,
            'bytes':sum(row['identity'][2] for row in targets),
            'allocated_bytes':sum(row['identity'][9] for row in targets),
            'protected_sha256':protected,
            'recovery':'Regenerate only GCC PCH caches from retained generated headers/toolchain; all executables, objects, libraries, sources and diagnostic evidence remain.'}
        if not apply:
            require(snapshot(excluded)==protected,'protected files changed during inventory')
            return result
        require(not RECEIPT.exists(),'cleanup receipt already exists; no blind retry')
        scope_inactive();validate_report()
        require(snapshot(excluded)==protected,'protected files changed before removal')
        removed=[]
        with RECEIPT.open('x') as receipt:
            try:
                for row in targets:
                    path=Path(row['path'])
                    require(path.resolve()==path,'PCH path changed')
                    require(tuple(row['identity'])==identity(path),'PCH identity changed before removal')
                    require(digest(path)==row['sha256'],'PCH contents changed before removal')
                    path.unlink();removed.append(str(path))
                require(snapshot(set())==protected,'retained file hashes changed after removal')
                scope_inactive()
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
    print(json.dumps({key:result[key] for key in ('status','bytes','allocated_bytes','recovery')},indent=2))
