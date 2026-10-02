"""Safe idempotent staging of class-policy static packets; no job dispatch.

Reuses the frozen, native-demonstrated stage implementation. Profile placement
is read solely from hash-pinned JSON; no candidate Python is imported at stage.
"""
import argparse
import hashlib
import json
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
PARENT_SHA='3f2186fa5aac8129ac1ad5a161de39cf221925ee95d5de6364a941b199e7279a'
CLASS_PACKAGE_SHA='61ae733fbd269a040aa73f02cf1d86810216fba24b57dc9ab4d8aade896a4932'
CLASS_EXECUTOR_SHA='1a50703e0554575e323697a11d5bbf43778603f78b1c978406734d7678529516'
PROFILES={
 'cloud/gcp-native-thread-profiles-v1.json':'c91d5c5519c9ef5c14aa1d1c014f2f4f0152170f77404cfd63dbabf4b5035fa5',
 'cloud/aethia-native-thread-profiles-v2.json':'837b27f292704ce8f46d03d37bed9b520aedc02da33a9b389b12588a71c5c916',
 'cloud/azure-f32-static-profiles-v1.json':'7919c768a8f39cbf98fdaf687ee562ef152a4de922b0abe7ce10de44972c88a2'}


def need(ok,why):
    if not ok:raise ValueError(why)


def profile_from_payload(payload,ticket,sources):
    for name,pin in [('tools/native_class_package_v1.py',CLASS_PACKAGE_SHA),('tools/native_class_v1.py',CLASS_EXECUTOR_SHA)]:
        need(sources.get(name)==pin,'known class worker/executor')
    selected=ticket['profile']
    mapping={
      'gcp-c4d-static01-v1':('cloud/gcp-native-thread-profiles-v1.json','gcp-c4d-sim01-v2'),
      'gcp-c4d-static23-v1':('cloud/gcp-native-thread-profiles-v1.json','gcp-c4d-sim23-v2'),
      'aethia-static02-v1':('cloud/aethia-native-thread-profiles-v2.json','aethia-sim02-v2'),
      'aethia-static46-v1':('cloud/aethia-native-thread-profiles-v2.json','aethia-sim46-v2'),
      'aethia-static810-v1':('cloud/aethia-native-thread-profiles-v2.json','aethia-sim810-v2')}
    if selected in mapping:name,key=mapping[selected]
    else:name,key='cloud/azure-f32-static-profiles-v1.json',selected
    need(sources.get(name)==PROFILES[name],'known immutable host placement JSON')
    data=json.loads(payload['capture/source/fpga/'+name])
    profiles=data.pop('profiles');need(key in profiles,'approved static profile')
    if isinstance(profiles[key],dict):data.update(profiles[key])
    else:data['cpus']=profiles[key]
    return data


def worker():
    raw=(HERE/'native_package_v2.py').read_bytes()
    need(hashlib.sha256(raw).hexdigest()==PARENT_SHA,'frozen safe stager identity')
    text=raw.decode()
    start=text.index('    # Only now inspect known trusted helper code.')
    end=text.index("    root=Path(profile['base'])",start)
    text=text[:start]+"    profile=profile_from_payload(payload,ticket,sources)\n"+text[end:]
    changes=[("sources.get('tools/'+relative(name))","sources.get(relative(name) if '/' in name else 'tools/'+relative(name))"),
      ("            claims=base/'claims';canonical_directory(claims);claims.mkdir(exist_ok=True)",
       "            claims=base/'claims';canonical_directory(claims);claims.mkdir(exist_ok=True)\n            scratch=Path(profile['scratch_base']);need(scratch.is_relative_to(base),'scratch within approved base');canonical_directory(scratch);scratch.mkdir(exist_ok=True)")]
    for old,new in changes:
        need(text.count(old)==1,'unique static stager source anchor');text=text.replace(old,new,1)
    module=types.ModuleType('_class_stage');module.__file__=str(Path(__file__).resolve())
    module.__dict__['profile_from_payload']=profile_from_payload
    exec(compile(text,str(HERE/'native_package_v2.py')+'[class-static]','exec'),module.__dict__)
    return module


def stage(archive,archive_sha,ticket_sha):return worker().stage(archive,archive_sha,ticket_sha)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    command=sub.add_parser('stage');command.add_argument('--archive',type=Path,required=True)
    command.add_argument('--archive-sha256',required=True);command.add_argument('--ticket-sha256',required=True)
    args=parser.parse_args();print(json.dumps(stage(args.archive,args.archive_sha256,args.ticket_sha256),indent=2))
