"""Closed F2 reference-data source/config archive; no executor or HDL runner.

An admitted dispatcher still supplies the actual finite Linux command,
fresh-source/runtime/resource/quota/budget checks, physical locks and terminal
collection. This file prepares data, never requests or grants a worker slot.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile

from fpga.reference import root_lookahead_field_host_v3 as host


ROOT = host.parent.ROOT
SELF = 'reference/root_lookahead_field_reference_prepare_v3.py'
DATA = 'reference/root_lookahead_field_data_v3.py'
DATA_SHA = 'aa3567a647adf0501f2bc33a98bb1f8b9ff39d7cc0e4d59ea7754c8252dc5e64'
HOST_SHA = '806849d97b5b3a28a7a80fe2ca789fe26f15f2346ba0df8189169e601dde13d3'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def prepare(output, identity, profile, field_index=0):
    host.parent.need(not (ROOT/'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    host.parent.need(type(identity) is str and re.fullmatch('[a-z0-9][a-z0-9-]{2,63}', identity), 'finite job identity')
    host.parent.need(type(field_index) is int and field_index in (0, 1, 2), 'field identity')
    host.configure(profile)
    selected = host.static.profile(profile)
    pins = {host.SELF: HOST_SHA, DATA: DATA_SHA,
            host.parent.SELF: host.PARENT_SHA,
            'reference/core27_prefetch_r2_structure.py': host.parent.PROFILE_SHA,
            'reference/merged_negacyclic27_model.py': host.parent.MATH_SHA,
            'tools/native_static_v1.py': host.STATIC_SHA,
            **host.static.PINS}
    pins['reference/__init__.py'] = sha(ROOT/'reference/__init__.py')
    pins[SELF] = sha(__file__)
    for name, pin in pins.items():
        path = ROOT/name
        host.parent.need(path.is_file() and not path.is_symlink() and sha(path) == pin,
                         'reference source pin: ' + name)
    output = Path(output)
    host.parent.need(output.is_absolute() and not output.exists() and output.parent.is_dir()
                     and output.parent.resolve() == output.parent, 'fresh canonical reference packet')
    source = output/'source/fpga'
    for name in sorted(pins):
        destination = source/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, destination)
        host.parent.need(sha(destination) == pins[name], 'copied reference source pin')
    remote = Path(selected['base'])/'reference-jobs'/identity
    config = dict(schema='F2-reference-data-config-v3', identity=identity, profile=profile,
        aw=16, field=field_index, numeric_reference_only=True, HDL_executed=False,
        source_root=str(remote/'source/fpga'), working_directory=str(remote/'source'),
        expected_output_root=str(remote/'output'),
        expected_files=['field-aw16-f'+str(field_index)+'-vectors.txt', 'field-aw16-f'+str(field_index)+'-vector-receipt-v3.json'],
        argv=['/usr/bin/python3.14', '-B', '-m', 'fpga.reference.root_lookahead_field_data_v3',
              '--aw', '16', '--field', str(field_index), '--profile', profile,
              '--output', str(remote/'output'/('field-aw16-f'+str(field_index)+'-vectors.txt')),
              '--receipt', str(remote/'output'/('field-aw16-f'+str(field_index)+'-vector-receipt-v3.json'))],
        runtime_sha256=selected['hashes']['python'], expected_hostname=selected['host'],
        expected_user=selected['user'], physical_cpus=selected['cpus'],
        containment=dict(cpu_quota_percent=200, memory_bytes=selected['memory_bytes'], swap_bytes=0,
                         runtime_seconds=1800, stop_seconds=15, kill_mode='control-group'),
        locks=[dict(path=selected['interop'], mode='SH'), dict(path=selected['pair_lock'], mode='EX')]
              + [dict(path=name, mode='EX') for name in selected['physical_locks']],
        scratch_reservation_bytes=selected['scratch_reservation_bytes'],
        scratch_floor_bytes=selected['scratch_floor_bytes'],
        static_profile_sha256=selected['profile_sha256'], sources=pins,
        admission='Not executed. Actual dispatcher source/runtime/quota/budget/lock admission and terminal proof required.',
        promotion_allowed=False)
    path = output/'reference-config.json'
    path.write_text(json.dumps(config, indent=2)+'\n')
    with tarfile.open(output/'source.tar.gz', 'x:gz') as archive:
        for name in sorted(pins):
            archive.add(source/name, arcname='source/fpga/'+name, recursive=False)
        archive.add(path, arcname='reference-config.json', recursive=False)
    result = dict(status='prepared_source_only_F2_AW16_reference_config', profile=profile,
        identity=identity, source_files=len(pins), reference_config_sha256=sha(path),
        archive_sha256=sha(output/'source.tar.gz'), archive_bytes=(output/'source.tar.gz').stat().st_size,
        copied_source_root=str(source), numeric_reference_executed=False,
        native_RTL_executed=False, launcher_clones_created=0, promotion_allowed=False)
    (output/'preparation.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--id', required=True)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--field', type=int, default=0)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.id, args.profile, args.field), indent=2))
