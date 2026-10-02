"""Remove exactly two authorized inactive GCC PCH caches; preserve all else."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import stat

ROOT=Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/host64-config-reject-v1')
LOCK=ROOT.parent/'compile.lock'
RECEIPT=Path('/home/jtl/gfn-fpga-lab/host64-config-pch-cleanup-v1.json')
PREFIX='Vgenefer_vector_config_tb'
TARGETS={ROOT/'build'/(PREFIX+'__pch.h.fast.gch'):101184865,
         ROOT/'build'/(PREFIX+'__pch.h.slow.gch'):99922759}
PINS={'test.log':'da0959d08d9fd9fc8358bcb214dbc535d7a3ba71a841f79aa24690c5d68c87c7',
      'build/'+PREFIX:'af3bd0a31f6a63f82c67e9745a13b5497af5fd6bb9c9dc07f69fdc2e2cbbfee2'}

def need(ok,why):
    if not ok: raise RuntimeError(why)

def identity(p):
    s=p.lstat()
    need(p.resolve()==p and stat.S_ISREG(s.st_mode),'canonical regular file: '+str(p))
    return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_nlink,s.st_uid,s.st_blocks*512]

def sha(p):
    before=identity(p)
    with p.open('rb') as f: value=hashlib.file_digest(f,'sha256').hexdigest()
    need(identity(p)==before,'hash race: '+str(p))
    return value

def idle():
    for proc in Path('/proc').glob('[0-9]*'):
        if proc.name==str(os.getpid()): continue
        try:
            if proc.stat().st_uid!=os.getuid(): continue
            cmd=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            comm=(proc/'comm').read_text().strip()
            need(comm not in ('cc1plus','verilator_bin','make','g++'),'compiler active: '+proc.name)
            need(str(ROOT) not in cmd,'target referenced by process: '+proc.name)
            # Ubuntu's user manager is non-dumpable even for its owner. It is
            # not a compiler/model; its child jobs are independently inspected.
            if comm=='systemd' and cmd.strip()=='/usr/lib/systemd/systemd --user': continue
            if comm=='(sd-pam)' and cmd.strip()=='(sd-pam)': continue
            # The setuid Tailscale SSH transport is also non-dumpable. Its
            # command was checked above; separately inspect the spawned job.
            if comm=='tailscaled' and cmd.startswith('/usr/sbin/tailscaled be-child ssh '): continue
            for link in [proc/'cwd',proc/'exe',*list((proc/'fd').iterdir())]:
                try: target=link.resolve(strict=True)
                except FileNotFoundError: continue
                need(not target.is_relative_to(ROOT),'target open by process: '+proc.name)
        except (FileNotFoundError,ProcessLookupError): continue

def protected():
    files={}
    for p in sorted(ROOT.rglob('*')):
        need(not p.is_symlink(),'symlink in target tree')
        if p.is_dir(): continue
        if p not in TARGETS: files[str(p.relative_to(ROOT))]=sha(p)
    return files

def run(apply=False):
    need(socket.gethostname()=='aethia' and os.getuid()==1000,'aethia/jtl only')
    need(ROOT.resolve()==ROOT and LOCK.resolve()==LOCK and LOCK.is_file(),'canonical root/lock')
    with LOCK.open('r') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB); idle()
        for n,h in PINS.items(): need(sha(ROOT/n)==h,'retained test/executable changed')
        need((ROOT/'build'/(PREFIX+'__pch.h')).is_file(),'regenerating header absent')
        targets=[]
        for p,size in TARGETS.items():
            info=identity(p)
            need(info[2]==size and info[6]==1 and info[7]==1000 and not info[5]&0o111,'PCH identity')
            with p.open('rb') as f: need(f.read(4)==b'gpch','GCC PCH magic')
            targets.append(dict(path=str(p),identity=info,sha256=sha(p)))
        before=protected(); idle()
        result=dict(status='inventoried_not_removed',targets=targets,protected_sha256=before,
                    allocated_bytes=sum(x['identity'][8] for x in targets),removed=[],
                    tool_sha256=sha(Path(__file__).resolve()),
                    recovery='Regenerate only PCH from retained generated header and compiler; executable, objects, source snapshot, logs and all other files retained.')
        if not apply: return result
        need(not RECEIPT.exists(),'receipt exists; no blind retry')
        with RECEIPT.open('x') as receipt:
            try:
                need(protected()==before,'protected files changed'); idle()
                for row in targets:
                    p=Path(row['path'])
                    need(identity(p)==row['identity'] and sha(p)==row['sha256'],'target changed')
                    p.unlink(); result['removed'].append(str(p))
                need(protected()==before,'retained hashes changed'); idle()
                result['status']='removed_two_inactive_pch_retained_hashes_verified'
            except BaseException as e:
                result.update(status='failed_or_partial',error=repr(e)); raise
            finally:
                json.dump(result,receipt,indent=2); receipt.write('\n'); receipt.flush(); os.fsync(receipt.fileno())
        return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--apply',action='store_true')
    result=run(parser.parse_args().apply)
    print(json.dumps({k:result[k] for k in ('status','allocated_bytes','removed','recovery')}))
