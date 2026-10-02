"""N1 selector-only retained physical ledger and calibrated frontier.

No Quartus, QDB open, refit, remote command or numeric transform. Author replay
only; hierarchy ALMs are not a measured whole-core area or clock bound.
"""
import importlib.util
import json
import math
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_selector_retained', HERE / 'radix22_selector_native_replay_v1.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
h.need(h.digest(HERE / 'radix22_selector_native_replay_v1.py') == '9204518b977c181c78aafc3c3b018f291b3d93fcae0baa4d1ad0146ee6e4289b', 'pinned read-only helpers')
sys.path.insert(0, str(h.FPGA.parent))
PINS = (
    'aa3711da26a6ce08b29fe0b94fdd427003bc58d589a2cdb76851a5bfab28259d',
    '91d4b372adf0f948cf07677e2fdea7152295663ef7d2322a7f239ee30ed7a87d',
    '1c0456ca71b96423793a9862aa20f9635c2d43ef5705f05b6673900274dc5b15',
)


def cells(line):
    return [x.strip() for x in line.split(';')[1:-1]]


def scalar(value):
    match = re.fullmatch(r'([\d,]+(?:\.\d+)?)\s*(?:\(([\d,]+(?:\.\d+)?)\))?', value)
    h.need(match is not None, 'typed hierarchy resource scalar')
    outside = float(match[1].replace(',', ''))
    return outside, float(match[2].replace(',', '')) if match[2] else outside


def entity(text, name):
    headers = [cells(x) for x in text.splitlines() if x.startswith('; Compilation Hierarchy Node ;') and 'ALMs needed' in x]
    h.need(len(headers) == 1, 'one final fitter hierarchy header')
    header = headers[0]
    index = header.index('Full Hierarchy Name')
    rows = [cells(x) for x in text.splitlines() if x.startswith(';') and len(cells(x)) == len(header) and cells(x)[index] == name]
    h.need(len(rows) == 1, 'exact hierarchy entity, not absent/ambiguous attribution')
    row = dict(zip(header, rows[0]))
    return {key: dict(inclusive=scalar(row[label])[0], own=scalar(row[label])[1]) for key, label in {
        'needed_ALMs': 'ALMs needed [=A-B+C]', 'placed_ALMs': '[A] ALMs used in final placement',
        'recoverable_ALMs': '[B] Estimate of ALMs recoverable by dense packing',
        'unavailable_ALMs': '[C] Estimate of ALMs unavailable', 'ALUTs': 'Combinational ALUTs',
        'registers': 'Dedicated Logic Registers', 'M20Ks': 'M20Ks', 'virtual_pins': 'Virtual Pins',
    }.items()}


def number(text, label):
    rows = [cells(x) for x in text.splitlines() if x.startswith(';') and cells(x) and cells(x)[0] == label]
    h.need(rows, 'exact resource row present')
    values = {int(re.match(r'[\d,]+', row[1]).group().replace(',', '')) for row in rows}
    h.need(len(values) == 1, 'unambiguous resource row')
    return values.pop()


def timing(text, section):
    anchors = list(re.finditer(r'^; ' + re.escape(section) + r'\s*;\n', text, re.M))
    h.need(len(anchors) == 1, 'one aggregate timing section')
    lines = text[anchors[0].end():].splitlines()
    row = next(cells(x) for x in lines if x.startswith('; kernel_clk ;'))
    return dict(slack_ns=float(row[1]), TNS_ns=float(row[2]), failing_endpoints=int(row[3]), corner=row[-1])


def planning(network):
    h.need(len(network) == 3 and all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in network), 'three measured child areas')
    floor, reserve, limit = 310024.9, 4096, 320000
    local_delta = network[2] - network[0]
    whole = floor + 3 * local_delta + reserve
    canonical_to_local = network[1] - network[2]
    # Same measured residual carried to the existing 2-source proxy is a
    # conditional model, not measured area and not a physical lower bound.
    assumed_saving_per_field = (5184 - 2592) * 0.5
    measured_marginal_root_selector_ALM_per_muxbit = canonical_to_local / (37017 - 5184)
    return dict(measured_child_delta_local_minus_baseline=round(local_delta, 1),
                measured_child_saving_canonical_minus_local=round(canonical_to_local, 1),
                per_field_delta_limit=round((limit - floor - reserve) / 3, 1),
                three_source_whole_calibrated_heuristic=round(whole, 1),
                three_source_gate_PASS=whole <= limit, additional_whole_saving_needed=round(max(0, whole - limit), 1),
                additional_per_field_saving_needed=round(max(0, whole - limit) / 3, 1),
                two_source_same_residual_heuristic=round(whole - 3 * assumed_saving_per_field, 1),
                two_source_conditional_saving_per_field=assumed_saving_per_field,
                measured_marginal_root_selector_ALM_per_muxbit=measured_marginal_root_selector_ALM_per_muxbit,
                two_source_measured_marginal_heuristic=round(whole - 3 * 2592 * measured_marginal_root_selector_ALM_per_muxbit, 1),
                two_source_M20K_proxy=1539, two_source_area_measured=False,
                two_source_launch_register_pruning_only=162,
                next_new_component_prepared=False, next_fit_requested=False,
                decision='Measured_3_source_NO_GO_at_declared_320K_heuristic; 2_source_not_yet_justified_by_area_model',
                physical_whole_core_bound=False, architecture_RTL_GO=False)


def recalibrated_frontier(plan):
    model = h.load('reference/radix22_root_local_model_v1.py', '40165e879c1be3275f87a10c7ee63415328e7859e3303bfcef49e080cb75a4c6')
    residual = plan['three_source_whole_calibrated_heuristic'] - model.resources()['ALMs_needed_proxy']
    rows = []
    for cuts in range(128):
        groups = [[]]
        for i, high in enumerate(range(1, 16, 2)):
            groups[-1].append(high)
            if i < 7 and cuts & (1 << i):
                groups.append([])
        old = model.resources(tuple(tuple(g) for g in groups))
        area = round(old['ALMs_needed_proxy'] + residual, 1)
        rows.append(dict(partition=groups, conditional_ALMs=area, M20K_proxy=old['M20K_legal_rectangle_proxy'], DSP_proxy=old['DSP_needed_proxy'],
                         all_declared_heuristics_PASS=area <= 320000 and old['M20K_legal_rectangle_proxy'] <= 2300 and old['DSP_needed_proxy'] <= 1100))
    memory_safe = [r for r in rows if r['M20K_proxy'] <= 2300]
    return dict(partitions=128, transferred_same_residual_ALMs=residual, models_not_measurements=True,
                residual_not_a_packing_or_area_bound=True, passing_all_declared_heuristics=sum(r['all_declared_heuristics_PASS'] for r in rows),
                best_area_memory_safe=min(memory_safe, key=lambda r: (r['conditional_ALMs'], r['M20K_proxy'])),
                best_area_without_memory_gate=min(rows, key=lambda r: (r['conditional_ALMs'], r['M20K_proxy'])),
                next_component_prepared=False, next_fit_requested=False,
                reason='No existing partition clears calibrated320K/2300M20K/1100DSP model. Two-source alone lacks required saving; no unmeasured packing/ROM/control credit.')


def replay(mode):
    root = h.FPGA / f'queue/fit-r54-controller-v{7 if mode == 0 else 8}/terminal/n1-selector-mode{mode}'
    h.need(h.digest(root / 'receipt.json') == PINS[mode], 'external terminal receipt pin')
    receipt = h.read(root / 'receipt.json')
    evidence, project = root / 'evidence', root / 'evidence/project'
    raw = h.archive(root / 'native-reports.tar.gz')
    h.need(h.digest(root / 'native-reports.tar.gz') == receipt['archive']['sha256'] and (root / 'native-reports.tar.gz').stat().st_size == receipt['archive']['size'], 'archive pin')
    h.need(raw == {str(x.relative_to(evidence)): x.read_bytes() for x in evidence.rglob('*') if x.is_file()}, 'complete collected archive')
    inventory = h.read(evidence / 'collection/collection-inventory-v1.json')
    h.need(h.digest(evidence / 'collection/collection-inventory-v1.json') == receipt['inventory_sha256'], 'inventory pin')
    h.need(set(raw) == set(inventory['files']) | {'collection/collection-inventory-v1.json'}, 'all inventory members')
    h.need(inventory['count'] == len(inventory['files']) == 32 and sum(x['size'] for x in inventory['files'].values()) == inventory['bytes'], 'inventory totals')
    for name, item in inventory['files'].items():
        h.need(h.sha(raw[name]) == item['sha256'] and len(raw[name]) == item['size'], 'exact retained hash/size')
    manifest, context = h.read(project / 'manifest.json'), h.read(project / 'execution-context.json')
    request = h.read(evidence / 'request.json')
    prepared = h.FPGA / f'artifacts/radix22-selector-experiment-v1/physical-mode{mode}-workers6'
    h.need(h.digest(project / 'manifest.json') == h.digest(prepared / 'manifest.json') == context['manifest_sha256'] == request['project']['manifest_sha256'], 'unchanged prepared manifest')
    h.need(manifest['source_sha256'] == context['source_sha256'] == request['project']['source_sha256'] == {'radix22_selector_probe_v1.sv': h.SV}, 'single unchanged RTL source')
    h.need(h.digest(project / 'rtl/radix22_selector_probe_v1.sv') == h.SV, 'actual RTL identity')
    for name, pin in context['control_sha256'].items():
        h.need(pin == request['project']['control_sha256'][name] == h.digest(prepared / name), 'source-bound control')
        raw_control = (project / name).read_bytes()
        if name == 'probe.qsf':
            suffix = b'set_global_assignment -name LAST_QUARTUS_VERSION "26.1.0 Pro Edition"\n'
            h.need(raw_control.endswith(suffix) and h.sha(raw_control[:-len(suffix)]) == pin, 'only native Quartus metadata suffix')
        else:
            h.need(h.sha(raw_control) == pin, 'unchanged executed control')
    h.need(manifest['core_parameters'] == context['qsf_parameters'] == {'MODE': mode}
           and manifest['clock_period_ns'] == 10 and manifest['seed'] == 1 and manifest['compile_processors'] == 6, 'matched static MODE timing/seed/workers')
    h.need(h.digest(evidence / 'request.json') == receipt['source_request_sha256'], 'request pin')
    h.need((context['quartus_workers'], context['cpu_max'], context['memory_max'], context['swap_max'], context['timeout_seconds']) == (6, '600000 100000', str(20 << 30), '0', 21600), 'actual caps')
    h.need(context['affinity'] == list(range(6)) and context['physical_cores'] == [[0, c] for c in range(6)], 'same actual six physical cores')
    h.need(h.read(project / 'plain-final-source-guard.json') == dict(unchanged=True, drift=[], vendor_returncode=0, promotion_allowed=False), 'source guard')
    result = h.read(project / 'execution-result.json')
    h.need(result == receipt['native_result'] and result['quartus_returncode'] == result['summarize_returncode'] == 0 and result['context_sha256'] == h.digest(project / 'execution-context.json'), 'actual native result')
    proof = h.read(evidence / 'collection/native-journal-proof.json')
    h.need(proof == receipt['native_journal_proof'] and proof['terminal_proven'] and proof['invocation_id'] == receipt['invocation_id'], 'terminal proof')
    journal = [json.loads(line) for line in (evidence / 'collection/native-journal.jsonl').read_text().splitlines()]
    trusted = [x for x in journal if x.get('_PID') == '1' and x.get('UNIT') == receipt['unit'] and x.get('INVOCATION_ID') == receipt['invocation_id']]
    h.need(any(x.get('MESSAGE') == proof['manager_terminal_message'] for x in trusted) and all(x in trusted for x in proof['resource_journal']), 'actual trusted manager terminal/resource fields')
    database = h.read(project / 'database-inventory-final.json')
    h.need(len(database) == receipt['compiled_db_files'] == 194 and sum(x['size'] for x in database.values()) == receipt['compiled_db_bytes'] and not inventory['raw_qdb_included'], 'QDB inventory only, no local QDB rehash')
    output = project / 'output_files'
    fit, sta, syn = [(output / name).read_text() for name in ('probe.fit.rpt', 'probe.sta.rpt', 'probe.syn.rpt')]
    h.need('26.1.0 Build 110 03/26/2026 SC Pro Edition' in fit and '10AX115N4F40E3SG' in fit and re.search(r'; Fitter Status\s*; Successful', fit), 'native fit/tool/device')
    h.need(re.search(r'; kernel_clk ; Base ; 10.000\s*; 100.0 MHz ; 0.000 ; 5.000', sta), 'actual10ns clock')
    h.need(re.search(r'; Design Closure Summary\s*; Fail', sta) and re.search(r';   Unconstrained Paths\s*; Fail', sta), 'preserved non-signoff unconstrained closure')
    for corner in ('Slow 900mV 100C Model', 'Slow 900mV 0C Model', 'Fast 900mV 100C Model', 'Fast 900mV 0C Model'):
        h.need(corner in sta, 'four-corner report coverage')
    network, wrapper = entity(fit, 'network'), entity(fit, '|')
    h.need(network['registers']['inclusive'] == network['registers']['own'] == 0, 'combinational child; wrapper owns registers')
    synthesis_registers = number(syn, 'Dedicated logic registers')
    expected_pruned = (17300, 24048, 19830)[mode]
    h.need(synthesis_registers == expected_pruned, 'static payload/control pruning matches declared sources and live outputs')
    timing_rows = {name: timing(sta, title) for name, title in [('setup', 'Setup Summary'), ('hold', 'Hold Summary'), ('pulse', 'Minimum Pulse Width Summary')]}
    summary = h.read(evidence / f'root/n1-selector-mode{mode}-aws-fitq-v1-summary.json')[f'n1-selector-mode{mode}-aws-fitq-v1']
    totals = {name: number(fit, label) for name, label in {'needed_ALMs': 'ALMs needed [=A-B+C]', 'placed_ALMs': '[A] ALMs used in final placement [=a+b+c+d]', 'registers': 'Total registers', 'M20Ks': 'Total RAM Blocks', 'DSPs': 'Total DSP Blocks', 'route_through_ALUTs': 'Combinational ALUT usage for route-throughs'}.items()}
    h.need(summary['manifest'] == manifest and summary['fit_success'] and summary['internal_timing_met'] and summary['setup_slack_ns'] == timing_rows['setup']['slack_ns'], 'summary raw timing closure')
    for key, resource in [('alms_needed', 'needed_ALMs'), ('alms_placed', 'placed_ALMs'), ('registers', 'registers'), ('ram_blocks', 'M20Ks'), ('dsp_blocks', 'DSPs')]:
        h.need(summary[key] == totals[resource], 'summary raw resources')
    h.need(all(x['slack_ns'] > 0 and x['TNS_ns'] == x['failing_endpoints'] == 0 for x in timing_rows.values()), 'scoped internal10ns timing pass')
    return dict(mode=mode, receipt_sha256=PINS[mode], archive_sha256=receipt['archive']['sha256'], inventory_pins=32, archive_members=len(raw),
                manifest_sha256=context['manifest_sha256'], invocation=receipt['invocation_id'], source=h.SV,
                fit_report_sha256=h.digest(output / 'probe.fit.rpt'), sta_report_sha256=h.digest(output / 'probe.sta.rpt'),
                synthesis_report_sha256=h.digest(output / 'probe.syn.rpt'), network=network, wrapper_entity=wrapper, top_totals=totals,
                synthesis_registers=synthesis_registers, registers_pruned_from_declared24055=24055 - synthesis_registers,
                postfit_minus_synthesis_registers=totals['registers'] - synthesis_registers, timing=timing_rows,
                reported_Fmax_NOT_usable_whole_clock_MHz=summary['fmax_mhz'], design_closure='Fail_unconstrained_virtual_IO',
                manager_elapsed_seconds=proof['manager_elapsed_seconds'], peak_bytes=int(proof['resource_journal'][0]['MEMORY_PEAK']),
                CPU_seconds=int(proof['resource_journal'][0]['CPU_USAGE_NSEC']) / 1e9,
                QDB_inventory_only_files=194, QDB_inventory_only_bytes=receipt['compiled_db_bytes'], no_QDB_local_rehash=True)


def main():
    runs = [replay(mode) for mode in range(3)]
    plan = planning([x['network']['needed_ALMs']['inclusive'] for x in runs])
    return dict(schema='n1-selector-owner-physical-replay-v1', status='PASS_retained_selector_evidence_measured_3_source_heuristic_NO_GO',
                independent=False, vendor_or_remote_execution=False, runs=runs,
                planning=plan, next_smallest_existing_frontier=recalibrated_frontier(plan),
                caveat='Hierarchy fractional attribution is not exactly additive to rounded top totals; do not sum root-inclusive and child counts. No root ROM/address supply, field arithmetic, delay registers or whole core.',
                architecture_RTL_GO=False, promotion_allowed=False)


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
