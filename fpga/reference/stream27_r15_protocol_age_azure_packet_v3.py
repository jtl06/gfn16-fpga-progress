"""Package the source author's Boolean-only AGE v3 through current Azure APIs.

The failed v1/v2 sources and captures stay immutable. This script does not
change RTL, calendars, validators, operator tools, or any accepted queue row.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from fpga.reference.stream27_context_storage_combo_registerederror_native import sha, need, dump

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/throughput-20260929/trackS-r15-protocol-age-native-v3'
PROFILES = ('azure-f16-static1213-v1', 'azure-f16-static1415-v1')
RUNNER = 'tools/native_class_package_v4.py'
RUNNER_PIN = '84c314a3b45665bb2a1552991be2b31b1b99adda5b1db3579595ea1bb78a34a5'
STAGER = 'tools/native_package_v6.py'
STAGER_PIN = 'f7d6bd0ce894a2e724ba6d8e6c455c4fb87891cd4b8d3f2f6ca20a99fc82e948'
ROLES = {
    'aw8': ('323012677ba353d267079091e79b06b6d41d3bd75eb3e7db309024a17993ccf3', 60),
    'full': ('a26573cc6e65ebe3b2af033e1e95879f9da4f9bb9eff5a9c43e44c809d721619', 61),
}


def prepare(stage):
    from fpga.tools import native_class_package_v4 as package, global_queue_v1 as queue
    from fpga.cloud import host_hours_azure_signed_v1 as meter
    need(stage in ROLES, 'R15_AGE_V3_LITERAL_AUTHOR_ROLE')
    pin, count = ROLES[stage]
    need(sha((ROOT / RUNNER).read_bytes()) == RUNNER_PIN and
         sha((ROOT / STAGER).read_bytes()) == STAGER_PIN and
         package.ACTIVE_PROFILES == PROFILES, 'R15_AGE_V3_CURRENT_AZURE_PINS')
    role = BASE / (stage + '-normal')
    manifest = role / 'manifest.json'
    m = json.loads(manifest.read_bytes())
    source = role / 'source/fpga'
    need(sha(manifest.read_bytes()) == pin and len(m['build']['sv_sources']) == count and
         m['build']['runtime_threads'] == 1 and m['build']['parameters']['EPOCH_AGE_REG'] == 1 and
         all(sha((source / n).read_bytes()) == h for n, h in m['sources'].items()),
         'R15_AGE_V3_SOURCE_AUTHOR_FROZEN_CLOSURE')
    id = 's4-p16-r15-protocol-age-' + stage + '-normal-q1-v3'
    need(not any((ROOT / 'queue' / state / (id + '.json')).exists()
                 for state in ('pending', 'running', 'done')), 'R15_AGE_V3_STILL_UNSUBMITTED')
    out = role / 'azure-packet-v1'
    need(not out.exists(), 'R15_AGE_V3_FRESH_ADDITIVE_PACKET')
    out.mkdir()
    provider = queue.provider_capture_ref()
    budget = out / 'budget.json'
    dump(budget, meter.make_budget('gfn16-azure-f16', 3715,
        str(Path(provider['path']).relative_to(ROOT)), provider['sha256'], package.source_identity(m),
        profile_sha256=package.F16_PROFILE_SHA))
    variants = []
    for profile in PROFILES:
        pair = profile.split('static', 1)[1].split('-', 1)[0]
        worker = id.removesuffix('-q1-v3') + '-' + pair + '-v3'
        packet = out / ('packet-' + pair)
        result = package.prepare(manifest, source, profile, worker, 'run', packet, budget)
        native = json.loads((packet / 'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet / 'package.tar.gz'), sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'], manifest_sha256=sha((packet / 'manifest.json').read_bytes()),
            worker_id=worker, profile=profile, native_root=native['native_root'],
            runner=RUNNER, runner_sha256=RUNNER_PIN, stager=str(ROOT / STAGER), stager_sha256=STAGER_PIN,
            stager_dependencies=[dict(path=str(ROOT / p), sha256=sha((ROOT / p).read_bytes())) for p in
                ('tools/native_package_v5.py', 'tools/native_package_v3.py', 'tools/native_package_v2.py')],
            max_seconds=3700))
    ticket = dict(schema='gfn16-global-ticket-v1', id=id, owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), priority='P0', kind='sim',
        needs='verilator', tool_identity='azure-f16-verilator5032-gcc13-python312-v1',
        allowed_hosts=['gfn16-azure-f16'], resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4),
        minimum_ram_gib=8, est_minutes=25, promotion_bound=False, test_role='normal',
        rtl_readiness=m['rtl_readiness'], packages=variants)
    if stage == 'full':
        ticket.update(after=['s4-p16-r15-protocol-age-aw8-normal-q1-v3'], on='PASS_expected_contracts')
    need(sha(manifest.read_bytes()) == pin and sha((ROOT / RUNNER).read_bytes()) == RUNNER_PIN and
         sha((ROOT / STAGER).read_bytes()) == STAGER_PIN, 'R15_AGE_V3_SOURCE_OPERATOR_STABLE')
    queue.validate(ticket)
    queue.require_consumer_adoption(ticket)
    dump(out / 'global-ticket.json', ticket)
    return dict(id=id, ticket=str(out / 'global-ticket.json'), status='PREPARED_NOT_SUBMITTED')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--stage', choices=tuple(ROLES), required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.stage), indent=2))
