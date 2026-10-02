"""Safe staging for observed Azure/GCP/local class-package-v3 captures."""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9'
PACKAGE_SHA='a8c42095d5d174b6bc622eb10774a0a581e6060b8366d981afabc39084ddcfdd'
EXECUTOR_SHA='5a3ab8b8306e74de9d6dd9fcbe26ee185a25dff95ac6a5e1b51503ce00e543c3'
F16_SHA='c6d0dd6cc08f305492f7569eb0dfd08a855e1c75373917c3c971efae8fc871eb'


def worker():
    raw=(HERE/'native_package_v3.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('frozen class stager')
    text=raw.decode()
    changes=[('native_class_package_v1.py','native_class_package_v3.py'),
      ('61ae733fbd269a040aa73f02cf1d86810216fba24b57dc9ab4d8aade896a4932',PACKAGE_SHA),
      ('native_class_v1.py','native_class_v2.py'),
      ('1a50703e0554575e323697a11d5bbf43778603f78b1c978406734d7678529516',EXECUTOR_SHA),
      ('PROFILES={',"PROFILES={'cloud/azure-native-static-profiles-v1.json':'"+F16_SHA+"',"),
      ("    else:name,key='cloud/azure-f32-static-profiles-v1.json',selected",
       "    elif selected.startswith('azure-f16-static'):name,key='cloud/azure-native-static-profiles-v1.json',selected\n    else:name,key='cloud/azure-f32-static-profiles-v1.json',selected")]
    for old,new in changes:
        if old not in text:raise ValueError('unique observed Azure stager anchor')
        text=text.replace(old,new)
    module=types.ModuleType('_observed_azure_stage');module.__file__=str(Path(__file__).resolve())
    exec(compile(text,str(HERE/'native_package_v3.py')+'[observed-Azure]','exec'),module.__dict__)
    return module.worker()


def stage(archive,archive_sha,ticket_sha):return worker().stage(archive,archive_sha,ticket_sha)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    command=sub.add_parser('stage');command.add_argument('--archive',type=Path,required=True)
    command.add_argument('--archive-sha256',required=True);command.add_argument('--ticket-sha256',required=True)
    args=parser.parse_args();print(json.dumps(stage(args.archive,args.archive_sha256,args.ticket_sha256),indent=2))
