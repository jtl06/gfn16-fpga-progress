"""Exact safe staging of the same-hardware Azure8GiB envelope."""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9'


def worker():
    raw=(HERE/'native_package_v3.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('frozen safe stage implementation')
    text=raw.decode()
    changes=[('native_class_package_v1.py','native_class_package_burst8_v1.py'),
      ('61ae733fbd269a040aa73f02cf1d86810216fba24b57dc9ab4d8aade896a4932','8d7c794ffd6e136b15ccf75a6e72621ae24886a3bf0cd088eca3a42acf6fc59f'),
      ('native_class_v1.py','native_class_burst8_v1.py'),
      ('1a50703e0554575e323697a11d5bbf43778603f78b1c978406734d7678529516','8c7234c341ad20823520761c429e030f26b8ed4e90cb4b171f3f91f328cfe767'),
      ('PROFILES={',"PROFILES={'cloud/azure-burst16-memory8-profiles-v1.json':'04fe25064f68301526492ebd232dba201fb15469e88c9f2cee0d3389215a9808',"),
      ("    else:name,key='cloud/azure-f32-static-profiles-v1.json',selected",
       "    elif selected.startswith('azure-burst16-static8g'):name,key='cloud/azure-burst16-memory8-profiles-v1.json',selected\n    else:name,key='cloud/azure-f32-static-profiles-v1.json',selected")]
    for old,new in changes:
        if old not in text:raise ValueError('memory8 stage source anchor')
        text=text.replace(old,new)
    result=types.ModuleType('_burst8_stage');result.__file__=str(Path(__file__).resolve())
    exec(compile(text,str(HERE/'native_package_v3.py')+'[burst8GiB]','exec'),result.__dict__)
    return result.worker()


def stage(archive,archive_sha,ticket_sha):return worker().stage(archive,archive_sha,ticket_sha)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    command=sub.add_parser('stage');command.add_argument('--archive',type=Path,required=True)
    command.add_argument('--archive-sha256',required=True);command.add_argument('--ticket-sha256',required=True)
    args=parser.parse_args();print(json.dumps(stage(args.archive,args.archive_sha256,args.ticket_sha256),indent=2))
