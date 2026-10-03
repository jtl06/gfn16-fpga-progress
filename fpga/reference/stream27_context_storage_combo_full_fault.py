"""Combined C2 AW16 separate genuine full-size fault contracts."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tarfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-ownlong-v1'
DONOR = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-native-v1/full-normal'
SELF = 'reference/stream27_context_storage_combo_full_fault.py'
CPP = 'rtl/tb/stream27_context_storage2_full_fault.cpp'
HEADER = 'rtl/tb/c2_storage2_full_fault_config.h'
MANIFEST_PIN = 'fb3a56a95f0616c3a8b6799088ca37a1c477cc1fa274e3c7821fc75c60c8c437'
GATE_ID = 's4-p16-c2-combo-full-normal-q1-v1'
FOOTERS = {
 'external': 'C2_STORAGE_FULL_EXTERNAL_PASS bad_base=1 stale_generation=1 full32_index=1 global_abort=3 peer_recovery=0\n',
 'owner': 'C2_STORAGE_FULL_OWNER_PASS mutants=4 full27=1 bank_context_epoch_generation=1 publication=0 baseline_reads=262144 recovered_reads=262144 simulation_only=1\n',
 'reset': 'C2_STORAGE_FULL_RESET_PASS seed=1 pointwise=1 last_read_e4=1 quiet_edges=24 recovered_reads=786432 epoch_wrap=1\n',
 'ordinal': 'C2_STORAGE_FULL_ORDINAL_PASS alias_delta=65536 low16_epoch_same=1 full56=1 capture_bad_origin=1 same_edge_error=1 publication=0 baseline_reads=262144 recovered_reads=262144 simulation_only=1\n',
 'early-cache': 'C2_STORAGE_FULL_EARLY_CACHE_PASS seed_start_token=1 duplicate_cache_rejected=1 publication=0 simulation_only=1\n'}


def need(ok, why):
    if not ok:
        raise ValueError('C2_STORAGE_FULL_FAULT_' + why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def role(mode):
    need(mode == 'contracts', 'MODE')
    raw = (DONOR / 'manifest.json').read_bytes()
    need(sha(raw) == MANIFEST_PIN, 'ORIGINAL_FULL_CAPTURE')
    manifest = json.loads(raw)
    files = {name: (DONOR / 'source/fpga' / name).read_bytes() for name in manifest['sources']}
    need(all(sha(files[name]) == pin for name, pin in manifest['sources'].items()), 'SOURCE_PINS')
    evidence = ROOT / 'queue/evidence' / GATE_ID
    gate = (evidence / 'gate-receipt.json').read_bytes()
    need(json.loads(gate)['status'] == 'PASS_expected_contracts', 'ACTUAL_FULL_NORMAL')
    archive = evidence / 'attempt-0/collected/output/native/generated-sources.tar.gz'
    top = manifest['build']['top']
    with tarfile.open(archive) as stream:
        generated = stream.extractfile('V' + top + '___024root.h').read().decode()
    host = top + '__DOT__candidate__DOT__'
    storage = host + 'engine__DOT__arithmetic__DOT__field0__DOT__'
    for prefix, members in ((host, ('job_count', 'capture_bad')), (storage, ('seed_running', 'payload_reserved',
        'payload_ready', 'payload_owner', 'fwd_slot', 'protocol_pw_row', 'term_producer__DOT__product_slot',
        'term_producer__DOT__context_valid'))):
        need(all(prefix + name in generated for name in members), 'ACTUAL_GENERATED_ABI')
    before = {name: files[name] for name in manifest['build']['sv_sources']}
    delta = []
    need(len(before) == 54 and all(files[n] == raw for n, raw in before.items() if n not in delta), 'EXACT_PRODUCTION_SCOPE')
    files[CPP] = (ROOT / CPP).read_bytes()
    files[HEADER] = ('#pragma once\n#include "V' + top + '___024root.h"\n'
        '#define HOST(member) d.rootp->' + host + ' ## member\n'
        '#define STORAGE(member) d.rootp->' + storage + ' ## member\n').encode()
    files['lineage/' + SELF] = (ROOT / SELF).read_bytes()
    manifest['build']['cpp_source'] = CPP
    modes = ('external', 'owner', 'reset', 'ordinal', 'oracle')
    manifest['steps'] = [dict(name='storage2-full-' + name, argv=['{exe}', '--' + name],
        expected_returncode=1 if name == 'oracle' else 0, expected_stdout='' if name == 'oracle' else FOOTERS[name],
        expected_stderr='R84_FULL_SIGNED96_REFERENCE ctx=0 address=0\n' if name == 'oracle' else '') for name in modes]
    manifest['sources'] = {n: sha(raw) for n, raw in files.items()}
    manifest['test_role'] = 'deliberate_fault'
    manifest['storage2_full_fault'] = dict(actual_full_normal_gate=GATE_ID, full_geometry=True,
        original_interval=8459, generated_header_archive_sha256=sha(archive.read_bytes()),
        production_rtl_unchanged=not delta, diagnostic_rtl_delta=delta, full27_payload_key=True,
        full56_ordinal_alias=mode == 'contracts', ordinal_origin_capture_bad_same_edge=True,
        baseline_and_recovery_both_full_chains=True, reset_actual_seed_pw_lastread_e4=True,
        shared_fault_peer_recovery=False, promotion_allowed=False)
    return manifest, files


def dump(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def prepare(mode):
    from fpga.tools import candidate_ladder, native_class_package_v2 as package
    out = BASE / ('full-fault-' + mode + '-v1')
    need(not out.exists() and not any((ROOT / p).exists() for p in ('queue/PAUSE', 'docs/briefs/PAUSE')), 'FRESH_UNPAUSED')
    manifest, files = role(mode)
    source = out / 'source/fpga'
    source.mkdir(parents=True)
    for name, raw in files.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    manifest['source_root'] = str(source)
    dump(out / 'manifest.json', manifest)
    dump(out / 'host-hours.json', candidate_ladder.budget_from_hourly())
    variants = []
    for pair in ('01', '23'):
        profile = 'gcp-c4d-static' + pair + '-v1'
        worker = 's4-p16-c2-combo-full-' + mode + '-' + pair + '-v1'
        packet = out / ('packet-' + pair)
        result = package.prepare(out / 'manifest.json', source, profile, worker, 'run', packet, out / 'host-hours.json')
        ticket = json.loads((packet / 'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet / 'package.tar.gz'), sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'], manifest_sha256=sha((packet / 'manifest.json').read_bytes()),
            worker_id=worker, profile=profile, native_root=ticket['native_root'], runner='tools/native_class_package_v2.py',
            runner_sha256=sha((ROOT / 'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT / 'tools/native_package_v4.py'), stager_sha256=sha((ROOT / 'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT / n), sha256=sha((ROOT / n).read_bytes()))
                for n in ('tools/native_package_v3.py', 'tools/native_package_v2.py')], max_seconds=3700))
    logical = dict(schema='gfn16-global-ticket-v1', id='s4-p16-c2-combo-full-' + mode + '-q1-v1', owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), priority='P1', kind='sim', needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1', resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4),
        minimum_ram_gib=4, minimum_ram_rationale='Bounded exploratory4GiB full-fault cap after own combined4GiB normal; exact production RTL, new diagnostic driver. Not measured fault sufficiency; retain resource failures/no automatic retry.',
        est_minutes=25, promotion_bound=False, test_role='deliberate_fault', rtl_readiness=manifest['rtl_readiness'], packages=variants, allowed_hosts=['gfn16-pilot-c4d','aethia'],
        after=[GATE_ID], on='PASS_expected_contracts')
    dump(out / 'global-ticket.json', logical)
    return dict(id=logical['id'], ticket=str(out / 'global-ticket.json'), status='PREPARED_NOT_NATIVE')


if __name__ == '__main__':
    print(json.dumps(prepare('contracts'), indent=2))
