"""Read-only author consolidation for the frozen canonical1 P8 promotion.

Metadata/source hashes and bounded scalar cycle arithmetic only. Never imports
candidate preparation, GMP, NTT or HDL runners; independent replay is separate.
Prints a repeatable JSON handoff, rather than changing frozen evidence.
"""
import argparse
import ast
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import tarfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
FIT = 'artifacts/s4-p8-canonical-pipe-whole-aw16-f164-v2/project'
FIT_PIN = '3609c409adf2650d40611a037cae832c534e79b0052f0c0ddac0c6f951abcc38'
TOP = 'genefer_stream27_host_chain_aw16_p8_canonreg_v1'
TOP_PIN = '140e2b306e39a5fba02046917d0733eb31ed1e2f9c80f81be7fd086181b8c051'
LEAF = 'genefer_stream27_canonical_image_pipe_v1.sv'
LEAF_PIN = '763b069a9797b91c7122bdf30fe86879b8c34dd318613ec4e096797610a379a5'
LEDGER_PINS = {
    'reference/stream27_host_chain_v1.py': '0ca7724092b7b93dfe5976f8dac023cf90aab7a483e877cc3f126acee04c3759',
    'reference/stream27_host_chain_param_v3.py': '017f581581d3f832cbb511a278901afb0a9a59ae6ed14a8df6234641634aa102',
}
JOBS = {
    'full_normal_and_cold_short': ('s4-aw16-p8-canon-pipe-host-normal-q1-v2', '892d867b1162c9ea8a4d185732d2402dd970db9206263762e4ebd90755461423'),
    'eight_prps': ('s4-p8-canon1-eight-prp-normal-q1-v1', '89c76819658b54c92e3369157c8df39232d0358ea9172760b5a73a5dc86c2cd2'),
    'whole_host_faults': ('s4-p8-canon1-host-faults-q1-v1', 'f3543ab076fc3476f0f1cbff9933aef19166e0b675b33fe80ba03e279ee6ef91'),
    'continuous100': ('s4-p8-canon1-continuous100-normal-q1-v1', 'dc67f76568b375c72832d4a35fd1e6b977c7aeb303d98bb5223e60cb5768d242'),
    'continuous1000': ('s4-p8-canon1-continuous1000-normal-q1-v2', '019024a90e375e7cb2864723920ad647c3692109b17c4fd793794033ebc7846e'),
    'leaf_aw5_normal': ('s4-canon-pipe-aw5-p8-normal-q1-v2', None),
    'leaf_aw8_normal': ('s4-canon-pipe-aw8-p8-normal-q1-v2', None),
    'leaf_faults': ('s4-canon-pipe-aw5-p8-fault-q1-v1', None),
}


def need(ok, message):
    if not ok:
        raise ValueError('P8_CANON1_PROMOTION_' + message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def ref(path, root=ROOT):
    p = root / path
    return dict(path=path, sha256=sha(p.read_bytes()))


def source_cycles(n, geometry, count, cache_hit=False, special=False, root=ROOT):
    """Execute only the two exact frozen scalar function ASTs, no imports."""
    functions = []
    for path, pin in LEDGER_PINS.items():
        raw = (root / path).read_bytes()
        need(sha(raw) == pin, 'LEDGER_SOURCE_DRIFT')
        nodes = [x for x in ast.parse(raw).body if isinstance(x, ast.FunctionDef) and x.name == 'cycle_contract']
        need(len(nodes) == 1, 'LEDGER_FUNCTION')
        functions.append(nodes[0])
    ns = {}
    exec(compile(ast.Module(body=[functions[0]], type_ignores=[]), '[frozen scalar ledger]', 'exec'), ns)
    ns['ledger'] = SimpleNamespace(cycle_contract=ns['cycle_contract'])
    exec(compile(ast.Module(body=[functions[1]], type_ignores=[]), '[frozen scalar canonical delta]', 'exec'), ns)
    return ns['cycle_contract'](n, geometry, count=count, cache_hit=cache_hit,
                                special=special, canonical_pipe_stages=1)


def sample_ledger(root=ROOT):
    n, base, k = 65536, 604832956, 1911814
    need(math.floor(n * math.log2(base)) + 1 == k, 'LEADING_BIT_COUNT')
    g = dict(warm_interval=16653, carry_done=24847)
    cold = source_cycles(n, g, k, root=root)
    cached = source_cycles(n, g, k, cache_hit=True, root=root)
    special = source_cycles(n, g, k, special=True, root=root)
    need(cold['host_done'] == 31838102204 and cached['host_done'] == 31838102105, 'SAMPLE_CYCLES')
    need(cold['host_done'] - cached['host_done'] == 99 and
         special['host_done'] - cold['host_done'] == n, 'COLD_SPECIAL_DELTA')
    sec = lambda cycles: str(Decimal(cycles) * Decimal('12.814') / Decimal(10**9))
    return dict(base=base, n=n, p=8, operations=k,
        bit_convention='K=floor(N*log2(base))+1 includes leading exponent bit; x0=1 and every bit performs square then optional double. Sample full PRP not executed.',
        selected_period_ns='12.814', selected_frequency_mhz=str(Decimal(1000)/Decimal('12.814')),
        cold_primary_cycles=cold['host_done'], cold_primary_seconds=sec(cold['host_done']),
        cached_alternate_cycles=cached['host_done'], cached_alternate_seconds=sec(cached['host_done']),
        cold_setup_extra_cycles=99, first_field_accept_cold=102, first_field_accept_cached=3,
        warm_interval=16653, carry_done=24847, canonical_normal_cycles=9*n,
        copy_cycles=n+3, canonical_and_copy_occurrences=1,
        equation='102 + (1911814-1)*16653 + 24847 + 2 + 9*65536 + 65536 + 4',
        sentinel_alternate_extra_cycles=n,
        scope='Compute-only source-ledger projection: cold setup and one ordinary final canonical/copy included; initial host load, final host readback, board I/O, stalls/gaps and measured full PRP excluded.',
        method='Frozen scalar functions only; no full-N arithmetic/oracle run.',
        source_functions=[ref(path, root) for path in LEDGER_PINS])


def fit_sources(root=ROOT):
    path = FIT + '/manifest.json'
    need(ref(path, root)['sha256'] == FIT_PIN, 'FIT_MANIFEST_DRIFT')
    m = json.loads((root / path).read_text())
    sources = m['source_sha256']
    need(len(sources) == 49 and sources[TOP+'.sv'] == TOP_PIN and sources[LEAF] == LEAF_PIN, 'FIT_SOURCE_MAP')
    need(m['core_parameters'] == dict(AW=16,P=8,CONTEXTS=1,EPOCH_SEED=65534,CANONICAL_PIPE_STAGES=1), 'FIT_PARAMETERS')
    for name, pin in sources.items():
        need(sha((root / FIT / 'rtl' / name).read_bytes()) == pin, 'FIT_RTL_DRIFT:'+name)
    for name, pin in m['control_sha256'].items():
        need(sha((root / FIT / name).read_bytes()) == pin, 'FIT_CONTROL_DRIFT:'+name)
    return m


def compact_metadata(manifest):
    """The pinned manifest retains vectors/certificates; do not duplicate them."""
    result = {}
    for key in ['p8_prp_qualification','canonical_qualification','canonical_pipe','continuous']:
        if key not in manifest:
            continue
        value = dict(manifest[key])
        for field in ['generated_sha256','source_sha256']:
            if field in value:
                value[field+'_map_digest'] = sha(json.dumps(value.pop(field),sort_keys=True).encode())
        if 'cases' in value:
            value['cases'] = [{k:c[k] for k in ['index','base','label','operations','doubles','cycles','baseline_cycles']} |
                dict(bit_program_sha256=sha(json.dumps(c['bits']).encode()),proof_metadata_sha256=sha(json.dumps(c['proof'],sort_keys=True).encode()))
                for c in value['cases']]
        if 'plan' in value:
            plan = dict(value['plan'])
            plan['double_bits_sha256'] = sha(plan.pop('double_bits').encode())
            value['plan'] = plan
        result[key] = value
    return result


def native(role, job, report_pin, fitted, root=ROOT):
    base = 'queue/evidence/' + job
    directory = base + '/attempt-0/collected/output/native'
    gate = json.loads((root / base / 'gate-receipt.json').read_text())
    r = json.loads((root / directory / 'report.json').read_text())
    m = json.loads((root / directory / 'approved-manifest.json').read_text())
    need(gate['status'] == 'PASS_expected_contracts' and gate['id'] == job, 'GATE:'+job)
    need(gate['report_sha256'] == ref(directory+'/report.json', root)['sha256'], 'REPORT_GATE:'+job)
    if report_pin:
        need(gate['report_sha256'] == report_pin, 'REPORT_PIN:'+job)
    need(gate['manifest_sha256'] == ref(directory+'/approved-manifest.json', root)['sha256'] == r['manifest_sha256'], 'MANIFEST:'+job)
    need(m['sources'] == r['sources'] and r['model_threads'] == 1 and
         r['probe'] == dict(context_threads=1,model_threads=1,expected_threads=1), 'SOURCES_PROBE:'+job)
    archive = root / directory / 'sources.tar.gz'
    need(sha(archive.read_bytes()) == r['artifacts']['sources.tar.gz'], 'SOURCE_ARCHIVE:'+job)
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        need(len(members) == len(r['sources']) and len({x.name for x in members}) == len(members), 'SOURCE_COUNT:'+job)
        for member in members:
            path = PurePosixPath(member.name)
            need(member.isfile() and not path.is_absolute() and '..' not in path.parts and member.name in r['sources'], 'UNSAFE_SOURCE:'+job)
            need(sha(tar.extractfile(member).read()) == r['sources'][member.name], 'SOURCE_BYTES:'+job)
    sv = {PurePosixPath(name).name:r['sources'][name] for name in m['build']['sv_sources']}
    need(sv[LEAF] == LEAF_PIN, 'CANONICAL_LEAF:'+job)
    if role in ('full_normal_and_cold_short','continuous100','continuous1000'):
        need(len(sv) == 60 and all(sv.get(name) == pin for name,pin in fitted['source_sha256'].items()), 'FITTED49_JOIN:'+job)
    typed = {x['name']:x for x in gate['steps']}
    for contract in m['steps']:
        actual = next(x for x in r['steps'] if x['name'] == contract['name'])
        t = typed[contract['name']]
        need(actual['returncode'] == contract['expected_returncode'] == t['actual_returncode'], 'STEP_RETURN:'+job)
        for field, afield, hfield in [('expected_stdout','log','stdout_sha256'),('expected_stderr','stderr_log','stderr_sha256')]:
            raw = (root / directory / actual[afield]).read_bytes()
            need(sha(raw) == t[hfield], 'STEP_LOG:'+job)
            if field in contract:
                need(raw.decode() == contract[field], 'EXACT_TEXT:'+job)
    if role.startswith('continuous'):
        count = 100 if role == 'continuous100' else 1000
        validation = gate['steps'][0]['validation'];c = validation['counts']
        expected = source_cycles(65536,dict(warm_interval=16653,carry_done=24847),count,root=root)
        need(validation['candidate_root_sha256'] == TOP_PIN and validation['independent_reference_equal'] and
             validation['final_actual_sha256'] == validation['final_expected_sha256'], 'ARRAY_BINDING:'+job)
        need(c['operations'] == count and c['doubles'] == count//2 and
             all(c[key] == 1 for key in ['resets','loads','starts','readbacks']) and
             c['signed96_words'] == 65536 and c['candidate_cycles'] == expected['host_done'] and
             c['canonical_cycles'] == 9*65536 and c['copy_cycles'] == 65539, 'CONTINUOUS_CALENDAR:'+job)
    return dict(role=role,id=job,gate=ref(base+'/gate-receipt.json',root),
        report=ref(directory+'/report.json',root),manifest=ref(directory+'/approved-manifest.json',root),
        source_archive=ref(directory+'/sources.tar.gz',root),source_count=len(r['sources']),rtl_count=len(sv),
        fitted49_join=role in ('full_normal_and_cold_short','continuous100','continuous1000'),
        host=r['host'],model_threads=r['model_threads'],overall_seconds=r['seconds'],
        contracts=[{k:step[k] for k in ['name','argv','expected_returncode','validator'] if k in step} |
            {k+'_sha256':sha(step[k].encode()) for k in ['expected_stdout','expected_stderr'] if k in step}
            for step in m['steps']],typed_results=gate['steps'],
        metadata=compact_metadata(m),
        numerical_recompute=False,author_does_not_claim_independent_replay=True)


def audit(number,period,closes,root=ROOT):
    path=f'queue/standing-fit-state/audit-terminal/s4-p8-canonical-pipe-whole-10000-v1-audit{number}/receipt.json'
    d=json.loads((root/path).read_text());s=d['timing']['selected']
    need(s['period_ns'] == period and d['timing_closes'] is closes and d['original_unchanged'] and d['compiled_input_unchanged'], 'AUDIT_BINDING')
    corners={name:{kind:row[kind] for kind in ['setup','hold','mpw','recovery','removal']} for name,row in s['corners'].items()}
    return dict(receipt=ref(path,root),period_ns=period,timing_closes=closes,corners=corners,
        original_tree_sha256=d['original_tree_sha256'],qdb_inventory_sha256=d['qdb_inventory_sha256'],
        observed_setup_paths=s['observed_setup_paths'],observed_failing_setup_paths=s['observed_failing_setup_paths'],
        scope='Same saved whole layout; four-corner scoped internal STA, virtual I/O, recovery/removal excluded_no_paths; not board/reset-release or exhaustive maximum clock.')


def consolidate(root=ROOT):
    fitted=fit_sources(root)
    receipts=[native(role,*args,fitted,root) for role,args in JOBS.items()]
    audits=[audit(5,12.814,True,root),audit(4,12.812,False,root)]
    need(audits[0]['original_tree_sha256'] == audits[1]['original_tree_sha256'] and audits[0]['qdb_inventory_sha256'] == audits[1]['qdb_inventory_sha256'], 'AUDIT_LAYOUT_DRIFT')
    history=[]
    for job in ['s4-canon-pipe-aw5-p8-normal-q1-v1','s4-canon-pipe-aw8-p8-normal-q1-v1','s4-aw16-p8-canon-pipe-host-normal-q1-v1','s4-p8-canon1-continuous1000-normal-q1-v1']:
        path='queue/done/'+job+'.json';d=json.loads((root/path).read_text())
        history.append(dict(id=job,receipt=ref(path,root),status=d['result']['status'],error=d['result'].get('queue_report',{}).get('error'),reason=d['result'].get('reason')))
    review_path='results/throughput-20260929/s4-p8-canon1-promotion-independent-v1.json'
    review=json.loads((root/review_path).read_text())
    need(ref(review_path,root)['sha256'] == '36dd77ecf5978799a5a02def89b3658cae8c14acd4e6ff7d3524e0152463458c' and
         review['status'] == 'PASS_internal_compute_only_evidence_ready_for_advisor_verification' and
         review['candidate_root_sha256'] == TOP_PIN, 'FINAL_INDEPENDENT_RECEIPT')
    return dict(schema='stream27-p8-canon1-promotion-author-handoff-v1',status='AUTHOR_CONSOLIDATION_COMPLETE_FINAL_INDEPENDENT_PASS_REFERENCED_ADVISOR_PENDING',
        independent_review=ref(review_path,root),
        producer=ref('reference/stream27_p8_canon1_promotion_v1.py',root),author_tests=ref('tests/test_stream27_p8_canon1_promotion_v1.py',root),
        candidate='canonical-pipeline P8, contexts1, no r75 flags',source_map=dict(fit_manifest=ref(FIT+'/manifest.json',root),
        top=TOP,top_sha256=TOP_PIN,canonical_leaf_sha256=LEAF_PIN,standalone49=fitted['source_sha256'],control_sha256=fitted['control_sha256']),
        receipt_index=receipts,selected_layout_audits=audits,sample_ledger=sample_ledger(root),preserved_history=history,
        complete_author_scope=['own eight small PRPs','own full9 cold1/cached8 two-image loaded-state normal','own100 and uninterrupted1000 one-reset/load/start/final-read FIFO jobs','own minimal whole-host underflow/reset/recovery/typed comparator controls','exact leaf AW5/AW8 normal/sentinel plus leaf range/reset/read-oracle controls','exact49 fitted RTL matches full normal/100/1000'],
        remaining=['Advisor verification and main adoption; no author self-promotion'],
        scope_limits=['No executed full-size sample PRP or board runtime','100/1000 dense signed mixed-bit chain is not the complete sample PRP','No component clock inheritance or P16/r75 source inheritance','Recovery/removal audit reports no paths, not asynchronous reset-release signoff','Minimal whole-host controls do not claim exhaustive malformed descriptor/fault coverage','No standalone new canonical1 short ticket: own full9 contains exact cold1 and cached8 stopped jobs'],
        method='Read-only metadata/source archive hashing and exact text/typed contract checks plus bounded scalar frozen cycle function arithmetic; no GMP, NTT, HDL, vendor or native rerun.')


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=ROOT)
    a=p.parse_args();print(json.dumps(consolidate(a.root),sort_keys=True,indent=2))
