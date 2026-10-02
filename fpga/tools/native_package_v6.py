"""Safe static staging for the r49 meter-v3 package; no dispatch."""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='9b2dc9048500d0e31d14b4ba7b64b4906b944486478cac8cc83c814d8d205e75'
PACKAGE_SHA='9ca500ca811740232017de9f3f852bc8e838e5384769e26c401ab891d3295564'

def worker():
    raw=(HERE/'native_package_v5.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('frozen observed-host stager')
    text=raw.decode().replace('native_class_package_v3.py','native_class_package_v4.py').replace('a8c42095d5d174b6bc622eb10774a0a581e6060b8366d981afabc39084ddcfdd',PACKAGE_SHA)
    module=types.ModuleType('_meter_v3_stage');module.__file__=str(Path(__file__).resolve())
    exec(compile(text,str(HERE/'native_package_v5.py')+'[r49]','exec'),module.__dict__)
    return module.worker()

def stage(archive,archive_sha,ticket_sha):return worker().stage(archive,archive_sha,ticket_sha)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    command=sub.add_parser('stage');command.add_argument('--archive',type=Path,required=True)
    command.add_argument('--archive-sha256',required=True);command.add_argument('--ticket-sha256',required=True)
    args=parser.parse_args();print(json.dumps(stage(args.archive,args.archive_sha256,args.ticket_sha256),indent=2))
