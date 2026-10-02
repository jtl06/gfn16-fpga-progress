"""Safe stage binding for both frozen class package versions; no dispatch."""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9'
V2_SHA='03b6a81aa7d465487da97f854a79e9e43a19c9c637db6178587cfac02476f604'


def worker():
    raw=(HERE/'native_package_v3.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('frozen class stage parent')
    text=raw.decode()
    old="    for name,pin in [('tools/native_class_package_v1.py',CLASS_PACKAGE_SHA),('tools/native_class_v1.py',CLASS_EXECUTOR_SHA)]:"
    new="    if 'native_class_package_v2.py' in ticket['tools']:\n        need(sources.get('tools/native_class_package_v2.py') == '"+V2_SHA+"', 'known strict host-budget worker')\n"+old
    if text.count(old)!=1:raise ValueError('unique strict package stage anchor')
    text=text.replace(old,new,1)
    module=types.ModuleType('_strict_class_stage');module.__file__=str(Path(__file__).resolve())
    exec(compile(text,str(HERE/'native_package_v3.py')+'[strict-package]','exec'),module.__dict__)
    return module.worker()


def stage(archive,archive_sha,ticket_sha):return worker().stage(archive,archive_sha,ticket_sha)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    command=sub.add_parser('stage');command.add_argument('--archive',type=Path,required=True)
    command.add_argument('--archive-sha256',required=True);command.add_argument('--ticket-sha256',required=True)
    args=parser.parse_args();print(json.dumps(stage(args.archive,args.archive_sha256,args.ticket_sha256),indent=2))
