"""Additive current-operator refresh of the unsubmitted app-v4 recoveries.

Uses the existing source-preserving repackage_variant API only. The logical
IDs, original failure ancestry, source/config/steps and dependencies stay exact.
"""
import argparse
import json
from pathlib import Path

from fpga.reference.stream27_context_storage_combo_registerederror_native import sha, need, dump
from fpga.reference import stream27_r15_application_v4_quota_recovery_packet_v1 as recovery

ROOT = Path(__file__).resolve().parents[1]
RUNNER = 'tools/native_class_package_v4.py'
RUNNER_PIN = '03ff2d89cb40d36a170ddb239500f611b76b069aa31cf1ae18ac65caf1c6c2c6'
STAGER = 'tools/native_package_v6.py'
STAGER_PIN = 'a2bdc7413484a8a8f4ab562870571b72cc644818ae29362bd5723a7f036bc82b'
REFRESH_PIN = 'c27a9912d6800eaed1d45edaaf69d5642ca1d5ae3967668cbe88c114ecd57007'
INPUT_PINS = {
    'aw8': '90220679ff0c19f025eb5695dd142a0e67c7196fbf66bbd3e665d012ed3a9390',
    'full': '68e62988ce960e53857cba38d4d0270da3eab813cfb93491b431cda1e383814e',
}


def prepare(stage):
    from fpga.tools import global_queue_v1 as queue
    from fpga.tools import native_azure_variant_refresh_v5 as refresh
    need(stage in INPUT_PINS, 'R15_APP_V4_LITERAL_OPERATOR_REFRESH')
    role = recovery.own.BASE / 'trackS-r15-shell-application-native-v4' / (stage + '-normal')
    old_path = role / 'quota-retry-packet-v1/global-ticket.json'
    raw = old_path.read_bytes()
    need(sha(raw) == INPUT_PINS[stage], 'R15_APP_V4_PRESERVED_UNSUBMITTED_INPUT')
    before = json.loads(raw)
    need(not any((ROOT / 'queue' / state / (before['id'] + '.json')).exists()
                 for state in ('pending', 'running', 'done')), 'R15_APP_V4_STILL_UNSUBMITTED')
    need(sha((ROOT / RUNNER).read_bytes()) == RUNNER_PIN and
         sha((ROOT / STAGER).read_bytes()) == STAGER_PIN and
         sha((ROOT / 'tools/native_azure_variant_refresh_v5.py').read_bytes()) == REFRESH_PIN,
         'R15_APP_V4_ACTUAL_FINAL_OPERATOR_PINS')
    out = role / 'operator-refresh-packet-v2'
    need(not out.exists(), 'R15_APP_V4_FRESH_ADDITIVE_OPERATOR_OUTPUT')
    out.mkdir()
    provider = queue.provider_capture_ref()
    packages = []
    for old in before['packages']:
        pair = old['profile'].split('static', 1)[1].split('-', 1)[0]
        worker = old['worker_id'] + '-op2'
        target = out / ('variant-' + pair)
        result = refresh.repackage_variant(Path(old['archive']).parent, old['profile'], worker,
                    Path(provider['path']), provider['sha256'], target)
        packet = target / 'packet'
        native = json.loads((packet / 'ticket.json').read_bytes())
        current = dict(old)
        current.update(archive=str(packet / 'package.tar.gz'), sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'], manifest_sha256=sha((packet / 'manifest.json').read_bytes()),
            worker_id=worker, native_root=native['native_root'], runner=RUNNER, runner_sha256=RUNNER_PIN,
            stager=str(ROOT / STAGER), stager_sha256=STAGER_PIN)
        packages.append(current)
    ticket = dict(before, packages=packages)
    need(queue.expected_identity(ticket) == queue.expected_identity(before) and
         sha(old_path.read_bytes()) == INPUT_PINS[stage], 'R15_APP_V4_SAME_LOGICAL_BODY_OLD_INPUT_UNTOUCHED')
    need(all(ticket.get(k) == before.get(k) for k in
             ('id', 'created', 'infra_retry_of', 'supersedes_unstarted', 'after', 'on', 'resources')),
         'R15_APP_V4_EXACT_RECOVERY_AND_DEPENDENCY_METADATA')
    queue.validate(ticket)
    queue.require_consumer_adoption(ticket)
    dump(out / 'global-ticket.json', ticket)
    dump(out / 'operator-refresh-receipt.json', dict(
        original_input_sha256=INPUT_PINS[stage], original_input_preserved=True,
        functional_identity=queue.expected_identity(ticket), runner_sha256=RUNNER_PIN,
        stager_sha256=STAGER_PIN, provider=provider, submitted=False))
    return dict(id=ticket['id'], ticket=str(out / 'global-ticket.json'), sha256=sha((out / 'global-ticket.json').read_bytes()),
                status='PREPARED_CURRENT_REGISTRY_VALIDATED_NOT_SUBMITTED')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--stage', choices=tuple(INPUT_PINS), required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.stage), indent=2))
