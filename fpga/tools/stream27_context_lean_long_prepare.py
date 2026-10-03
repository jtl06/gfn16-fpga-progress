"""Thin own lean-R7 binding to the existing measured finite serial package."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepare(output):
    from fpga.reference import stream27_context_lean_continuous as role
    from fpga.tools import candidate_ladder, global_queue_v1 as queue, native_long_package_v3 as package
    out = Path(output).resolve()
    original = ROOT/'results/throughput-20260929/trackS-c2-lean-r7-ownlong-v1/continuous1000-source-v2'
    role.need(out.is_relative_to(original.parent) and not out.exists(), 'FRESH_LONG_PACKET')
    role.need(not any((ROOT/name).exists() for name in ('queue/PAUSE', 'docs/briefs/PAUSE')), 'PAUSE')
    manifest = json.loads((original/'manifest.json').read_bytes())
    role.need(manifest['sources'][role.SELF] == role.sha((ROOT/role.SELF).read_bytes()), 'FROZEN_OWN_HELPER')
    evidence = dict(forecast=original/'forecast.json', pilot_manifest=role.RAW/'approved-manifest.json',
                    pilot_report=role.RAW/'report.json', pilot_gate=role.PILOT_GATE)
    out.mkdir(parents=True)
    bound = package.bind_role(original/'manifest.json', original/'source/fpga', evidence,
                              out/'bound', host='gfn16-pilot-c4d')
    role.dump(out/'host-hours.json', candidate_ladder.budget_from_hourly())
    variants = []
    for pair in ('01', '23'):
        profile = 'gcp-c4d-static'+pair+'-v1'
        worker = 's4-p16-c2-lean-r7-continuous1000-'+pair+'-v1'
        packet = out/('packet-'+pair)
        package.prepare(Path(bound['manifest']), Path(bound['source_root']), profile, worker,
                        'run', packet, out/'host-hours.json', compile_workers=2)
        native = json.loads((packet/'ticket.json').read_bytes())
        packed = json.loads((packet/'manifest.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'), sha256=queue.sha(packet/'package.tar.gz'),
            ticket_sha256=queue.sha(packet/'ticket.json'), manifest_sha256=queue.sha(packet/'manifest.json'),
            worker_id=worker, profile=profile, native_root=native['native_root'],
            runner='tools/native_long_package_v3.py', runner_sha256=packed['sources']['tools/native_long_package_v3.py'],
            stager=str(ROOT/'tools/native_long_stage_v3.py'), stager_sha256=queue.sha(ROOT/'tools/native_long_stage_v3.py'),
            stager_dependencies=[dict(path=str(ROOT/name), sha256=queue.sha(ROOT/name)) for name in
                ('tools/native_long_stage_v1.py', 'tools/native_package_v3.py', 'tools/native_package_v2.py')], max_seconds=10800))
    ticket = dict(schema='gfn16-global-ticket-v1', id='s4-p16-c2-lean-r7-continuous1000-serial-q1-v1',
        owner='independent-review', created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), priority='P3',
        kind='sim', needs='verilator', tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4), minimum_ram_gib=8,
        minimum_ram_rationale='lean build; host GL assumed (unimplemented); own serial100 source/forecast only.',
        est_minutes=100, promotion_bound=False, test_role='normal', rtl_readiness=manifest['rtl_readiness'],
        after=[role.pilot.ID], on='PASS_expected_contracts', packages=variants)
    role.dump(out/'global-ticket.json', ticket)
    role.dump(out/'preparation.json', dict(status='PREPARED_NOT_NATIVE', id=ticket['id'], admission=bound['admission']))
    return dict(id=ticket['id'], ticket=str(out/'global-ticket.json'), status='PREPARED_NOT_SUBMITTED')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(prepare(parser.parse_args().output), indent=2))
