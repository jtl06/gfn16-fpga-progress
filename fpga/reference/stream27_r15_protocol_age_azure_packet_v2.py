"""Package source-owner's additive AGE width repair; old failures untouched."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from fpga.reference.stream27_context_storage_combo_registerederror_native import sha, need, dump
from fpga.reference import stream27_r15_application_v4_operator_refresh_packet_v2 as operator

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/throughput-20260929/trackS-r15-protocol-age-native-v2'
PROFILES = ('azure-f16-static1213-v1', 'azure-f16-static1415-v1')
ROLES = {
    'aw8': ('88027f41a7a98c626c76e0ea10f9d6a58544f5e983b34528436120c911e706cd', 60),
    'full': ('ca75d4c8fd132b879f0313ff118f2d65da15d9271205661a5d84868517b5123b', 61),
}


def prepare(stage):
    from fpga.tools import native_class_package_v4 as package
    from fpga.tools import global_queue_v1 as queue
    from fpga.cloud import host_hours_azure_signed_v1 as meter
    need(stage in ROLES, 'R15_AGE_V2_LITERAL_AUTHOR_ROLE')
    pin, count = ROLES[stage]
    need(sha((ROOT / operator.RUNNER).read_bytes()) == operator.RUNNER_PIN and
         sha((ROOT / operator.STAGER).read_bytes()) == operator.STAGER_PIN and
         package.ACTIVE_PROFILES == PROFILES, 'R15_AGE_V2_CURRENT_AZURE_PINS')
    role = BASE / (stage + '-normal')
    manifest = role / 'manifest.json'
    m = json.loads(manifest.read_bytes())
    source = role / 'source/fpga'
    need(sha(manifest.read_bytes()) == pin and len(m['build']['sv_sources']) == count and
         m['build']['runtime_threads'] == 1 and m['build']['parameters']['EPOCH_AGE_REG'] == 1 and
         all(sha((source / n).read_bytes()) == h for n, h in m['sources'].items()),
         'R15_AGE_V2_SOURCE_AUTHOR_FROZEN_CLOSURE')
    out = role / 'azure-packet-v1'
    need(not out.exists(), 'R15_AGE_V2_FRESH_ADDITIVE_PACKET')
    out.mkdir()
    provider = queue.provider_capture_ref()
    budget = out / 'budget.json'
    dump(budget, meter.make_budget('gfn16-azure-f16', 3715,
        str(Path(provider['path']).relative_to(ROOT)), provider['sha256'], package.source_identity(m),
        profile_sha256=package.F16_PROFILE_SHA))
    id = 's4-p16-r15-protocol-age-' + stage + '-normal-q1-v2'
    variants = []
    for profile in PROFILES:
        pair = profile.split('static', 1)[1].split('-', 1)[0]
        worker = id.removesuffix('-q1-v2') + '-' + pair + '-v2'
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
    if stage == 'full':
        ticket.update(after=['s4-p16-r15-protocol-age-aw8-normal-q1-v2'], on='PASS_expected_contracts')
    need(sha(manifest.read_bytes()) == pin and
         sha((ROOT / operator.RUNNER).read_bytes()) == operator.RUNNER_PIN and
         sha((ROOT / operator.STAGER).read_bytes()) == operator.STAGER_PIN,
         'R15_AGE_V2_CURRENT_OPERATOR_AND_SOURCE_STABLE')
    queue.validate(ticket)
    queue.require_consumer_adoption(ticket)
    dump(out / 'global-ticket.json', ticket)
    return dict(id=id, ticket=str(out / 'global-ticket.json'), status='PREPARED_NOT_SUBMITTED')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--stage', choices=tuple(ROLES), required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.stage), indent=2))
