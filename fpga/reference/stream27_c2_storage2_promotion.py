"""Read-only evidence consolidation for ORIGINAL53 C2 storage2 route14.

Scalar source/clock/native receipt joins only. No local HDL/full-N arithmetic,
native replay, synthesis, fit, route, clock exception or adoption is performed.
"""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/throughput-20260929/trackS-c2-storage2-ownlong-v1'
DONOR = ROOT / 'results/throughput-20260929/trackS-c2-storage2-native-v1/full-normal'
FIT_ID = 's4-p16-c2-storage2-route14-aws12-v1'
AUDIT_BASE = ROOT / 'queue/standing-fit-state/audit-terminal'
FIT = ROOT / 'queue/standing-fit-state/terminal' / FIT_ID
NATIVE_IDS = {
 'aw8': 's4-p16-c2-storage2-aw8-normal-q1-v1',
 'full': 's4-p16-c2-storage2-full-normal-q1-v1',
 'pilot': 's4-p16-c2-storage2-own100-serial-q1-v1',
 'long': 's4-p16-c2-storage2-continuous1000-q1-v1',
 'full_contracts': 's4-p16-c2-storage2-full-contracts-q1-v1',
 'aw8_earlycache': 's4-p16-c2-storage2-aw8-early-cache-q1-v2',
 'full_earlycache': 's4-p16-c2-storage2-full-early-cache-q1-v2'}


def need(ok, label):
    if not ok:
        raise ValueError('ORIGINAL_STORAGE2_PROMOTION_' + label)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def ref(path):
    path = Path(path).resolve()
    need(path.is_relative_to(ROOT) and path.is_file(), 'CONTAINED_EVIDENCE')
    return dict(path=str(path.relative_to(ROOT)), sha256=sha(path.read_bytes()))


def native(identifier, required=True):
    evidence = ROOT / 'queue/evidence' / identifier
    gatepath = evidence / 'gate-receipt.json'
    if not gatepath.exists():
        need(not required, 'REQUIRED_NATIVE_GATE:' + identifier)
        return dict(id=identifier, status='PENDING_REQUIRED_GATE', gate_path=str(gatepath.relative_to(ROOT)))
    gate = read(gatepath)
    need(gate['status'] == 'PASS_expected_contracts', 'ACTUAL_NATIVE_PASS:' + identifier)
    donepath = ROOT / 'queue/done' / (identifier + '.json')
    done = read(donepath)
    output = evidence / 'attempt-0/collected/output/native'
    manifestpath, reportpath = output / 'approved-manifest.json', output / 'report.json'
    manifest, report = read(manifestpath), read(reportpath)
    need(sha(manifestpath.read_bytes()) == gate['manifest_sha256'] == report['manifest_sha256']
         and sha(reportpath.read_bytes()) == gate['report_sha256'], 'GATE_REPORT_MANIFEST_JOIN')
    need(not report.get('lint_fatal_classes') and not report.get('lint_unknown_classes'), 'NO_LINT_WAIVER')
    return dict(id=identifier, status=gate['status'], gate=ref(gatepath), manifest=ref(manifestpath), report=ref(reportpath),
        done=ref(donepath), collected_at_utc=done['result']['completed'], host=report['host'],
        archive_sha256=done['result']['archive_sha256'], model_threads=report.get('model_threads'),
        actual_worker_seconds=report['seconds'], steps=gate['steps'], source_pins=manifest['sources'],
        properties=done['result']['properties'], validation_role_only_not_adoption=True)


def assemble():
    from fpga.reference import stream27_c2_storage2_record_ledger_v1 as ledger
    bundlepath, manifestpath = DONOR / 'production-bundle.json', DONOR / 'manifest.json'
    bundle, manifest = read(bundlepath), read(manifestpath)
    need(sha(bundlepath.read_bytes()) == ledger.BUNDLE_PIN and sha(manifestpath.read_bytes()) == ledger.MANIFEST_PIN,
         'EXACT_ORIGINAL_CAPTURE')
    production = bundle['generated_sha256']
    need(len(production) == 53 and all(sha(bundle['files'][n].encode()) == pin == manifest['sources']['rtl/' + n]
         for n, pin in production.items()), 'PRODUCTION53_BYTE_JOIN')
    projectpath = FIT / 'evidence/project/manifest.json'
    project = read(projectpath)
    need(project['source_sha256'] == production and project['top'] == bundle['top']
         and project['core_parameters'] == manifest['build']['parameters'], 'PHYSICAL_ORIGINAL_SOURCE_JOIN')
    records = {name: native(identifier, required=name != 'full_earlycache') for name, identifier in NATIVE_IDS.items()}
    for key in ('full', 'pilot', 'long', 'full_contracts'):
        need(all(records[key]['source_pins']['rtl/' + n] == pin for n, pin in production.items()), 'NATIVE_PRODUCTION_JOIN:' + key)
    values = records['long']['steps'][0]['validation']['measurements']
    need(values['count_per_context'] == 1000 and values['interval'] == 8459 and values['reads'] == 262144
         and values['squares'] == 2000 and values['descriptors'] == 1998 and values['signed96']
         and values['independent_reference'] and values['model_threads'] == 1, 'OWN_LONG_EXACT_SCOPE')
    ledger.check_native()
    longledger = ledger.ledger((1000, 1000))
    need(values['warm_edges'] == longledger['warm_edges'] and values['done_edges'] == longledger['publication_edges']
         and values['joint_cycles'] == longledger['pair_completion_cycles'] + 65536, 'OWN_LONG_PUBLICATION_LEDGER')
    clocks = {}
    for version, period, closes in ((5, 16.150, True), (4, 16.148, False)):
        path = AUDIT_BASE / (FIT_ID + '-audit' + str(version)) / 'receipt.json'
        receipt = read(path)
        selected = receipt['timing']['selected']
        need(selected['period_ns'] == period and selected['timing_closes'] is closes and receipt['original_unchanged']
             and receipt['compiled_input_unchanged'] and receipt['fit_commands'] == 0, 'SAME_LAYOUT_CLOCK_BRACKET')
        corners = selected['corners']
        need(len(corners) == 4 and all(d['hold']['closes'] and d['mpw']['closes'] for d in corners.values()), 'MCMM_HOLD_MPW')
        clocks['pass' if closes else 'fail'] = dict(receipt=ref(path), archive=ref(path.parent / 'native-audit.tar.gz'),
            period_ns=period, closes=closes, qdb_inventory_sha256=receipt['qdb_inventory_sha256'],
            original_tree_sha256=receipt['original_tree_sha256'], original_invocation=receipt['original_invocation'],
            corners={c: {k: d[k] for k in ('setup', 'hold', 'mpw', 'recovery', 'removal', 'unconstrained')} for c, d in corners.items()},
            finite_setup_observations=selected['observed_setup_paths'], scope=receipt['limitation'])
    need(clocks['pass']['qdb_inventory_sha256'] == clocks['fail']['qdb_inventory_sha256'], 'EXACT_QDB_BRACKET')
    resourcespath = FIT / 'evidence/project/output_files/probe.fit.summary'
    placementpath = FIT / 'evidence/project/output_files/probe.fit.place.rpt'
    summary, placement = resourcespath.read_text(), placementpath.read_text()
    def number(pattern, text):
        hit = re.search(pattern, text)
        need(hit is not None, 'ACTUAL_RESOURCE_REPORT')
        return int(hit.group(1).replace(',', ''))
    resources = dict(alms_needed=number(r'Logic utilization \(in ALMs\) : ([\d,]+)', summary),
        alms_placed=number(r'ALMs used in final placement \[=a\+b\+c\+d\]\s*;\s*([\d,]+)', placement),
        labs=number(r'Total LABs:  partially or completely used\s*;\s*([\d,]+)', placement),
        labs_capacity=42720, total_registers=number(r'Total registers : (\d+)', summary),
        m20k=number(r'Total RAM Blocks : ([\d,]+)', summary), dsp=number(r'Total DSP Blocks : ([\d,]+)', summary),
        virtual_pins=number(r'Total virtual pins : ([\d,]+)', summary), stage='successful final routed fit',
        summary=ref(resourcespath), placement_report=ref(placementpath), fit_receipt=ref(FIT / 'receipt.json'),
        raw_reports_archive=ref(FIT / 'native-reports.tar.gz'))
    projection = ledger.sample('16.150')
    pair = Decimal(projection['conditional_pair_seconds'])
    previous = Decimal('178.632349')
    projection.update(audited_period_used=True, audited_period_receipt=clocks['pass']['receipt'],
        audited_period_requires_independent_review=True, throughput_improvement_percent=str((1 - pair / 2 / previous) * 100),
        previous_single_context_projection_seconds=str(previous),
        throughput_not_individual_latency=True, each_job_latency_seconds='approximately261.2',
        measured_full_sample_PRP=False, board_runtime_measured=False)
    pending = [name for name, row in records.items() if row['status'] != 'PASS_expected_contracts']
    return dict(schema='stream27-original-c2-storage2-promotion-evidence-v1',
        status='PENDING_REQUIRED_GATE' if pending else 'READY_FOR_FRESH_INDEPENDENT_REVIEW_NOT_ADOPTED',
        created_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), author='p16_mlab',
        original_production_only=True, production_modules=53, native_full_observer_modules=1,
        production_top=bundle['top'], production_bundle=ref(bundlepath), full_source_manifest=ref(manifestpath),
        production_source_pins=production, physical_project_manifest=ref(projectpath), physical_controls=project['control_sha256'],
        native=records, required_pending=pending, clock_bracket=clocks, routed_resources=resources,
        source_ledger=ref(ROOT / 'reference/stream27_c2_storage2_record_ledger_v1.py'),
        count2_ledger=ledger.ledger(), count1000_ledger=longledger, sample_projection=projection,
        cross_talk_scope=dict(full_normal='Each context-alone and joint bit-identical against independent full-N reference;393216 signed96 words, distinct bases/states/epochs, II1 full56 response owners.',
            aw8='Own original N256 counts3/14:1024signed96 words,256peer-live reads, waitingB/capture-during-copy/canonical-peer-arithmetic all actual.',
            own1000='Two independent uninterrupted1000-operation programs with1998actual ordered descriptors,1022double choices,262144signed96 words including65536peer-busy reads; exact2000launches and final publications.',
            faults='Global quarantine, not context-local recovery. Four actual full27 physical payload-key flips; full56 ordinal+65536 alias at capture origin after both FIRSTs; real external malformed tuples; seed/PW/last-read-E4 resets and both full-chain reference recovery; wrongword expected rc1.',
            limitations='Specified concrete simulation mutations and value/tag checks, not arbitrary corruption, formal proof, FPGA board or complete PRP.'),
        preserved_failures=[dict(id='s4-p16-c2-storage2-full-early-cache-q1-v1', scope='Lint missing original leaf used by F1/F2; immutable failure. v2 retains original leaf and adds F0 probe; production unchanged.'),
                            dict(id='s4-p16-c2-storage2-aw8-early-cache-q1-v1', scope='Original AW8 diagnostic closure failure retained; own AW8v2 qualified separately.')],
        scope_corrections=['Immutable full reset footer epoch_wrap=1 is an overbroad label: fullfault COUNT2/EPOCH_SEED0=65534 ends65535, so do not credit reset-wrap coverage from that footer. Actual full-N epoch wrap is checked by ORIGINAL own1000 ending C0epoch997/ordinal999; AW8counts3/14 is its separate wrap/reset companion. No frozen validator or native result is altered.'],
        exclusions=['combined', 'timing58', 'timing-order', 'what-if excluded-path STA', 'component clock inheritance'],
        independent_receipt=None, advisor_verification=None, promotion_allowed=False,
        limitations=['Internal compute-only scoped MCMM,1ps setup reserve/5ps hold reserve; no robust maximum-clock guarantee.',
                     'Board I/O and asynchronous reset recovery/removal remain outside timing claim; virtual pins/unconstrained external ports explicit.',
                     'Two-test amortized throughput projection; not measured full PRP, individual130.6s latency, board runtime, power or publication.'])


def emit(output):
    out = Path(output).resolve()
    need(out.is_relative_to(BASE) and not out.exists(), 'FRESH_PROMOTION_INDEX')
    value = assemble()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    return dict(status=value['status'], index=str(out), required_pending=value['required_pending'], promotion_allowed=False)
