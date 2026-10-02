"""Safe immutable staging for the same-pair 24GiB GCP envelope."""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9'


def worker():
    raw=(HERE/'native_package_v3.py').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA: raise ValueError('frozen safe stager')
    text=raw.decode()
    changes=[('native_class_package_v1.py','native_class_package_gcp24_v1.py'),
      ('61ae733fbd269a040aa73f02cf1d86810216fba24b57dc9ab4d8aade896a4932','39a85fbde4a87b773fc51fb0fad65f7a21e7549c91bd6d13f7dd33b404ef1d32'),
      ('native_class_v1.py','native_class_gcp24_v1.py'),
      ('1a50703e0554575e323697a11d5bbf43778603f78b1c978406734d7678529516','13697e0cf18f4fddfc896b35d32e6fa26123639b304e5ae42ff99a03890a8fff'),
      ('PROFILES={',"PROFILES={'cloud/gcp-native-24g-profiles-v1.json':'1d657a2bd188dee76926ba1497cec7f46089dde2d0542e1a27f77f3f143ef140',"),
      ('    mapping={',"    mapping={\n      'gcp-c4d-static24g01-v1':('cloud/gcp-native-24g-profiles-v1.json','gcp-c4d-static24g01-v1'),\n      'gcp-c4d-static24g23-v1':('cloud/gcp-native-24g-profiles-v1.json','gcp-c4d-static24g23-v1'),")]
    for old,new in changes:
        if old not in text: raise ValueError('24GiB stager source anchor')
        text=text.replace(old,new)
    result=types.ModuleType('_gcp24_stage');result.__file__=str(Path(__file__).resolve())
    exec(compile(text,str(HERE/'native_package_v3.py')+'[24GiB]','exec'),result.__dict__)
    return result.worker()


def stage(archive,archive_sha,ticket_sha): return worker().stage(archive,archive_sha,ticket_sha)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    command=sub.add_parser('stage');command.add_argument('--archive',type=Path,required=True)
    command.add_argument('--archive-sha256',required=True);command.add_argument('--ticket-sha256',required=True)
    args=parser.parse_args();print(json.dumps(stage(args.archive,args.archive_sha256,args.ticket_sha256),indent=2))
