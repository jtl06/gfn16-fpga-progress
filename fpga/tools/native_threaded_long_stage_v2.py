"""Safe stage for intrinsic-deadline measured threaded long packages only."""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='7386da14bf92f3af529e1926a4ba4b6c6bee97d13ebe115503d4b1c04cebb4c9'
PACKAGE_SHA='3da644327e3bdc7cdef0ae9804516b22942900a08b1e6a8faf19719011fcf04c'
EXECUTOR_SHA='8df98eae0fa2b82f868eadf2730cb1b47c11fdf02f07445b1c3b62983e1edfb4'


def worker():
    raw=(HERE/'native_threaded_long_stage_v1.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('frozen safe threaded long stager')
    text=raw.decode().replace('native_threaded_long_package_v1.py','native_threaded_long_package_v2.py').replace('ef0da878723fd06184a2cb57396f628ad4c0546612830c595d4e075e056960b3',PACKAGE_SHA)
    text=text.replace('native_threaded_long_class_v1.py','native_threaded_long_class_v2.py').replace('8eeeabd2456fd29e10a8534e007c98baf5832e94cec753f509a97df38ab7c0db',EXECUTOR_SHA)
    result=types.ModuleType('_intrinsic_threaded_long_stage');result.__file__=str(Path(__file__).resolve())
    exec(compile(text,'[intrinsic deadline safe stage]','exec'),result.__dict__)
    return result.worker()


def stage(archive,archive_sha,ticket_sha):return worker().stage(archive,archive_sha,ticket_sha)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    command=sub.add_parser('stage');command.add_argument('--archive',type=Path,required=True)
    command.add_argument('--archive-sha256',required=True);command.add_argument('--ticket-sha256',required=True)
    args=parser.parse_args();print(json.dumps(stage(args.archive,args.archive_sha256,args.ticket_sha256),indent=2))
