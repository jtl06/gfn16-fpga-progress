"""Data-only wide stage bound to the corrected callable runtime/package."""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='20581efa4daadb13ec986224ed5fc1c86df339e5508fd400a5f09340482a83f9'
PACKAGE_SHA='36ba765ff5da04a845fdfa22a56084296bcfc9a7b9e3c93cc093d134c918cadb'
EXECUTOR_SHA='0342e1a85f70ec3ba0afe3612f408d9e2ccffb770ebcef7b2e4352f228ff7ff5'


def module():
    raw=(HERE/'native_threaded_wide_stage_v1.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('frozen safe wide stage')
    text=raw.decode().replace('native_threaded_wide_package_v1.py','native_threaded_wide_package_v2.py').replace('9632fc4f55038052add52cc8bdce1cdc2398093baf5d9561677637cdad9b2d56',PACKAGE_SHA)
    text=text.replace('native_threaded_wide_v1.py','native_threaded_wide_v2.py').replace('75bd5bae7ffa549db530c02a46c527d5d996391980385e2a28c3d5c39adac9a1',EXECUTOR_SHA)
    value=types.ModuleType('_wide_callable_stage');value.__file__=str(Path(__file__).resolve())
    exec(compile(text,'[wide callable source stage]','exec'),value.__dict__)
    return value


base=module()
profile_from_payload=base.profile_from_payload
HARDWARE=base.HARDWARE
HARDWARE_SHA=base.HARDWARE_SHA
OVERLAY=base.OVERLAY
OVERLAY_SHA=base.OVERLAY_SHA
worker=base.worker
stage=base.stage


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    command=sub.add_parser('stage');command.add_argument('--archive',type=Path,required=True)
    command.add_argument('--archive-sha256',required=True);command.add_argument('--ticket-sha256',required=True)
    args=parser.parse_args();print(json.dumps(stage(args.archive,args.archive_sha256,args.ticket_sha256),indent=2))
