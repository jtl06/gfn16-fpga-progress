"""Two exact regenerable PCH caches from one completed AW7 integration gate only."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import socket
import stat
import subprocess

if __package__:
    from .cleanup_data27_full_pch import identity, digest, require
else:
    from cleanup_data27_full_pch import identity, digest, require

BASE=Path('/home/jtl/gfn-fpga-lab/agent-work/square-core27-rootpipe/profiles/small-v1/fpga/artifacts')
LOCK=Path('/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')
RECEIPT=Path('/home/jtl/gfn-fpga-lab/fpga/tools/rootpipe-integration-aw7-pch-cleanup-v1.json')
PREFIX='Vgenefer_square_core27_stream_rootpipe__pch.h.'
GATES={
    7:('gfn-core27-rootpipe-aw7-v1.scope','cc0a83f3b698923b8f9a1e2c966cee1fe73d8405f67930530248e422dcc36525',{
        'fast':(101675475,101679104,'95d542406ecb7cf040fcc1b87db1cd81df0264441ca247ac5d72cd823d181b73'),
        'slow':(100405620,100409344,'7ced983ea4503e8d6eb866ca75bd15901ffb2967f2ba91ba714ef4e2478754be')})}


def stopped():
    for unit,_,_ in GATES.values():
        output=subprocess.check_output(['systemctl','--user','show',unit,'-p','ActiveState','-p','SubState'],text=True)
        require(dict(line.split('=',1) for line in output.splitlines())==
                {'ActiveState':'inactive','SubState':'dead'},'gate still active: '+unit)


def protected(excluded):
    result={}
    for aw in GATES:
        root=BASE/f'aw{aw}-v1'
        require(root.resolve()==root,'noncanonical gate directory')
        for path in sorted(root.rglob('*')):
            require(not path.is_symlink(),'symlink in gate')
            if path.is_dir():continue
            require(stat.S_ISREG(path.lstat().st_mode),'nonregular gate member')
            if path not in excluded:result[str(path)]=digest(path)
    return result


def run(apply=False):
    require(socket.gethostname()=='aethia' and os.getuid()==1000 and os.getgid()==1000,'aethia/jtl only')
    require(LOCK.resolve()==LOCK and LOCK.is_file(),'existing canonical shared lock required')
    with LOCK.open('r') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);stopped()
        targets=[]
        for aw,(_,report_sha,kinds) in GATES.items():
            root=BASE/f'aw{aw}-v1'
            require(digest(root/'report.json')==report_sha,'gate report changed')
            report=json.loads((root/'report.json').read_text())
            require(report['status']=='passed' and report['aw']==[aw],'gate not passed')
            for name,value in report['artifacts'].items():
                path=root/name
                require(not Path(name).is_absolute() and path.resolve().is_relative_to(root),'artifact outside gate')
                require(digest(path)==value,'indexed artifact changed')
            for kind,(size,allocated,value) in kinds.items():
                path=root/f'build-aw{aw}'/(PREFIX+kind+'.gch');info=identity(path)
                require(path.resolve()==path,'noncanonical PCH')
                require((info[2],info[9],info[6],info[7],info[8])==(size,allocated,1,1000,1000) and
                        not info[5]&0o111,'PCH size/link/owner/mode changed')
                with path.open('rb') as stream:require(stream.read(4)==b'gpch','not GCC PCH')
                require(digest(path)==value,'PCH hash changed')
                targets.append(dict(path=str(path),identity=info,sha256=value))
        excluded={Path(row['path']) for row in targets};before=protected(excluded)
        result=dict(status='inventoried_not_removed',targets=targets,protected_sha256=before,
                    tool_sha256=digest(Path(__file__)),
                    helper_sha256=digest(Path(__file__).with_name('cleanup_data27_full_pch.py')),
                    allocated_bytes=sum(row['identity'][9] for row in targets),removed=[],
                    recovery='Regenerate two PCH caches from retained generated headers/toolchain; all objects, executables, sources and results preserved.')
        if not apply:return result
        require(not RECEIPT.exists(),'receipt exists; do not blindly retry')
        stopped();require(protected(excluded)==before,'retained files changed before removal')
        with RECEIPT.open('x') as receipt:
            try:
                for row in targets:
                    path=Path(row['path'])
                    require(identity(path)==row['identity'] and digest(path)==row['sha256'],'PCH changed before unlink')
                    path.unlink();result['removed'].append(str(path))
                require(protected(set())==before,'retained files changed after removal')
                stopped();result['status']='removed_two_pch_caches_retained_hashes_verified'
            except BaseException as error:
                result.update(status='failed_or_partial',error=repr(error));raise
            finally:
                json.dump(result,receipt,indent=2);receipt.write('\n');receipt.flush();os.fsync(receipt.fileno())
        return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true')
    result=run(parser.parse_args().apply)
    print(json.dumps({key:result[key] for key in ('status','allocated_bytes','recovery')},indent=2))
