"""Safe data-only stage for user75 serial packets on existing burst pairs."""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
PARENT_SHA = '5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9'
PACKAGE_SHA = '4adfd234e8b7d5f20f73d6e275cfee666fca9cce6ad031e93380e3a8a55ca461'


def worker():
    raw = (HERE / 'native_package_v3.py').read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError('frozen safe static stager')
    text = raw.decode()
    for old, new in [
        ('native_class_package_v1.py', 'native_class_package_azure75_v1.py'),
        ('61ae733fbd269a040aa73f02cf1d86810216fba24b57dc9ab4d8aade896a4932', PACKAGE_SHA),
        ('native_class_v1.py', 'native_class_burst8_v1.py'),
        ('1a50703e0554575e323697a11d5bbf43778603f78b1c978406734d7678529516',
         '8c7234c341ad20823520761c429e030f26b8ed4e90cb4b171f3f91f328cfe767'),
        ('PROFILES={', "PROFILES={'cloud/azure-burst16-memory8-profiles-v1.json':'04fe25064f68301526492ebd232dba201fb15469e88c9f2cee0d3389215a9808','cloud/azure-burst16-static-profiles-v1.json':'eef2a816c7fc6ae5e53919b24b2bb135a16808d7ef7ccb7341395b0c030b596d',"),
        ("    else:name,key='cloud/azure-f32-static-profiles-v1.json',selected",
         "    elif selected.startswith('azure-burst16-static8g'):name,key='cloud/azure-burst16-memory8-profiles-v1.json',selected\n    elif selected.startswith('azure-burst16-static'):name,key='cloud/azure-burst16-static-profiles-v1.json',selected\n    else:name,key='cloud/azure-f32-static-profiles-v1.json',selected"),
    ]:
        if old not in text:
            raise ValueError('exact75 safe-stage anchor')
        text = text.replace(old, new)
    value = types.ModuleType('_qualified_azure75_stage')
    value.__file__ = str(Path(__file__).resolve())
    exec(compile(text, '[user75 unchanged burst4/8 staging]', 'exec'), value.__dict__)
    return value.worker()


def stage(archive, archive_sha, ticket_sha):
    return worker().stage(archive, archive_sha, ticket_sha)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('stage')
    command.add_argument('--archive', type=Path, required=True)
    command.add_argument('--archive-sha256', required=True)
    command.add_argument('--ticket-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.archive, args.archive_sha256, args.ticket_sha256), indent=2))
