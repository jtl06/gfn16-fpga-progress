"""Read-only A10 archive replay, no full-N arithmetic or remote/native command."""
import hashlib
import json
from pathlib import Path
import re
import tarfile

from fpga.tools import run_a10_software_aethia_v1 as envelope
from fpga.tools import run_merged_negacyclic27_software_gate as frozen
from fpga.reference import merged_negacyclic27_model as model

ARCHIVE = Path(__file__).resolve().parents[1] / 'results/throughput-20260929/a10-merged-negacyclic-software-aethia-native-v1'
INVOCATION = '3d8198dc5dc74dc493f57744c1d48f5b'
PINS = {
    'terminal-read.json': '0719377fc69d2f69f87d4a6f36f3e5596c227fa64c3a0f372da8f392ca508f48',
    'preflight-read.json': '4820955a46d51ed7ac741904375387cfee7ad1cbc6a7a322b9a882ca624cb652',
    'stage-read.json': '2f860f6ed95b131e304775cd59625723cd17c11751ceaf3d762f830efe566b78',
    'approved-manifest-v1.json': 'ad88335fac1b57f52d560b8272a8f25f93ce03bf21255afe45fa33500d69e327',
    'source-v1.tar.gz': '726ffc16828b0cf86550ec4820d7dffb3923d2a5709e42c9d9d9a819564cc287',
    'context.json': '9729cac3a12097bad851ed4a0f7f5819520dceaf5f5fac367f66e1e5ba8ebb4a',
    'result.json': 'e35e053493febe61b6d986b62631164ed07f471ecb0f45ec2ebbc1412187b450',
    'gate/receipt.json': '3edf871e161635eecbf5f4230350b78856bd89add5680a439f32edf0b1e3300e',
    'stdout.log': 'ed2f1652ec0b0b83e4aa137ef9fe677381edbbe2997425355246a84f9c7a0b8a',
    'stderr.log': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
}


def need(ok, why):
    if not ok:
        raise ValueError(why)


def load(path):
    return json.loads(Path(path).read_text())


def verify(directory=ARCHIVE):
    directory = Path(directory).resolve()
    for name, digest in PINS.items():
        path = directory / name
        need(not path.is_symlink() and path.is_file() and envelope.sha(path) == digest, 'collected artifact pin: ' + name)
    actual = {str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file()}
    required = set(PINS) | {'terminal-read.json', 'preflight-read.json', 'stage-read.json'}
    need(actual == required | ({'review.json'} if 'review.json' in actual else set()), 'exact archive closure')
    manifest = load(directory / 'approved-manifest-v1.json')
    context = load(directory / 'context.json')
    result = load(directory / 'result.json')
    gate = load(directory / 'gate/receipt.json')
    status = load(directory / 'terminal-read.json')
    members = {}
    with tarfile.open(directory / 'source-v1.tar.gz') as archive:
        for member in archive.getmembers():
            need(member.isfile() and member.name.startswith('fpga/') and '..' not in Path(member.name).parts
                 and member.name not in members, 'safe exact source archive member')
            members[member.name] = archive.extractfile(member).read()
    need({name[5:]: hashlib.sha256(raw).hexdigest() for name, raw in members.items()} == manifest['sources']
         and len(members) == 16, 'sixteen exact source archive members')
    original_raw = members['fpga/' + envelope.ORIGINAL_MANIFEST]
    need(hashlib.sha256(original_raw).hexdigest() == envelope.ORIGINAL_SHA, 'original manifest untouched')
    original = json.loads(original_raw)
    need(gate['sources'] == original['sources'] and context['sources'] == manifest['sources'], 'gate/deployment source identities')
    need(gate['status'] == 'passed_software_arithmetic_only' and gate['manifest_sha256'] == envelope.ORIGINAL_SHA
         and gate['profile'] == model.PROFILE and gate['host'] == 'aethia', 'exact original software gate success')
    need(result['status'] == 'passed_A10_AW16_Python_arithmetic_only' and result['returncode'] == 0
         and result['context_sha256'] == PINS['context.json'] and result['source_manifest_sha256'] == PINS['approved-manifest-v1.json'],
         'successful source-bound child terminal')
    need(result['artifact_sha256'] == {name: PINS[name] for name in ('context.json', 'stdout.log', 'stderr.log', 'gate/receipt.json')},
         'exact retained artifact identities')
    need(context['manifest_sha256'] == PINS['approved-manifest-v1.json']
         and context['original_manifest_sha256'] == envelope.ORIGINAL_SHA
         and context['python_sha256'] == envelope.PYTHON_SHA and context['software_only'] is True
         and context['HDL_or_compiler_started'] is False and context['shared_compile_lock_acquired'] is False, 'Python-only execution identity')
    limits = context['limits']
    need(limits['affinity'] == [0, 2] and limits['physical_cores'] == [[0, 0], [0, 1]]
         and limits['cpu_max'] == ['200000', '100000'] and limits['memory_max_bytes'] == 6 << 30
         and limits['memory_swap_max_bytes'] == 0, 'actual finite disjoint physical resource caps')
    command = [str(envelope.PYTHON), '-I', '-B', str(envelope.SOURCE / envelope.RUNNER), '--manifest',
               str(envelope.SOURCE / envelope.ORIGINAL_MANIFEST), '--manifest-sha', envelope.ORIGINAL_SHA,
               '--output', result['output'] + '/gate']
    need(context['command'] == result['command'] == command, 'exact archived frozen runner command')
    vector = members['fpga/' + frozen.VECTOR]
    need(hashlib.sha256(vector).hexdigest() == frozen.VECTOR_SHA, 'exact frozen AW16 vectors')
    # Parse only command headers; do not execute any NTT, carry or whole-integer arithmetic locally.
    events = re.findall(r'^(LOAD(?:_KEEP)?|RUN(?:_NOREAD)?)\s+(\S+)\s+(\d+)', vector.decode(), re.M)
    expected = []
    base = None
    for kind, label, value in events:
        if kind.startswith('LOAD'):
            base = int(value)
        else:
            expected.append(dict(name=label, base=base, fields=3, double_bit=int(value),
                                 residues_checked=196608, digits_checked=65536, status='passed'))
    need(gate['cases'] == expected and len(expected) == 12, 'exact ordered native twelve-case vector headers')
    need((directory / 'stdout.log').read_text().splitlines() == ['passed ' + row['name'] for row in expected]
         and (directory / 'stderr.log').stat().st_size == 0, 'exact twelve-case stdout and empty stderr')
    negatives = [dict(field=f.p, fault=fault, status='detected') for f in model.FIELDS for fault in frozen.FAULTS]
    need(gate['negative_controls'] == negatives and len(negatives) == 27, 'exact three-field nine typed-negative matrix')
    need(gate['independent_vector_coverage'] == dict(operations=12, readbacks=10, aborts=0, loads=4,
         independent_eligibility_shadow=True), 'native independent whole-integer coverage')
    need(gate['cycle_model'] == model.cycle_work(), 'conditional cycle model unchanged, not a hardware record')
    need(status['invocation_id'] == INVOCATION and status['source_unchanged'] is True
         and 'ActiveState=inactive' in status['systemd_user_state'] and 'MainPID=0' in status['systemd_user_state'], 'terminal released own invocation')
    rows = status['user_journal_identity']['selected_rows']
    need(len(rows) == 3 and rows[0]['USER_INVOCATION_ID'] == rows[2]['USER_INVOCATION_ID'] == INVOCATION
         and rows[1]['_SYSTEMD_INVOCATION_ID'] == INVOCATION
         and rows[0]['CODE_FUNC'] == 'job_emit_done_message' and rows[2]['CODE_FUNC'] == 'unit_log_resources'
         and 'passed_A10_AW16_Python_arithmetic_only' in rows[1]['MESSAGE'], 'same user manager start/PASS/resource journal')
    return dict(status='PASS_archived_A10_AW16_Python_arithmetic_only', manifest_sha256=PINS['approved-manifest-v1.json'],
                original_manifest_sha256=envelope.ORIGINAL_SHA, source_archive_sha256=PINS['source-v1.tar.gz'],
                source_members=16, cases=12, fields=3, residues_compared=12 * 196608, digits_compared=12 * 65536,
                readbacks=10, typed_negatives=27, invocation_id=INVOCATION, elapsed_seconds=gate['elapsed_seconds'],
                memory_peak_bytes=int(rows[2]['MEMORY_PEAK']), swap_peak_bytes=int(rows[2]['MEMORY_SWAP_PEAK']),
                limits=limits, CPU0_2_released=True, frozen_sources_unchanged=True,
                evidence_class='aethia Python software arithmetic; not native HDL simulation', promotion_allowed=False,
                limitations=['No local full-N numeric NTT or whole-integer rerun.',
                             'Only Python executable is fingerprinted; OS/stdlib tree is not individually hashed.',
                             'Root-bank issue schedule, cycle record, normalization RTL and physical fit remain later gates.'])


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
