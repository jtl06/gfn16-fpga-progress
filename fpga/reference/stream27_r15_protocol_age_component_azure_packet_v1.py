"""Capture bounded AGE component roles on the existing admitted Azure lanes.

Source-author RTL/diagnostics/expectations are not rewritten. Each negative
depends on this component's own actual normal typed gate, not whole COMPUTE.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha, need, dump
from fpga.reference import stream27_r15_application_packet_v3 as operator

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/throughput-20260929/trackS-r15-protocol-age-component-v1'
NORMAL_ID = 's4-r15-protocol-age-component-normal-q1-v1'
ROLES = {
    'normal': ('normal-v1', '96ac156eb15f54145644eb599f8d03a002a070899ae77c89b25f7be03b6d0d20'),
    'fault': ('fault-v1', '0c72c132b29cf373bdd12db72f2f5a1f635c35cdddb7904d4844626d937a2917'),
    'bad-allocation': ('bad-allocation-v1', 'dd06411c7ab532b3b904a432c26800e032bfe3417368449e0ff72a21bf246f0f'),
    'bad-stop': ('bad-stop-v1', 'e66ce39fd43da09fb474d7a3b84156e2de368eaa62f0bee5b4e28cbe8418fb20'),
}


def prepare(stage):
    from fpga.tools import native_class_package_v4 as package
    from fpga.cloud import host_hours_azure_signed_v1 as meter
    need(stage in ROLES, 'R15_AGE_COMPONENT_LITERAL_ROLE')
    name, pin = ROLES[stage]
    id = 's4-r15-protocol-age-component-' + stage + '-q1-v1'
    need(sha((ROOT / operator.RUNNER).read_bytes()) == operator.RUNNER_PIN and
         sha((ROOT / operator.STAGER).read_bytes()) == operator.STAGER_PIN and
         package.ACTIVE_PROFILES == operator.PROFILES, 'R15_AGE_COMPONENT_CURRENT_AZURE_OPERATOR')
    role = BASE / name
    manifest = role / 'manifest.json'
    m = json.loads(manifest.read_bytes())
    source = role / 'source/fpga'
    need(sha(manifest.read_bytes()) == pin and len(m['build']['sv_sources']) == 3 and
         m['build']['runtime_threads'] == 1 and m['build']['parameters'] == {} and
         m['test_role'] == ('normal' if stage == 'normal' else 'deliberate_fault'),
         'R15_AGE_COMPONENT_FROZEN_AUTHOR_MANIFEST')
    need(all(sha((source / n).read_bytes()) == h for n, h in m['sources'].items()),
         'R15_AGE_COMPONENT_SOURCE_CLOSURE')
    need(m['scope']['production_candidate_unchanged'] and
         not m['scope']['runtime_age_or_clock_forcing'] and not m['scope']['full_COMPUTE'],
         'R15_AGE_COMPONENT_BOUNDED_SCOPE')
    need(sha((ROOT / operator.PROVIDER).read_bytes()) == operator.PROVIDER_PIN,
         'R15_AGE_COMPONENT_AUTHENTIC_PROVIDER')
    out = role / 'azure-packet-v1'
    need(not out.exists(), 'R15_AGE_COMPONENT_FRESH_PACKET')
    out.mkdir()
    budget = out / 'budget.json'
    dump(budget, meter.make_budget('gfn16-azure-f16', 3715, operator.PROVIDER,
         operator.PROVIDER_PIN, package.source_identity(m), profile_sha256=package.F16_PROFILE_SHA))
    variants = []
    for profile in operator.PROFILES:
        pair = profile.split('static', 1)[1].split('-', 1)[0]
        worker = id.removesuffix('-q1-v1') + '-' + pair + '-v1'
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
    need(sha(manifest.read_bytes()) == pin and
         sha((ROOT / operator.RUNNER).read_bytes()) == operator.RUNNER_PIN and
         sha((ROOT / operator.STAGER).read_bytes()) == operator.STAGER_PIN,
         'R15_AGE_COMPONENT_STABLE_AFTER_CAPTURE')
    ticket = dict(schema='gfn16-global-ticket-v1', id=id, owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), priority='P0', kind='sim',
        needs='verilator', tool_identity='azure-f16-verilator5032-gcc13-python312-v1',
        allowed_hosts=['gfn16-azure-f16'], resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4),
        minimum_ram_gib=8, est_minutes=10, promotion_bound=False,
        test_role=m['test_role'], rtl_readiness=m['rtl_readiness'], packages=variants)
    if stage != 'normal':
        ticket.update(after=[NORMAL_ID], on='PASS_expected_contracts')
    dump(out / 'global-ticket.json', ticket)
    return dict(id=id, ticket=str(out / 'global-ticket.json'), variants=2, status='PREPARED_NOT_SUBMITTED')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--stage', choices=tuple(ROLES), required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.stage), indent=2))
