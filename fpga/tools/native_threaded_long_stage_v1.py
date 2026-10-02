"""Data-only safe stage for the fixed measured Azure thread2 5000s package."""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9'
PACKAGE_SHA='ef0da878723fd06184a2cb57396f628ad4c0546612830c595d4e075e056960b3'
EXECUTOR_SHA='8eeeabd2456fd29e10a8534e007c98baf5832e94cec753f509a97df38ab7c0db'
SHAPE=dict(id='t5b-burst23-thread2-continuous5000-v1',model_command_seconds=4500,
 ancillary_command_seconds=1800,overall_seconds=4800,outer_seconds=5000,
 stop_grace_seconds=15,lock_wait_seconds=1800,model_threads=2)


def worker():
    raw=(HERE/'native_package_v3.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('frozen safe stage')
    text=raw.decode()
    changes=[('native_class_package_v1.py','native_threaded_long_package_v1.py'),
      ('61ae733fbd269a040aa73f02cf1d86810216fba24b57dc9ab4d8aade896a4932',PACKAGE_SHA),
      ('native_class_v1.py','native_threaded_long_class_v1.py'),
      ('1a50703e0554575e323697a11d5bbf43778603f78b1c978406734d7678529516',EXECUTOR_SHA),
      ('PROFILES={',"PROFILES={'cloud/azure-burst16-static-profiles-v1.json':'eef2a816c7fc6ae5e53919b24b2bb135a16808d7ef7ccb7341395b0c030b596d',"),
      ('    mapping={',"    need(selected=='azure-burst16-static23-v1','exact measured pair')\n    mapping={\n      'azure-burst16-static23-v1':('cloud/azure-burst16-static-profiles-v1.json','azure-burst16-static23-v1'),"),
      ("    module=types.ModuleType('_class_stage')", "    text=text.replace(\"ticket['max_seconds']==3700\",\"ticket['max_seconds']==5000 and ticket['runtime_duration']==\"+repr(LONG_SHAPE)+\" and manifest['runtime_duration']['shape']==\"+repr(LONG_SHAPE))\n    module=types.ModuleType('_class_stage')")]
    for old,new in changes:
        if old not in text:raise ValueError('stage source anchor')
        text=text.replace(old,new)
    result=types.ModuleType('_threaded_long_stage');result.__file__=str(Path(__file__).resolve());result.LONG_SHAPE=SHAPE
    exec(compile(text,'[measured thread2 stage]','exec'),result.__dict__)
    return result.worker()


def stage(archive,archive_sha,ticket_sha):return worker().stage(archive,archive_sha,ticket_sha)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    command=sub.add_parser('stage');command.add_argument('--archive',type=Path,required=True)
    command.add_argument('--archive-sha256',required=True);command.add_argument('--ticket-sha256',required=True)
    args=parser.parse_args();print(json.dumps(stage(args.archive,args.archive_sha256,args.ticket_sha256),indent=2))
