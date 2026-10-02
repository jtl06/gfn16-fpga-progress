"""Pinned 546-file historical-component PCH-only cleanup; never cleans caches.

Run as stdin Python with --save-inventory, copy that file byte-for-byte,
then review and supply its exact SHA
with --manifest and --manifest-sha --apply --confirm REMOVE_546_HISTORICAL_COMPONENT_PCH.
V2 prevents loss of integer timestamp precision through JS JSON conversion.
No source tree mutation except546 explicit verified .gch unlinks is permitted.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import re
import socket
import stat

ENTRY=Path('/home/jtl/gfn-fpga-lab/agent-work')
ROOTS=tuple(ENTRY/name for name in ('ntt27-tiled','ntt-pair-banked','ntt27-folded','ntt-wide','ntt27-routepipe','ntt27-prefetch','carry-stream-pipe','ntt27','ntt27-generated-final'))
LOCK=ENTRY/'square-core/fpga/artifacts/compile.lock'
SELECTION=Path('/dev/shm/aethia-historical-component-pch-selection-v1.json')
SELECTION_SHA='368f276af81529879be62a11642368b3b9ad10e5a18b7c03adbbf008a402cf26'
TAILSCALED_PREFIX_SHA='0634666c51506105945e8837beb44e44fa778bbe8f983ed99b2a34d442d232c3'
TOOLS={'make','gmake','gcc','g++','cc','c++','cc1','cc1plus','clang','clang++','verilator','verilator_bin','yosys','sby','iverilog','vvp','pytest','pytest-3','ld','ld.bfd','ld.gold','as'}
CONFIRM='REMOVE_546_HISTORICAL_COMPONENT_PCH'
RECEIPT=Path('/dev/shm/historical-component-pch-cleanup-v1.json')
INVENTORY=Path('/dev/shm/historical-component-pch-inventory-v1.json')


def require(ok,message):
    if not ok:raise RuntimeError(message)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()


def identity(path):
    s=path.lstat()
    require(path.resolve()==path and stat.S_ISREG(s.st_mode),'noncanonical regular file: '+str(path))
    return dict(device=s.st_dev,inode=s.st_ino,size=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=s.st_mode,nlink=s.st_nlink,uid=s.st_uid,allocated=s.st_blocks*512)


def digest(path):
    before=identity(path)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as stream:
        h=hashlib.sha256()
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    require(identity(path)==before,'file changed while hashing')
    return h.hexdigest()


def target_record(path):
    require(any(path.is_relative_to(root) for root in ROOTS) and re.fullmatch(r'V[A-Za-z0-9_]+__pch\.h\.(fast|slow)\.gch',path.name) is not None,'target outside exact historical roots/PCH names')
    info=identity(path)
    require(info['uid']==1000 and info['nlink']==1 and not info['mode']&0o111,'PCH owner/link/execute bit')
    with path.open('rb') as stream:require(stream.read(4)==b'gpch','not GCC PCH')
    prefix=path.name.split('__pch.h.',1)[0]
    header=path.with_name(prefix+'__pch.h');exe=path.with_name(prefix)
    require(header.is_file() and exe.is_file() and exe.stat().st_mode&0o111,'retained header/executable absent')
    return dict(path=str(path),identity=info,sha256=digest(path),header_sha256=digest(header),executable_sha256=digest(exe))


def protected(excluded):
    result={}
    for root in ROOTS:
        require(root.resolve()==root and root.is_dir(),'unsafe root')
        h=hashlib.sha256();count=0;size=0
        for path in sorted(root.rglob('*')):
            require(not path.is_symlink(),'symlink in gate tree')
            if path.is_dir():continue
            require(stat.S_ISREG(path.lstat().st_mode),'nonregular gate member')
            if path in excluded:continue
            record=dict(path=str(path.relative_to(root)),sha256=digest(path),size=path.stat().st_size,mode=stat.S_IMODE(path.stat().st_mode))
            h.update(canonical(record)+b'\n');count+=1;size+=record['size']
        result[str(root)]=dict(sha256=h.hexdigest(),files=count,bytes=size)
    return result


def proc_identity(proc):
    raw = (proc / 'stat').read_text()
    fields = raw[raw.rfind(')') + 2:].split()
    return int(fields[1]), int(fields[19])  # PPid and process start tick.


def process_ancestors():
    result = set(); pid = os.getpid()
    while pid > 1:
        require(pid not in result, 'cyclic process ancestry')
        result.add(pid)
        pid, _ = proc_identity(Path('/proc') / str(pid))
    return result


def is_job(comm, argv):
    names = [comm, *(Path(arg).name for arg in argv if arg)]
    if any(name in TOOLS or name.startswith(('Vgenefer_', 'Vntt_', 'Vsquare_', 'Vmontgomery_'))
           for name in names):
        return True
    return any(('gfn-fpga-lab' in arg and ('/fpga/reference/' in arg or
                '/fpga/tools/run_' in arg)) or
               (arg.endswith('.py') and any(word in Path(arg).name for word in
                 ('regression', 'replay', 'fault', 'pytest', 'qualified', 'recovery')))
               for arg in argv)


def infrastructure(comm, argv, pid, ancestors, own_argv):
    if comm == 'systemd' and argv == ['/usr/lib/systemd/systemd', '--user']:
        return 'exact-systemd-user'
    if comm == '(sd-pam)' and argv == ['(sd-pam)']:
        return 'exact-sd-pam'
    if comm != 'tailscaled' or pid not in ancestors or len(argv) != 15:
        return None
    if hashlib.sha256(canonical(argv[:-1])).hexdigest() != TAILSCALED_PREFIX_SHA:
        return None
    if not argv[-1].startswith('--cmd='):
        return None
    command = argv[-1][len('--cmd='):]
    # Exact argv equality rejects separators, redirection, extra commands and
    # unrelated Python invocations. The daemon must be our own SSH ancestor.
    if shlex.split(command) != own_argv:
        return None
    return 'exact-current-ssh-ancestor'


def quiet_processes():
    ancestors = process_ancestors()
    own_argv = [a.decode() for a in Path('/proc/self/cmdline').read_bytes().split(b'\0') if a]
    require(own_argv[0] in ('python3', '/usr/bin/python3') and own_argv[1] == '-',
            'helper must run as the exact stdin Python invocation')
    approved = []; inspected = 0
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name) == os.getpid():
            continue
        try:
            identity = proc_identity(proc)
            argv = [a.decode() for a in (proc / 'cmdline').read_bytes().split(b'\0') if a]
            comm = (proc / 'comm').read_text().strip()
            if not argv:
                continue
            require(not is_job(comm, argv), 'active HDL/compiler/test job PID ' + proc.name)
            require(not any(str(ENTRY) in a for a in argv), 'cache consumer argv PID ' + proc.name)
            if proc.stat().st_uid != os.getuid():
                continue  # All UIDs' readable argv/comm checked for jobs.
            inspected += 1; gaps = set()
            for label in ('cwd', 'exe'):
                try:
                    require(not os.readlink(proc / label).startswith(str(ENTRY)),
                            'cache consumer ' + label + ' PID ' + proc.name)
                except PermissionError:
                    gaps.add(label)
            try:
                require(str(ENTRY) not in (proc / 'maps').read_text(), 'cache mapping PID ' + proc.name)
            except PermissionError:
                gaps.add('maps')
            try:
                for fd in (proc / 'fd').iterdir():
                    try:
                        require(not os.readlink(fd).startswith(str(ENTRY)), 'cache fd PID ' + proc.name)
                    except FileNotFoundError:
                        pass
                    except PermissionError:
                        gaps.add('fd_links')
            except PermissionError:
                gaps.add('fd')
            require(proc_identity(proc) == identity, 'process identity changed PID ' + proc.name)
            if gaps:
                category = infrastructure(comm, argv, int(proc.name), ancestors, own_argv)
                require(category is not None, 'unresolved /proc visibility PID ' + proc.name)
                if category == 'exact-current-ssh-ancestor':
                    command = argv[-1][len('--cmd='):]
                    for ancestor in ancestors - {os.getpid(), int(proc.name)}:
                        a = Path('/proc') / str(ancestor)
                        shell_argv = [v.decode() for v in (a / 'cmdline').read_bytes().split(b'\0') if v]
                        if (a / 'comm').read_text().strip() == 'zsh':
                            require(len(shell_argv) == 3 and shell_argv[0] in ('zsh', '/usr/bin/zsh')
                                    and shell_argv[1] == '-c' and shell_argv[2] == command,
                                    'SSH shell invocation mismatch')
                approved.append(dict(pid=int(proc.name), category=category, inaccessible_fields=sorted(gaps)))
        except (FileNotFoundError, ProcessLookupError):
            pass
    return dict(active_jobs=0, detected_consumers=0, inspected_same_user=inspected,
                narrowed_infrastructure_exceptions=approved)



def load_selection():
    require(SELECTION.resolve()==SELECTION and digest(SELECTION)==SELECTION_SHA,'exact selection file SHA')
    value=json.loads(SELECTION.read_bytes())
    require(value['root']==str(ENTRY) and value['roots']==[str(p) for p in ROOTS] and len(value['targets'])==546 and len(set(value['targets']))==546,'exact selection scope')
    for name in value['targets']:
        p=Path(name);require(not p.is_absolute() and '..' not in p.parts and any((ENTRY/p).is_relative_to(r) for r in ROOTS),'selection target traversal/scope')
    return value


def inventory():
    selection=load_selection();targets=[];reports={}
    for root in ROOTS:
        require(root.resolve()==root and not list(root.rglob('manifest.json')),'unsafe or manifest-indexed root cannot be trimmed')
    for name,pin in selection['report_pins'].items():
        report=ENTRY/name
        require(any(report.is_relative_to(r) for r in ROOTS) and digest(report)==pin,'report selection changed')
        data=json.loads(report.read_bytes())
        require(data.get('status') in ('passed','failed') and '.gch' not in json.dumps(data),'report incomplete or explicitly indexes PCH')
        reports[str(report)]=pin
    targets=[target_record(ENTRY/name) for name in selection['targets']]
    require(len(targets)==546,'expected exactly546 preflight PCH files')
    require(sum(r['identity']['allocated'] for r in targets)==selection['allocated_bytes'],'selection allocated size changed')
    excluded={Path(row['path']) for row in targets}
    return dict(schema=2,status='inventoried_not_removed',selection_sha256=SELECTION_SHA,roots=[str(p) for p in ROOTS],targets=targets,report_sha256=reports,protected=protected(excluded),allocated_bytes=sum(r['identity']['allocated'] for r in targets),recovery='Regenerate PCH from retained generated headers/compiler. All executables/objects/generated source/source trees/snapshots/vectors/reports/logs retained. No frozen executable cache modified.')


def verify_manifest(value):
    require(value['schema']==2 and value['status']=='inventoried_not_removed' and value['roots']==[str(p) for p in ROOTS],'manifest identity/schema')
    require(len(value['targets'])==546 and len({x['path'] for x in value['targets']})==546,'exact unique546 targets')
    selection=load_selection()
    require(value['selection_sha256']==SELECTION_SHA and [r['path'] for r in value['targets']]==[str(ENTRY/n) for n in selection['targets']],'exact target selection order')
    for row in value['targets']:require(target_record(Path(row['path']))==row,'reviewed target changed')
    for name,h in value['report_sha256'].items():require(name in {str(ENTRY/n) for n in selection['report_pins']} and digest(Path(name))==h,'report changed')
    require(value['report_sha256']=={str(ENTRY/n):h for n,h in selection['report_pins'].items()},'report closure')
    require(protected({Path(r['path']) for r in value['targets']})==value['protected'],'protected tree changed')


def save_inventory(value,path):
    """Write exact Python integer JSON bytes, never JS-parsed inventory output."""
    require(path==INVENTORY and path.parent.resolve()==path.parent,'exact fresh tmpfs inventory path required')
    raw=(json.dumps(value,indent=2)+'\n').encode('utf-8')
    # Exclusive creation rejects existing files and symlinks; no replacement.
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    require(path.read_bytes()==raw,'inventory persisted bytes changed')
    return dict(status=value['status'],inventory=str(path),inventory_sha256=hashlib.sha256(raw).hexdigest(),schema=2,target_count=len(value['targets']),allocated_bytes=value['allocated_bytes'],integer_encoding='Native Python JSON integer tokens; SCP raw bytes without JSON parse/reemit',process_check=value['process_check'])


def run(args):
    require(socket.gethostname()=='aethia' and os.getuid()==1000,'aethia/jtl only')
    require(LOCK.resolve()==LOCK,'unsafe existing lock')
    fd=os.open(LOCK,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as lock:
        require(stat.S_ISREG(os.fstat(lock.fileno()).st_mode),'nonregular lock')
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        processes=quiet_processes()
        if not args.apply:
            require(not args.manifest and not args.manifest_sha,'inventory takes no manifest')
            require(args.save_inventory,'inventory requires --save-inventory; never parse/reemit timestamps through JS')
            result=inventory();result['process_check']=processes;quiet_processes()
            return save_inventory(result,Path(args.save_inventory))
        require(not args.save_inventory,'apply cannot save/replace inventory')
        require(args.confirm==CONFIRM and args.manifest and args.manifest_sha,'explicit confirmation and reviewed receipt required')
        raw=Path(args.manifest).read_bytes()
        require(hashlib.sha256(raw).hexdigest()==args.manifest_sha,'reviewed inventory SHA mismatch')
        value=json.loads(raw);verify_manifest(value);quiet_processes()
        result=dict(status='failed_or_partial',inventory_sha256=args.manifest_sha,allocated_bytes=value['allocated_bytes'],removed=[],protected=value['protected'],process_check=processes,recovery=value['recovery'])
        require(not RECEIPT.exists(),'receipt exists; no blind retry')
        with RECEIPT.open('x') as receipt:
            try:
                for row in value['targets']:
                    path=Path(row['path']);require(target_record(path)==row,'target changed immediately before unlink')
                    path.unlink();result['removed'].append(str(path))
                require(protected(set())==value['protected'],'protected files changed after unlink')
                result['process_check_after']=quiet_processes();result['status']='removed_546_historical_component_pch_retained_tree_verified'
            except BaseException as error:
                result['error']=repr(error);raise
            finally:
                json.dump(result,receipt,indent=2);receipt.write('\n');receipt.flush();os.fsync(receipt.fileno())
        return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--save-inventory',metavar='EXACT_V2_TMPFS_PATH');parser.add_argument('--apply',action='store_true');parser.add_argument('--confirm');parser.add_argument('--manifest');parser.add_argument('--manifest-sha')
    print(json.dumps(run(parser.parse_args()),indent=2))
