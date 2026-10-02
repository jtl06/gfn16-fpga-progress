"""Safe long staging with strict package and namespace-correct runtime pins."""
import argparse
import hashlib
import json
import tarfile
from pathlib import Path
import types

HERE = Path(__file__).resolve().parent
PARENT_SHA = 'cce5edc8ae265da2f2ffc6c00097bd9d5811ef2aef5699fbafe0b0f2f92b46c3'
PACKAGE_SHA = 'c4fc46b3ce4515d9c763e0828a2ec60d41522378baa6d0ba17581cfb116b3cd5'
EXECUTOR_SHA = '0c0cfe425bf4b6b67ea35954b3d5fef7f43059ee7718ce25f4cd862728aa0ea5'
WIDE_STAGE_SHA='de680fbef0b60f34c98b6278e7a0235fb169dc3272b20ecccc86ba10758c0cc3'
ENVELOPE = 'cloud/azure-burst16-memory8-profiles-v1.json'
ENVELOPE_SHA = '04fe25064f68301526492ebd232dba201fb15469e88c9f2cee0d3389215a9808'


def worker(count=None):
    if count is not None and (type(count) is not int or count not in (1,4,8)):
        raise ValueError('exact serial/four/eight measured long shape')
    raw = (HERE / 'native_long_stage_v1.py').read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA: raise ValueError('frozen safe long stager')
    text = raw.decode()
    for old, new in [('native_long_package_v1.py', 'native_long_package_v3.py'),
                     ('84f806d3b6a5a09acd652849418e65f55f05e443ee325980b30085c1f9cdc64f', PACKAGE_SHA),
                     ('native_long_class_v1.py', 'native_long_class_v2.py'),
                     ('ed9c3bbc8796862effc9409beff9a440cb2d13cd4b4cb55f822925ab5ecf1c4f', EXECUTOR_SHA)]:
        if old not in text: raise ValueError('exact namespace stage anchor')
        text = text.replace(old, new)
    result = types.ModuleType('_long_namespace_stage'); result.__file__ = str(Path(__file__).resolve())
    exec(compile(text, '[strict namespace long staging]', 'exec'), result.__dict__)
    if count in (4,8):result.SHAPE=dict(result.SHAPE,id=f'continuous-model-10800-thread{count}-v1',model_threads=count)
    value = result.worker()
    original = value.profile_from_payload
    def placement(payload, ticket, sources):
        if ticket['profile'] in ('azure-burst16-thread-wide07-v1','azure-burst16-thread-wide815-v1'):
            path=HERE/'native_threaded_wide_stage_v3.py';raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=WIDE_STAGE_SHA:raise ValueError('known safe physical-wide data stage')
            text=raw.decode().replace('tools/native_threaded_wide_package_v3.py','tools/native_long_package_v3.py')
            text=text.replace('tools/native_threaded_wide_v3.py','tools/native_long_class_v2.py')
            text=text.replace('8d8585935a42241b85813a8db6204b02ce5aa2a23559e91a4911489a8de410e6',PACKAGE_SHA)
            text=text.replace('71924875229a549fbcfb8cd52252406a8610d40946597e1d8b2470ae843466d7',EXECUTOR_SHA)
            changes=[('    allocation=dict(cpus=cpus,physical_cores=physical,cpu_quota_percent=800,compile_workers=2,memory_bytes=8<<30)',
                "    manifest=json.loads(payload['manifest.json']);workers=manifest['fixed_execution']['runtime_allocation']['compile_workers']\n"
                "    need(type(workers) is int and 1<=workers<=len(physical),'compiler workers fit owned physical cores')\n"
                "    allocation=dict(cpus=cpus,physical_cores=physical,cpu_quota_percent=800,compile_workers=workers,memory_bytes=8<<30)"),
                ('hardware.update(template,cpus=cpus,observed_l3=l3[0])',
                 'hardware.update(template,cpus=cpus,observed_l3=l3[0],compile_workers=workers)')]
            for old,new in changes:
                if text.count(old)!=1:raise ValueError('actual compile allocation data-stage anchor')
                text=text.replace(old,new,1)
            stage=types.ModuleType('_same_captured_physical_wide_data');stage.__file__=str(path)
            exec(compile(text,'[known data-only physical allocation for long envelope]','exec'),stage.__dict__)
            return stage.profile_from_payload(payload,ticket,sources)
        if not ticket['profile'].startswith('azure-burst16-static8g'):
            return original(payload, ticket, sources)
        if (sources.get('tools/native_long_package_v3.py') != PACKAGE_SHA
            or sources.get('tools/native_long_class_v2.py') != EXECUTOR_SHA
            or sources.get(ENVELOPE) != ENVELOPE_SHA):
            raise ValueError('exact serial Azure8 long source controls/envelope')
        raw = payload['capture/source/fpga/' + ENVELOPE]
        if hashlib.sha256(raw).hexdigest() != ENVELOPE_SHA:
            raise ValueError('data-only placement content hash')
        data = json.loads(raw); profiles = data.pop('profiles')
        if ticket['profile'] not in profiles:
            raise ValueError('existing admitted Azure8 pair')
        data.update(profiles[ticket['profile']])
        if (data['host'] != 'gfn16-azure-sim-f32' or len(data['cpus']) != 2
            or data['memory_bytes'] != 8589934592 or data['cpu_quota_percent'] != 200
            or data['model_threads'] != 1 or data['compile_workers'] != 2):
            raise ValueError('unchanged two-physical serial8 allocation')
        return data
    value.profile_from_payload = placement
    if count is None:
        def inspect(path,archive_sha,ticket_sha):
            # Read only verified bounded archive data to select a fixed shape;
            # no role/runtime Python is imported by the staging tool.
            value.regular(path);value.pin(archive_sha);value.pin(ticket_sha)
            value.need(Path(path).stat().st_size<=value.MAX_ARCHIVE and value.sha(path)==archive_sha,'bounded exact shape archive')
            with tarfile.open(path,'r:gz') as archive:payload=value.members(archive)
            value.need(value.digest(payload['ticket.json'])==ticket_sha,'exact shape ticket')
            native=json.loads(payload['ticket.json']);selected=native['runtime_duration']['model_threads']
            return worker(selected).inspect_archive(path,archive_sha,ticket_sha)
        value.inspect_archive=inspect
    return value


def stage(archive, archive_sha, ticket_sha): return worker().stage(archive, archive_sha, ticket_sha)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    command = sub.add_parser('stage'); command.add_argument('--archive', type=Path, required=True)
    command.add_argument('--archive-sha256', required=True); command.add_argument('--ticket-sha256', required=True)
    args = parser.parse_args(); print(json.dumps(stage(args.archive, args.archive_sha256, args.ticket_sha256), indent=2))
