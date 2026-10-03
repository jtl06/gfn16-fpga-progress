"""Mechanical packet capture for frozen DIRECT65/GMP roles; no native run."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/throughput-20261003/r15-host-window-gmp-native-v1'
RUNNER = 'tools/native_class_package_v4.py'
STAGER = 'tools/native_package_v6.py'
PINS = {
    RUNNER: '03ff2d89cb40d36a170ddb239500f611b76b069aa31cf1ae18ac65caf1c6c2c6',
    STAGER: '4112106d59052af6cd432356287577f147ff5964e21768bf53960fd52bbf6eed',
}
ROLES = {
    'normal': ('s4-r15-host-window-gmp-aw8-normal-q1-v1',
               '57ab0f67d5287e977eab2340ff9ad6025841e3540e7e5340b79c1d769e274b33',
               'eec12f06ac2458eed1c5eb12e61787567f263b48abd064084222609c7466d1b4'),
    'faults': ('s4-r15-host-window-gmp-aw8-faults-q1-v1',
               'be6c1c9e1eb6d2ca46f4813fa9f5c7fa49341af952d2394854e55064981b54ee',
               '852b61ee704617568b0c60f8fcd01c609d52866b1e7e7f8a47e4b9da51bd03c6'),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def need(ok, message):
    if not ok:
        raise ValueError('R15_WINDOW_PACKET_' + message)


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def prepare(mode, *, recovery=False):
    from fpga.tools import global_queue_v1 as queue
    from fpga.tools import native_class_package_v4 as package
    need(mode in ROLES, 'MODE')
    for name, pin in PINS.items():
        need(sha(ROOT / name) == pin, 'FINAL_OPERATOR_PIN')
    original_id, manifest_pin, identity = ROLES[mode]
    logical_id = original_id.removesuffix('-v1') + '-v2' if recovery else original_id
    role = BASE / mode
    manifest_path = role / 'manifest.json'
    need(sha(manifest_path) == manifest_pin, 'FROZEN_ROLE')
    manifest = json.loads(manifest_path.read_bytes())
    source = Path(manifest['source_root'])
    need(source == role / 'source/fpga' and package.source_identity(manifest) == identity,
         'EXACT_SOURCE_IDENTITY')
    need(all(sha(source / name) == pin for name, pin in manifest['sources'].items()),
         'ALL_FROZEN_SOURCE_BYTES')
    out = role / ('azure-packets-v2' if recovery else 'azure-packets-v1')
    need(not out.exists(), 'FRESH_OUTPUT')
    out.mkdir()
    provider = queue.provider_capture_ref()
    budget = package.meter().make_budget('gfn16-azure-f16', 3715,
        str(Path(provider['path']).relative_to(ROOT)), provider['sha256'],
        identity, package.F16_PROFILE_SHA)
    dump(out / 'budget.json', budget)
    variants = []
    for pair in ('1213', '1415'):
        profile = 'azure-f16-static' + pair + '-v1'
        worker = logical_id.replace('-q1-', '-' + pair + '-')
        packet = out / ('packet-' + pair)
        result = package.prepare(manifest_path, source, profile, worker, 'run', packet,
                                 out / 'budget.json')
        native = json.loads((packet / 'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet / 'package.tar.gz'),
            sha256=result['archive_sha256'], ticket_sha256=result['ticket_sha256'],
            manifest_sha256=sha(packet / 'manifest.json'), worker_id=worker,
            profile=profile, native_root=native['native_root'], runner=RUNNER,
            runner_sha256=PINS[RUNNER], stager=str(ROOT / STAGER),
            stager_sha256=PINS[STAGER], stager_dependencies=[
                dict(path=str(ROOT / name), sha256=sha(ROOT / name)) for name in
                ('tools/native_package_v5.py', 'tools/native_package_v3.py',
                 'tools/native_package_v2.py')], max_seconds=3700))
    predecessor = ('s4-p16-c2-r15-direct-compute-aw8-normal-q1-v2' if mode == 'normal'
                   else ROLES['normal'][0].removesuffix('-v1') + ('-v2' if recovery else '-v1'))
    ticket = dict(schema='gfn16-global-ticket-v1', id=logical_id,
        owner='independent-review', created=datetime.now(timezone.utc).isoformat(),
        priority='P0' if mode == 'normal' else 'P2', kind='sim', needs='verilator',
        tool_identity='azure-f16-verilator5032-gcc13-python312-v1',
        allowed_hosts=['gfn16-azure-f16'],
        resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4),
        minimum_ram_gib=8, est_minutes=10, promotion_bound=False,
        test_role='normal' if mode == 'normal' else 'deliberate_fault',
        rtl_readiness=manifest['rtl_readiness'],
        after=[predecessor], on='PASS_expected_contracts', packages=variants)
    if recovery:
        preserved = json.loads((ROOT/'queue/done'/(original_id+'.json')).read_bytes())
        wanted = ('terminal_prelaunch_failure_preserved' if mode == 'normal'
                  else 'cancelled_unstarted_dependency_failure')
        need(preserved['result']['status'] == wanted, 'EXACT_PRESERVED_FAILURE_CLASS')
        ticket['infra_retry_of' if mode == 'normal' else 'supersedes_unstarted'] = original_id
    dump(out / 'global-ticket.json', ticket)
    for name, pin in PINS.items():
        need(sha(ROOT / name) == pin, 'OPERATOR_STABLE_AFTER_CAPTURE')
    if not recovery:
        queue.validate(ticket)
    return dict(id=logical_id, ticket=str(out / 'global-ticket.json'),
                status='PREPARED_NOT_SUBMITTED' if recovery else 'PREPARED_VALIDATED_NOT_SUBMITTED', variants=2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=tuple(ROLES), required=True)
    parser.add_argument('--recovery', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare(args.mode,recovery=args.recovery), indent=2))
