"""Safe data-only staging for exact10800s GCP long packages; no execution."""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
PARENT_SHA = '5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9'
PACKAGE_SHA = '84f806d3b6a5a09acd652849418e65f55f05e443ee325980b30085c1f9cdc64f'
EXECUTOR_SHA = 'ed9c3bbc8796862effc9409beff9a440cb2d13cd4b4cb55f822925ab5ecf1c4f'
SHAPE = {'id': 'continuous-model-10800-v1', 'model_command_seconds': 10450,
         'ancillary_command_seconds': 1800, 'overall_seconds': 10700,
         'outer_seconds': 10800, 'stop_grace_seconds': 15, 'lock_wait_seconds': 1800,
         'model_threads': 1}


def worker():
    raw = (HERE / 'native_package_v3.py').read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA: raise ValueError('frozen safe static stager')
    text = raw.decode()
    changes = [('native_class_package_v1.py', 'native_long_package_v1.py'),
               ('61ae733fbd269a040aa73f02cf1d86810216fba24b57dc9ab4d8aade896a4932', PACKAGE_SHA),
               ('native_class_v1.py', 'native_long_class_v1.py'),
               ('1a50703e0554575e323697a11d5bbf43778603f78b1c978406734d7678529516', EXECUTOR_SHA),
               ('PROFILES={', "PROFILES={'cloud/gcp-native-24g-profiles-v1.json':'1d657a2bd188dee76926ba1497cec7f46089dde2d0542e1a27f77f3f143ef140',"),
               ('    mapping={', "    need(selected.startswith('gcp-c4d-'),'long GCP placement only')\n    mapping={\n      'gcp-c4d-static24g01-v1':('cloud/gcp-native-24g-profiles-v1.json','gcp-c4d-static24g01-v1'),\n      'gcp-c4d-static24g23-v1':('cloud/gcp-native-24g-profiles-v1.json','gcp-c4d-static24g23-v1'),"),
               ("    module=types.ModuleType('_class_stage')", "    text=text.replace(\"ticket['max_seconds']==3700\",\"ticket['max_seconds']==10800 and ticket['runtime_duration']==\"+repr(LONG_SHAPE)+\" and manifest['runtime_duration']['shape']==\"+repr(LONG_SHAPE))\n    module=types.ModuleType('_class_stage')")]
    for old, new in changes:
        if old not in text: raise ValueError('finite stage source anchor')
        text = text.replace(old, new)
    result = types.ModuleType('_long_stage'); result.__file__ = str(Path(__file__).resolve())
    result.LONG_SHAPE = SHAPE
    exec(compile(text, '[finite10800 stage]', 'exec'), result.__dict__)
    return result.worker()


def stage(archive, archive_sha, ticket_sha): return worker().stage(archive, archive_sha, ticket_sha)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    command = sub.add_parser('stage'); command.add_argument('--archive', type=Path, required=True)
    command.add_argument('--archive-sha256', required=True); command.add_argument('--ticket-sha256', required=True)
    args = parser.parse_args(); print(json.dumps(stage(args.archive, args.archive_sha256, args.ticket_sha256), indent=2))
