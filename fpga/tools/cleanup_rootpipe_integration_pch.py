"""Four exact regenerable PCH caches from two completed integration gates only."""
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
RECEIPT=Path('/home/jtl/gfn-fpga-lab/fpga/tools/rootpipe-integration-small-pch-cleanup-v1.json')
PREFIX='Vgenefer_square_core27_stream_rootpipe__pch.h.'
GATES={
    1:('gfn-core27-rootpipe-small-v1.scope','b32d3cddb5699769937f945b6038c0848c85618c4954e2b75d63f38528782505',{
        'fast':(101632156,101638144,'5f093d091f5b4b86f79a7358947305467752f445450f7333918fd0e42bd24894'),
        'slow':(100362210,100364288,'4d52f81a37467fafe21739d843b4ff6bde1ca975bb2652675701fc0b580e5901')}),
    5:('gfn-core27-rootpipe-aw5-v1.scope','1539d56d06baae8ffbdd7f3b921f62733caf5426b347ab64f55e021018bfc7d1',{
        'fast':(101551295,101552128,'7b98ba22292ae4e4781eeae566c75820332a8d4b120100718e594292883a8665'),
        'slow':(100276966,100282368,'b1e350f6654983707f8e12f7feed57fd6647ba4e3b0f0968aea837b92366c3e6')})}


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
                    recovery='Regenerate four PCH caches from retained generated headers/toolchain; all objects, executables, sources and results preserved.')
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
                stopped();result['status']='removed_four_pch_caches_retained_hashes_verified'
            except BaseException as error:
                result.update(status='failed_or_partial',error=repr(error));raise
            finally:
                json.dump(result,receipt,indent=2);receipt.write('\n');receipt.flush();os.fsync(receipt.fileno())
        return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true')
    result=run(parser.parse_args().apply)
    print(json.dumps({key:result[key] for key in ('status','allocated_bytes','recovery')},indent=2))
