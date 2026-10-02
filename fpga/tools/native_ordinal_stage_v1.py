"""Safe data-only staging of the exact source-pinned ordinal3300 family."""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
PARENT_SHA = '5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9'
PACKAGE_SHA = '2fc6d2dfab63f7b366826b51c59efa74c7c39f0ed77615da75dbeb4cff719245'
EXECUTOR_SHA = '744f041a01b7104762f3220a2a7e60141b19ebd4c472c24301d7c45b7d11a8f0'
SHAPE = dict(id='ordinal-single-model3300-v1', model_command_seconds=3300,
             ancillary_command_seconds=1800, overall_seconds=3600,
             outer_seconds=3700, stop_grace_seconds=15, lock_wait_seconds=1800,
             model_threads=1)


def worker():
    raw = (HERE / 'native_package_v3.py').read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError('frozen safe ordinal stager')
    text = raw.decode()
    changes = [
        ('native_class_package_v1.py', 'native_ordinal_package_v1.py'),
        ('61ae733fbd269a040aa73f02cf1d86810216fba24b57dc9ab4d8aade896a4932', PACKAGE_SHA),
        ('native_class_v1.py', 'native_ordinal_class_v1.py'),
        ('1a50703e0554575e323697a11d5bbf43778603f78b1c978406734d7678529516', EXECUTOR_SHA),
        ('    mapping={', "    need(selected in ('gcp-c4d-static01-v1','gcp-c4d-static23-v1'),'ordinal GCP8GiB placement only')\n    mapping={"),
        ("    module=types.ModuleType('_class_stage')",
         "    text=text.replace(\"ticket['max_seconds']==3700\",\"ticket['max_seconds']==3700 and ticket['runtime_duration']==\"+repr(ORDINAL_SHAPE)+\" and manifest['runtime_duration']['shape']==\"+repr(ORDINAL_SHAPE))\n    module=types.ModuleType('_class_stage')"),
    ]
    for old, new in changes:
        if old not in text:
            raise ValueError('exact ordinal stage anchor')
        text = text.replace(old, new)
    module = types.ModuleType('_ordinal_stage')
    module.__file__ = str(Path(__file__).resolve())
    module.ORDINAL_SHAPE = SHAPE
    exec(compile(text, '[safe single ordinal3300 staging]', 'exec'), module.__dict__)
    return module.worker()


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
