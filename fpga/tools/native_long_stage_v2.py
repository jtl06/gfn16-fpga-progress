"""Unchanged safe long staging, bound to the strict accounting successor."""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
PARENT_SHA = 'cce5edc8ae265da2f2ffc6c00097bd9d5811ef2aef5699fbafe0b0f2f92b46c3'
PACKAGE_SHA = '1e68060c89b8a013b42e87bb11ced3443b42dc74872e6f2dcbc3b3e39ecc7d06'


def worker():
    raw = (HERE / 'native_long_stage_v1.py').read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError('frozen safe long stager')
    text = raw.decode().replace('native_long_package_v1.py', 'native_long_package_v2.py')
    text = text.replace('84f806d3b6a5a09acd652849418e65f55f05e443ee325980b30085c1f9cdc64f', PACKAGE_SHA)
    result = types.ModuleType('_strict_long_stage'); result.__file__ = str(Path(__file__).resolve())
    exec(compile(text, '[strict long package staging]', 'exec'), result.__dict__)
    return result.worker()


def stage(archive, archive_sha, ticket_sha): return worker().stage(archive, archive_sha, ticket_sha)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    command = sub.add_parser('stage'); command.add_argument('--archive', type=Path, required=True)
    command.add_argument('--archive-sha256', required=True); command.add_argument('--ticket-sha256', required=True)
    args = parser.parse_args(); print(json.dumps(stage(args.archive, args.archive_sha256, args.ticket_sha256), indent=2))
