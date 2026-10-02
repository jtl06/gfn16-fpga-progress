"""Emit three immutable ordinary global inputs for existing ordinal packets.

Read-only package/source validation occurs here. Public submit must still use
the dispatcher CLI and actual consumer adoption; no queue state is written.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from fpga.tools import global_queue_v1 as queue

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PIN = '2fc6d2dfab63f7b366826b51c59efa74c7c39f0ed77615da75dbeb4cff719245'
STAGER_PIN = 'a431a6efa0b9c63c75f553dc5994b4481c71458b25bdcfd33742d65e154cc1ff'
PACKETS = {
    (16, 'positive', '01'): ROOT / 'results/throughput-20260929/native-ordinal-duration-v1/packet-positive01',
    (16, 'positive', '23'): ROOT / 'artifacts/s4-ordinal-p16-positive-gcp23-v1',
    (16, 'negative', '01'): ROOT / 'artifacts/s4-ordinal-p16-negative-gcp01-v1',
    (16, 'negative', '23'): ROOT / 'artifacts/s4-ordinal-p16-negative-gcp23-v1',
    (8, 'negative', '01'): ROOT / 'artifacts/s4-ordinal-p8-negative-gcp01-v1',
    (8, 'negative', '23'): ROOT / 'artifacts/s4-ordinal-p8-negative-gcp23-v1',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def package(p, role, lane):
    path = PACKETS[p, role, lane]
    preparation = json.loads((path / 'preparation.json').read_text())
    ticket = json.loads((path / 'ticket.json').read_text())
    if sha(path / 'package.tar.gz') != preparation['archive_sha256'] or sha(path / 'ticket.json') != preparation['ticket_sha256']:
        raise ValueError('S4_ORDINAL_PACKET_DRIFT')
    if ticket['profile'] != f'gcp-c4d-static{lane}-v1':
        raise ValueError('S4_ORDINAL_PACKET_PROFILE')
    return dict(archive=str((path / 'package.tar.gz').resolve()), sha256=preparation['archive_sha256'],
        ticket_sha256=preparation['ticket_sha256'], manifest_sha256=ticket['manifest_sha256'],
        worker_id=ticket['id'], profile=ticket['profile'], native_root=ticket['native_root'],
        runner='tools/native_ordinal_package_v1.py', runner_sha256=PACKAGE_PIN,
        stager=str((ROOT / 'tools/native_ordinal_stage_v1.py').resolve()), stager_sha256=STAGER_PIN,
        stager_dependencies=[
            dict(path=str((ROOT / 'tools/native_package_v3.py').resolve()),
                 sha256='5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9'),
            dict(path=str((ROOT / 'tools/native_package_v2.py').resolve()),
                 sha256='3f2186fa5aac8129ac1ad5a161de39cf221925ee95d5de6364a941b199e7279a')],
        max_seconds=3700)


def prepare(destination):
    destination = Path(destination).resolve()
    if destination.exists() or (ROOT / 'docs/briefs/PAUSE').exists():
        raise ValueError('S4_ORDINAL_BATCH_FRESH_PAUSE')
    if sha(ROOT / 'tools/native_ordinal_package_v1.py') != PACKAGE_PIN or sha(ROOT / 'tools/native_ordinal_stage_v1.py') != STAGER_PIN:
        raise ValueError('S4_ORDINAL_BATCH_POLICY_DRIFT')
    created = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    output = []
    for p, role, after in [
        (16, 'positive', ['s4-aw5-p16-long-host-q1-v4']),
        (16, 'negative', ['s4-aw5-p16-ordinal-positive-q1-v1']),
        (8, 'negative', ['s4-aw5-p8-ordinal-host-q1-v4'])]:
        identifier = f's4-aw5-p{p}-ordinal-{role}-q1-v1'
        value = dict(schema='gfn16-global-ticket-v1', id=identifier, owner='stream-core',
            created=created, priority='P1', kind='sim', needs='verilator',
            tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
            resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4), minimum_ram_gib=8,
            allowed_hosts=['gfn16-pilot-c4d'], est_minutes=60, promotion_bound=False,
            after=after, on='PASS_expected_contracts',
            memory_policy='Exact existing GCP8GiB/2core/one-model-thread ordinal family only. Complete65540 operations and65539 descriptors; unchanged candidate RTL/corpus, no shortened count/3h/thread or Azure policy substitution.',
            packages=[package(p, role, lane) for lane in ('01', '23')],
            scope='Zero-invariant full32 final-selector control witness; not random PRP/fullN arithmetic/clock/promotion.')
        if p == 16 and role == 'positive':
            value['preserved_failed_predecessor'] = dict(id='s4-aw5-p16-ordinal-host-q1-v4',
                record='queue/done/s4-aw5-p16-ordinal-host-q1-v4.json',
                classification='command timeout, killed-9 after1800.098110s; not arithmetic mismatch',
                delta='Only one exact declared model command3300; existing overall3600/outer3700/stop15/ancillary1800 remain. Not infra_retry_of because runtime source identity changes.')
        queue.validate(value)
        output.append(value)
    destination.mkdir()
    pins = {}
    for value in output:
        path = destination / (value['id'] + '.json')
        path.write_text(json.dumps(value, indent=2) + '\n')
        pins[value['id']] = sha(path)
    result = dict(status='PASS_source_package_queue_schema_ONLY_NOT_submitted',
        queue_inputs=pins, packages=6, preparer_sha256=sha(__file__),
        public_consumer_adoption_required=True, queued=False, native_executed=False,
        promotion_allowed=False)
    (destination / 'source-preparation.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    import sys
    print(json.dumps(prepare(sys.argv[1]), indent=2))
