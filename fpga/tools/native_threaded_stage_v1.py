"""Hash-checked safe staging for the observed resized Azure class package."""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
PARENT_SHA = '9b2dc9048500d0e31d14b4ba7b64b4906b944486478cac8cc83c814d8d205e75'
PACKAGE_SHA = 'a46870188ce7b637681f799bde2a0c1aa9b6b981774b00aeae77199ad919d351'
EXECUTOR_SHA = '4633c3ca20a6560fdeed35590922a01de8cd572b1bf127e3d2faa4a96734751f'
PROFILE_SHA = 'eef2a816c7fc6ae5e53919b24b2bb135a16808d7ef7ccb7341395b0c030b596d'


def worker():
    raw = (HERE / 'native_package_v5.py').read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError('frozen observed-host stager')
    text = raw.decode()
    changes = [('native_class_package_v3.py', 'native_threaded_package_v1.py'),
               ('a8c42095d5d174b6bc622eb10774a0a581e6060b8366d981afabc39084ddcfdd', PACKAGE_SHA),
               ('native_class_v2.py', 'native_threaded_class_v1.py'),
               ('5a3ab8b8306e74de9d6dd9fcbe26ee185a25dff95ac6a5e1b51503ce00e543c3', EXECUTOR_SHA),
               ("PROFILES={'cloud/azure-native", "PROFILES={'cloud/azure-burst16-static-profiles-v1.json':'" + PROFILE_SHA + "','cloud/azure-native"),
               ("    elif selected.startswith('azure-f16-static')", "    elif selected.startswith('azure-burst16-static'):name,key='cloud/azure-burst16-static-profiles-v1.json',selected\\n    elif selected.startswith('azure-f16-static')")]
    for old, new in changes:
        if old not in text:
            raise ValueError('resized stager source anchor')
        text = text.replace(old, new)
    module = types.ModuleType('_resized_azure_stage')
    module.__file__ = str(Path(__file__).resolve())
    exec(compile(text, str(HERE / 'native_package_v5.py') + '[r49-observed]', 'exec'), module.__dict__)
    return module.worker()


def stage(archive, archive_sha, ticket_sha):
    return worker().stage(archive, archive_sha, ticket_sha)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    command = sub.add_parser('stage')
    command.add_argument('--archive', type=Path, required=True)
    command.add_argument('--archive-sha256', required=True)
    command.add_argument('--ticket-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.archive, args.archive_sha256, args.ticket_sha256), indent=2))
