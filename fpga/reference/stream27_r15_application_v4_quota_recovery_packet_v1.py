"""One source-identical app-v4 recovery, preserving both original outcomes.

AW8 failed the initial quota guard before any native commands; full was never
claimed. Public submit still requires the queue owner's exact proof adoption.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from fpga.reference.stream27_context_storage_combo_registerederror_native import sha, need, dump
from fpga.reference import stream27_r15_application_packet_v3 as operator
from fpga.reference import stream27_r15_shell_application_v4_native as own

ROOT = Path(__file__).resolve().parents[1]
ROLES = {
    'aw8': ('s4-p16-c2-r15-shell-application-aw8-normal-q1-v5',
            '3248784f38814d8200a8a6bafe4ee9188b7ddd29f29193b95995c95918e6ef8d'),
    'full': ('s4-p16-c2-r15-shell-application-full-normal-q1-v7',
             '971e5835f8f45f4653091574fd7e2c606fa40f99e20116ac194d0884aa5bfdc8'),
}


def original(stage):
    path = ROOT / 'queue/done' / (own.ROLES[stage]['id'] + '.json')
    d = json.loads(path.read_bytes())
    r = d['result']
    if stage == 'aw8':
        e = Path(r['evidence'])
        need(r['status'] == 'terminal_failure' and r['properties']['InvocationID'] ==
             '20180630e35f4b5db7800a84add7e876' and r['archive_sha256'] ==
             'a61ab15ae8e754168de711a0b69e56145bd79d621ba2b1ecf9a3d50a952a99ed' and
             r['queue_report']['error'] == "QuotaError('global blocks below outstanding reservations plus floor')",
             'R15_APP_V4_ACTUAL_INITIAL_QUOTA_FAILURE')
        need(sha((e / 'runner.stderr').read_bytes()) ==
             '8fd7f10aa8391a9ced09201277fe61c46028d8c586834ba6efaacdda59383918' and
             sha((e / 'queue-report.json').read_bytes()) ==
             '33bb99497eb60f2ef916b92c93ef6b27181d2b3c8d930fdb00a6630445f0a382' and
             not (e / 'output').exists() and (e / 'runner.stdout').read_bytes() == b'',
             'R15_APP_V4_PRESERVED_NO_NATIVE_COMMANDS')
    else:
        need(r['status'] == 'cancelled_unstarted_dependency_failure' and not d.get('dispatch') and
             not d.get('selected_variant') and not d.get('logical_claim_sha256'),
             'R15_APP_V4_PROVEN_UNCLAIMED_FULL')
    return d


def prepare(stage):
    from fpga.tools import native_class_package_v4 as package
    from fpga.tools import global_queue_v1 as queue
    from fpga.cloud import host_hours_azure_signed_v1 as meter
    need(stage in ROLES, 'R15_APP_V4_LITERAL_RECOVERY_ROLE')
    before = original(stage)
    id, pin = ROLES[stage]
    need(sha((ROOT / operator.RUNNER).read_bytes()) == operator.RUNNER_PIN and
         sha((ROOT / operator.STAGER).read_bytes()) == operator.STAGER_PIN and
         package.ACTIVE_PROFILES == operator.PROFILES, 'R15_APP_V4_CURRENT_OPERATOR')
    role = own.BASE / 'trackS-r15-shell-application-native-v4' / (stage + '-normal')
    manifest = role / 'manifest.json'
    m = json.loads(manifest.read_bytes())
    source = role / 'source/fpga'
    need(sha(manifest.read_bytes()) == pin and len(m['build']['sv_sources']) == 71 and
         m['build']['runtime_threads'] == 1 and
         all(sha((source / n).read_bytes()) == h for n, h in m['sources'].items()),
         'R15_APP_V4_SAME_FROZEN_SOURCE_HARNESS_PARAMETERS')
    out = role / 'quota-retry-packet-v1'
    need(not out.exists(), 'R15_APP_V4_ONE_FRESH_RECOVERY_CAPTURE')
    out.mkdir()
    budget = out / 'budget.json'
    dump(budget, meter.make_budget('gfn16-azure-f16', 3715, operator.PROVIDER,
         operator.PROVIDER_PIN, package.source_identity(m), profile_sha256=package.F16_PROFILE_SHA))
    variants = []
    for profile in operator.PROFILES:
        pair = profile.split('static', 1)[1].split('-', 1)[0]
        worker = id.rsplit('-q1-', 1)[0] + '-' + pair + '-' + id.rsplit('-', 1)[-1]
        packet = out / ('packet-' + pair)
        result = package.prepare(manifest, source, profile, worker, 'run', packet, budget)
        native = json.loads((packet / 'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet / 'package.tar.gz'), sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'], manifest_sha256=sha((packet / 'manifest.json').read_bytes()),
            worker_id=worker, profile=profile, native_root=native['native_root'],
            runner=operator.RUNNER, runner_sha256=operator.RUNNER_PIN,
            stager=str(ROOT / operator.STAGER), stager_sha256=operator.STAGER_PIN,
            stager_dependencies=[dict(path=str(ROOT / p), sha256=sha((ROOT / p).read_bytes())) for p in
                ('tools/native_package_v5.py', 'tools/native_package_v3.py', 'tools/native_package_v2.py')],
            max_seconds=3700))
    ticket = dict(schema='gfn16-global-ticket-v1', id=id, owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), priority='P0', kind='sim',
        needs='verilator', tool_identity='azure-f16-verilator5032-gcc13-python312-v1',
        allowed_hosts=['gfn16-azure-f16'], resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4),
        minimum_ram_gib=8, est_minutes=25, promotion_bound=False, test_role='normal',
        rtl_readiness=m['rtl_readiness'], packages=variants)
    if stage == 'aw8':
        ticket['infra_retry_of'] = own.ROLES[stage]['id']
    else:
        ticket.update(supersedes_unstarted=own.ROLES[stage]['id'], after=[ROLES['aw8'][0]],
                      on='PASS_expected_contracts')
    need(queue.expected_identity(ticket) == queue.expected_identity(before),
         'R15_APP_V4_EXACT_ORIGINAL_FUNCTIONAL_IDENTITY')
    need(sha(manifest.read_bytes()) == pin and
         sha((ROOT / operator.RUNNER).read_bytes()) == operator.RUNNER_PIN and
         sha((ROOT / operator.STAGER).read_bytes()) == operator.STAGER_PIN,
         'R15_APP_V4_UNCHANGED_CAPTURE_AND_OPERATOR')
    dump(out / 'global-ticket.json', ticket)
    return dict(id=id, ticket=str(out / 'global-ticket.json'), status='PREPARED_HOLD_FOR_QUEUE_PROOF_ADOPTION')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--stage', choices=tuple(ROLES), required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.stage), indent=2))
