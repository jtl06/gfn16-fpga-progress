"""Thin R3 own-pilot binding to the existing finite serial long package."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))


def prepare(output):
    from fpga.reference import stream27_context_storage_combo_quarantine_continuous as role
    from fpga.tools import candidate_ladder, global_queue_v1 as queue, native_long_package_v3 as package
    out = Path(output).resolve()
    role.need(out.is_relative_to(role.BASE) and not out.exists(), 'FRESH_LONG_PACKET')
    role.need(not any((ROOT / n).exists() for n in ('docs/briefs/PAUSE', 'queue/PAUSE')), 'PAUSE')
    original = role.BASE / 'continuous1000-measured-v1'
    manifest = json.loads((original / 'manifest.json').read_text())
    role.need(manifest['sources'][role.SELF] == role.sha((ROOT / role.SELF).read_bytes()), 'FROZEN_OWN_HELPER')
    evidence = dict(forecast=original / 'forecast.json', pilot_manifest=role.PILOT_MANIFEST,
                    pilot_report=role.PILOT_REPORT, pilot_gate=role.PILOT_GATE)
    out.mkdir(parents=True)
    bound = package.bind_role(original / 'manifest.json', original / 'source/fpga', evidence,
                              out / 'bound', host='gfn16-pilot-c4d')
    bound_manifest, bound_source = Path(bound['manifest']), Path(bound['source_root'])
    role.dump(out / 'host-hours.json', candidate_ladder.budget_from_hourly())
    variants = []
    dependencies = ('tools/native_long_stage_v1.py', 'tools/native_package_v3.py', 'tools/native_package_v2.py')
    for pair in ('01', '23'):
        profile = 'gcp-c4d-static' + pair + '-v1'
        worker = 's4-p16-c2-combo-r3-continuous1000-' + pair + '-v1'
        packet = out / ('packet-' + pair)
        package.prepare(bound_manifest, bound_source, profile, worker, 'run', packet,
                        out / 'host-hours.json', compile_workers=2)
        native = json.loads((packet / 'ticket.json').read_text())
        packed = json.loads((packet / 'manifest.json').read_text())
        variants.append(dict(archive=str(packet / 'package.tar.gz'), sha256=queue.sha(packet / 'package.tar.gz'),
            ticket_sha256=queue.sha(packet / 'ticket.json'), manifest_sha256=queue.sha(packet / 'manifest.json'),
            worker_id=worker, profile=profile, native_root=native['native_root'],
            runner='tools/native_long_package_v3.py', runner_sha256=packed['sources']['tools/native_long_package_v3.py'],
            stager=str(ROOT / 'tools/native_long_stage_v3.py'), stager_sha256=queue.sha(ROOT / 'tools/native_long_stage_v3.py'),
            stager_dependencies=[dict(path=str(ROOT / name), sha256=queue.sha(ROOT / name)) for name in dependencies],
            max_seconds=10800))
    logical = dict(schema='gfn16-global-ticket-v1', id='s4-p16-c2-combo-r3-continuous1000-q1-v1',
        owner='p16-mlab', created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), priority='P1',
        kind='sim', needs='verilator', tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4), minimum_ram_gib=8,
        minimum_ram_rationale='Own R3 serial100 source/allocation/forecast; same production/CPP, COUNT/BITS header delta only.',
        est_minutes=100, promotion_bound=False, test_role='normal', rtl_readiness=manifest['rtl_readiness'],
        after=[role.PILOT_ID], on='PASS_expected_contracts', packages=variants)
    role.dump(out / 'global-ticket.json', logical)
    role.dump(out / 'preparation.json', dict(status='PREPARED_NOT_NATIVE', id=logical['id'], admission=bound['admission']))
    return dict(id=logical['id'], ticket=str(out / 'global-ticket.json'), status='PREPARED_NOT_SUBMITTED')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
