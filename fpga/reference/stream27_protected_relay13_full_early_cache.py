"""Own full-N protected R13 premature-cache diagnostic; production snapshots untouched.

Only F0's term leaf is cloned to propose a genuine full-owner seed-start cache
token before E4 seed products. F1/F2 keep their original shared term leaf.
The native harness must observe that premature token before claiming detection.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fpga.reference import stream27_protected_relay13_full_fault as full

ROOT = full.ROOT
SELF = 'reference/stream27_protected_relay13_full_early_cache.py'
ID = 's4-p16-c2-protected-relay13-full-early-cache-q1-v1'
TERM = 'genefer_stream27_term_context_param_v1_contexts_v1_storage2_v1_payload_lookahead_v1_select_token_v1'
OUT = full.BASE / 'full-early-cache-v1'
FOOTER = ('C2_STORAGE_FULL_EARLY_CACHE_PASS seed_start_token=1 '
          'premature_cache_rejected=1 publication=0 simulation_only=1\n')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def once(text, old, new):
    full.need(text.count(old) == 1, 'FULL_EARLY_CACHE_EXACT_ANCHOR')
    return text.replace(old, new, 1)


def role():
    manifest, files = full.role('contracts')
    archive = ROOT / 'queue/evidence' / full.GATE_ID / 'attempt-0/collected/output/native/generated-sources.tar.gz'
    with full.tarfile.open(archive) as stream:
        actual_root = stream.extractfile('V' + manifest['build']['top'] + '___024root.h').read().decode()
    prefix = files[full.HEADER].decode().split('#define STORAGE(member) d.rootp->', 1)[1].split(' ## member', 1)[0]
    full.need(prefix + 'term_cache_ready' in actual_root, 'FULL_EARLY_CACHE_ACTUAL_CACHE_ABI')
    baseline = {n: files[n] for n in manifest['build']['sv_sources']}
    old = 'rtl/' + TERM + '.sv'
    probe_term = TERM + '_relay13_full_earlycache_probe'
    new = 'rtl/' + probe_term + '.sv'
    text = once(files[old].decode(), 'module ' + TERM + ' #', 'module ' + probe_term + ' #')
    text = once(text,
        "assign cache_ready=product_slot && product_row==ROW_W'(3) && !stop &&\n                       bank_owner[prod_bank]==product_owner;",
        "assign cache_ready=(seed_slot && seed_start && !stop) ||\n                       (product_slot && product_row==ROW_W'(3) && !stop &&\n                       bank_owner[prod_bank]==product_owner);")
    text = once(text, 'assign cache_owner=product_owner;',
        'assign cache_owner=(seed_slot && seed_start) ? seed_owner : product_owner;')
    files[new] = text.encode()
    field = next(n for n in baseline if '_f0_' in n and n.endswith('_relay13_v1.sv'))
    files[field] = once(files[field].decode(), TERM + ' #', probe_term + ' #').encode()
    # Do not replace/remove old: the other two fields still instantiate it.
    manifest['build']['sv_sources'].append(new)
    full.need(len(manifest['build']['sv_sources']) == 60 and
              all(files[n] == raw for n, raw in baseline.items() if n != field),
              'FULL_EARLY_CACHE_ONLY_F0_DIAGNOSTIC_DELTA')
    cpp = once(files[full.CPP].decode(),
        'fault_job(d,input);bool failed=false;\n for(unsigned age=1;age<1000;age++){',
        'fault_job(d,input);bool failed=false,observed=false;\n for(unsigned age=1;age<1000;age++){')
    cpp = once(cpp,
        'clear(d);edge(d);need(!d.done&&!d.canonical_ready&&!d.read_valid,"C2_FULL_EARLY_CACHE_NO_PUBLICATION");',
        '''clear(d);d.clk=0;d.eval();
  if(STORAGE(seed_running)&&STORAGE(term_cache_ready)&&!observed){
   need(!STORAGE(term_producer__DOT__product_slot),"C2_FULL_EARLY_CACHE_ACTUAL_PREMATURE_TOKEN");observed=true;
  }
  d.clk=1;d.eval();need(!d.done&&!d.canonical_ready&&!d.read_valid,"C2_FULL_EARLY_CACHE_NO_PUBLICATION");''')
    cpp = once(cpp, 'need(failed,"C2_FULL_EARLY_CACHE_NOT_DETECTED");',
               'need(observed&&failed,"C2_FULL_EARLY_CACHE_NOT_DETECTED");')
    cpp = once(cpp, 'duplicate_cache_rejected=1', 'premature_cache_rejected=1')
    files[full.CPP] = cpp.encode()
    files['lineage/' + SELF] = (ROOT / SELF).read_bytes()
    manifest['steps'] = [dict(name='relay13-full-early-cache', argv=['{exe}', '--early-cache'],
        expected_returncode=0, expected_stdout=FOOTER, expected_stderr='')]
    manifest['sources'] = {n: sha(raw) for n, raw in files.items()}
    manifest['protected_relay13_full_fault'].update(full56_ordinal_alias=False,
        production_rtl_unchanged=False, diagnostic_rtl_delta=[field, new],
        diagnostic_scope='F0-only premature full-owner cache proposal; F1/F2 and all authority logic unchanged',
        early_cache_full_geometry=True, cache_latency=78, observed_premature_product_slot_false=True,
        publication_rejected=True, source_normal_gate=full.GATE_ID,
        eventual_duplicate_abort_only=True, origin_age_validation_not_proved=True,
        extra_early_token_and_genuine_later_row3_token_both_retained=True)
    snapshot = {n: sha(raw) for n, raw in files.items() if n.endswith('.sv')}
    manifest['rtl_readiness'] = dict(schema='gfn16-candidate-rtl-ready-v1',
        candidate_id='s4-p16-c2-protected-relay13-full-early-cache-diagnostic-v1',
        source_snapshot=snapshot,
        candidate_source_sha256=sha(json.dumps(snapshot, sort_keys=True, separators=(',', ':')).encode()),
        rtl_ready_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'))
    return manifest, files


def prepare():
    from fpga.tools import candidate_ladder, native_class_package_v2 as package
    full.need(not OUT.exists() and not any((ROOT / n).exists() for n in
              ('queue/PAUSE', 'docs/briefs/PAUSE')), 'FULL_EARLY_CACHE_FRESH_UNPAUSED')
    manifest, files = role()
    source = OUT / 'source/fpga'
    source.mkdir(parents=True)
    for name, raw in files.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    manifest['source_root'] = str(source)
    full.dump(OUT / 'manifest.json', manifest)
    full.dump(OUT / 'host-hours.json', candidate_ladder.budget_from_hourly())
    variants = []
    for pair in ('01', '23'):
        profile = 'gcp-c4d-static' + pair + '-v1'
        worker = 's4-p16-c2-protected-relay13-full-early-cache-' + pair + '-v1'
        packet = OUT / ('packet-' + pair)
        result = package.prepare(OUT / 'manifest.json', source, profile, worker,
                                 'run', packet, OUT / 'host-hours.json')
        ticket = json.loads((packet / 'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet / 'package.tar.gz'), sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'], manifest_sha256=sha((packet / 'manifest.json').read_bytes()),
            worker_id=worker, profile=profile, native_root=ticket['native_root'],
            runner='tools/native_class_package_v2.py', runner_sha256=sha((ROOT / 'tools/native_class_package_v2.py').read_bytes()),
            stager=str(ROOT / 'tools/native_package_v4.py'), stager_sha256=sha((ROOT / 'tools/native_package_v4.py').read_bytes()),
            stager_dependencies=[dict(path=str(ROOT / n), sha256=sha((ROOT / n).read_bytes()))
                for n in ('tools/native_package_v3.py', 'tools/native_package_v2.py')], max_seconds=3700))
    logical = dict(schema='gfn16-global-ticket-v1', id=ID, owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        priority='P0', kind='sim', needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4),
        minimum_ram_gib=4,
        minimum_ram_rationale='Bounded exploratory4GiB full early-cache diagnostic of same full geometry with one F0 probe; no measured R13 fault peak or sufficiency promise. Retain OOM/timeout/no retry, desiredGCP8 unchanged.',
        est_minutes=10, promotion_bound=False, test_role='deliberate_fault',
        rtl_readiness=manifest['rtl_readiness'], packages=variants,
        allowed_hosts=['gfn16-pilot-c4d', 'aethia'], after=[full.GATE_ID], on='PASS_expected_contracts')
    full.dump(OUT / 'global-ticket.json', logical)
    return dict(id=ID, ticket=str(OUT / 'global-ticket.json'), status='PREPARED_NOT_NATIVE')


if __name__ == '__main__':
    print(json.dumps(prepare(), indent=2))
