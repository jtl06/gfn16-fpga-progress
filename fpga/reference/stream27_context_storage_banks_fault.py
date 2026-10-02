"""Separate storage2 diagnostics on the frozen actual AW8 normal candidate.

No local HDL or integer reference execution. Public queue owns native runs.
Only early-cache mode has a diagnostic RTL delta; every other role compiles
the exact production53. Generated-root corruption is simulation-only.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tarfile

from . import stream27_context_storage_banks_native as native

ROOT = native.ROOT
SELF = 'reference/stream27_context_storage_banks_fault.py'
CPP = 'rtl/tb/stream27_context_storage2_fault.cpp'
HEADER = 'rtl/tb/c2_storage2_fault_config.h'
NORMAL = ROOT / 'results/throughput-20260929/trackS-c2-storage2-native-v1/aw8-normal'
MANIFEST_PIN = '2a0c70c0e14844f667ce1f39bc7a45e37572b0a46c5ee597649b7d469beb0940'
MODES = ('external', 'reset', 'owner', 'early-cache', 'oracle')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def role(mode):
    native.need(mode in MODES, 'FAULT_MODE')
    raw = (NORMAL / 'manifest.json').read_bytes()
    native.need(sha(raw) == MANIFEST_PIN, 'FAULT_FROZEN_NORMAL')
    manifest = json.loads(raw)
    files = {}
    for name, pin in manifest['sources'].items():
        data = (NORMAL / 'source/fpga' / name).read_bytes()
        native.need(sha(data) == pin, 'FAULT_SOURCE:' + name)
        files[name] = data
    evidence = ROOT / 'queue/evidence' / native.IDS['aw8']
    gate = json.loads((evidence / 'gate-receipt.json').read_text())
    native.need(gate['status'] == 'PASS_expected_contracts', 'FAULT_ACTUAL_NORMAL')
    archive = evidence / 'attempt-0/collected/output/native/generated-sources.tar.gz'
    top = manifest['build']['top']
    with tarfile.open(archive) as stream:
        root = stream.extractfile('V' + top + '___024root.h').read().decode()
    prefix = top + '__DOT__engine__DOT__arithmetic__DOT__field0__DOT__'
    members = ('seed_running', 'payload_reserved', 'payload_ready', 'payload_owner',
               'fwd_slot', 'protocol_pw_row', 'term_producer__DOT__product_slot',
               'term_producer__DOT__context_valid')
    native.need(all(prefix + member in root for member in members), 'FAULT_ACTUAL_ROOT_ABI')
    rtl_before = {name: files[name] for name in manifest['build']['sv_sources']}
    delta = []
    if mode == 'early-cache':
        # Sole diagnostic: inject a genuine full-owner cache token at seed
        # start, before the four E4 seed products. No corruption of arithmetic.
        term = 'genefer_stream27_term_context_param_v1_contexts_v1_storage2_v1'
        old = 'rtl/' + term + '.sv'
        newterm = term + '_earlycache_probe'
        text = files.pop(old).decode()
        text = native.binder.parent.once(text, 'module ' + term + ' #', 'module ' + newterm + ' #')
        text = native.binder.parent.once(text,
            "assign cache_ready=product_slot && product_row==ROW_W'(3) && !stop &&\n                       bank_owner[prod_bank]==product_owner;",
            "assign cache_ready=(seed_slot && seed_start && !stop) ||\n                       (product_slot && product_row==ROW_W'(3) && !stop &&\n                       bank_owner[prod_bank]==product_owner);")
        text = native.binder.parent.once(text, 'assign cache_owner=product_owner;',
            'assign cache_owner=(seed_slot && seed_start) ? seed_owner : product_owner;')
        new = 'rtl/' + newterm + '.sv'
        files[new] = text.encode()
        manifest['build']['sv_sources'] = [new if name == old else name for name in manifest['build']['sv_sources']]
        field = next(name for name in files if '_f0_' in name and name.endswith('_storage2_v1.sv'))
        files[field] = native.binder.parent.once(files[field].decode(), term + ' #', newterm + ' #').encode()
        delta = [old, field]
    normal_footer = manifest['steps'][0]['expected_stdout']
    footers = {
        'external': 'C2_STORAGE_EXTERNAL_PASS bad_base=1 stale_generation=1 full32_index=1 global_abort=3 peer_recovery=0\n',
        'reset': normal_footer * 3 + 'C2_STORAGE_RESET_PASS seed=1 pointwise=1 last_read_e4=1 quiet_edges=24 recovered_reads=3072 epoch_wrap=1\n',
        'owner': normal_footer + 'C2_STORAGE_OWNER_PASS mutants=4 full27=1 bank_context_epoch_generation=1 publication=0 recovered_reads=1024 simulation_only=1\n',
        'early-cache': 'C2_STORAGE_EARLY_CACHE_PASS seed_start_token=1 duplicate_cache_rejected=1 publication=0 simulation_only=1\n'}
    if mode == 'oracle':
        step = dict(name='storage2-oracle', argv=['{exe}', '--oracle-negative'], expected_returncode=1,
                    expected_stdout='', expected_stderr='S4_HOST_CONTEXT_SIGNED96_VALUE ctx=0 address=0\n')
    else:
        files[CPP] = (ROOT / CPP).read_bytes()
        files[HEADER] = ('#pragma once\n#include "V' + top + '___024root.h"\n'
                        '#define STORAGE(member) d.rootp->' + prefix + ' ## member\n').encode()
        manifest['build']['cpp_source'] = CPP
        step = dict(name='storage2-' + mode, argv=['{exe}', '--' + mode], expected_returncode=0,
                    expected_stdout=footers[mode], expected_stderr='')
    files['lineage/' + SELF] = (ROOT / SELF).read_bytes()
    manifest['sources'] = {name: sha(data) for name, data in files.items()}
    manifest.update(steps=[step], test_role='deliberate_fault', source_root='UNBOUND', output_parent='UNBOUND')
    manifest.pop('rtl_readiness', None)
    manifest['storage2_fault'] = dict(mode=mode, actual_normal_gate_sha256=sha((evidence / 'gate-receipt.json').read_bytes()),
        normal_input_manifest_sha256=MANIFEST_PIN, generated_header_archive_sha256=sha(archive.read_bytes()),
        production_rtl_unchanged=not delta, diagnostic_rtl_delta=delta,
        full_owner_bits=27, reset_scope='Actual seed/first PW/last PW with E4 product present; 8 quiet edges then both full chains',
        owner_scope='Simulation-only four full27 physical payload key bit flips, not arbitrary corruption/hardware injection',
        shared_fault_peer_recovery=False, promotion_allowed=False)
    native.need(len(rtl_before) == 53 and all(files[name] == data for name, data in rtl_before.items()
                if name not in delta), 'FAULT_ONLY_DECLARED_RTL_DELTA')
    return manifest, files


def prepare(output, mode):
    from fpga.tools import candidate_ladder, native_class_package_v2 as package
    out = Path(output).resolve()
    native.need(out.is_relative_to(ROOT) and not out.exists(), 'FAULT_FRESH_OUTPUT')
    native.need(not any((ROOT / path).exists() for path in ('queue/PAUSE', 'docs/briefs/PAUSE')), 'FAULT_PAUSE')
    manifest, files = role(mode)
    source = out / 'source/fpga'
    source.mkdir(parents=True)
    for name, data in files.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
    manifest['source_root'] = str(source)
    native.dump(out / 'manifest.json', manifest)
    native.dump(out / 'host-hours.json', candidate_ladder.budget_from_hourly())
    normal_ticket = json.loads((NORMAL / 'global-ticket.json').read_text())
    identifier = 's4-p16-c2-storage2-aw8-' + mode + '-q1-v1'
    variants = []
    for pair, template in zip(('01', '23'), normal_ticket['packages']):
        worker = 's4-p16-c2-storage2-' + mode + '-' + pair + '-v1'
        packet = out / ('packet-' + pair)
        result = package.prepare(out / 'manifest.json', source, template['profile'], worker, 'run', packet, out / 'host-hours.json')
        ticket = json.loads((packet / 'ticket.json').read_text())
        variant = copy.deepcopy(template)
        variant.update(archive=str(packet / 'package.tar.gz'), sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'], manifest_sha256=sha((packet / 'manifest.json').read_bytes()),
            worker_id=worker, native_root=ticket['native_root'])
        variants.append(variant)
    logical = {key: copy.deepcopy(normal_ticket[key]) for key in ('schema','owner','priority','kind','needs','tool_identity',
               'resources','minimum_ram_gib','minimum_ram_rationale','est_minutes','promotion_bound')}
    logical.update(id=identifier, created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        test_role='deliberate_fault', packages=variants, after=[native.IDS['aw8']], on='PASS_expected_contracts')
    native.dump(out / 'global-ticket.json', logical)
    return dict(id=identifier, ticket=str(out / 'global-ticket.json'), status='prepared_not_native', mode=mode)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=MODES, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.mode), indent=2))
