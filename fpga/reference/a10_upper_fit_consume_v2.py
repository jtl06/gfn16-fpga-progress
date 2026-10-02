"""Read-only, hold-aware consumption of the immutable upper-sum field fit.

Native tool exit zero is not timing closure. No remote action or fitted-source
mutation; all arithmetic/control sources and original physical failures remain.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

from fpga.reference import a10_upper_sum_generate_v2 as gen
from fpga.reference import a10_point_fit_consume_v3 as point

ROOT = gen.ROOT
DOSSIER = ROOT/'queue/fit-r54-controller-v9/terminal/a10-upper-sum-sizing'
RECEIPT_SHA = '1eec3912a8f84f18166a78f3cdbe40ae729406025bdfbacb859c83ec82cde3be'
STA_SHA = '2368c2e4cc7e1117a0ec061bb375e1ab5bdb5d9804f82e5997bdf2acf8282d51'
MANIFEST_SHA = '711fd3a733e90bf5ab1a9c12175ac9d757e76bfe75e854a86184fcd36cf95787'
PARSER_SHA = 'a06c90d1b00a732065e016fb779bc60cd2270f27b283489bf07c69ce8665085a'
OUTPUT = ROOT/'results/throughput-20260929/a10-upper-field-fit-consumption-v2'
PREPARED = ROOT/'results/throughput-20260929/a10-upper-sum-field-probe-v2a/project-workers6'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parser():
    path = ROOT/'tools/plain_fit_path_ledger_v2.py'
    gen.need(sha(path) == PARSER_SHA, 'A10_UPPER_FIT_PARSER_PIN')
    spec = importlib.util.spec_from_file_location('_a10_upper_fit_ledger', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def closed_archive(dossier, receipt):
    evidence = dossier/'evidence'
    inventory_path = evidence/'collection/collection-inventory-v1.json'
    gen.need(sha(inventory_path) == receipt['inventory_sha256'] and
             sha(dossier/'native-reports.tar.gz') == receipt['archive']['sha256'],
             'A10_UPPER_FIT_ARCHIVE_INVENTORY')
    inventory = json.loads(inventory_path.read_text())
    for name, record in inventory['files'].items():
        gen.need(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts,
                 'A10_UPPER_FIT_INVENTORY_PATH')
        path = evidence/name
        gen.need(path.is_file() and not path.is_symlink() and path.stat().st_size == record['size'] and
                 sha(path) == record['sha256'], 'A10_UPPER_FIT_CLOSED_FILE '+name)
    archived = {}
    with tarfile.open(dossier/'native-reports.tar.gz', 'r:gz') as archive:
        for member in archive:
            gen.need(member.isfile() and not member.issparse() and member.name not in archived and
                     not PurePosixPath(member.name).is_absolute() and '..' not in PurePosixPath(member.name).parts,
                     'A10_UPPER_FIT_REGULAR_ARCHIVE')
            archived[member.name] = hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    expected = {name: record['sha256'] for name, record in inventory['files'].items()}
    expected['collection/collection-inventory-v1.json'] = receipt['inventory_sha256']
    gen.need(archived == expected and inventory['count'] == len(inventory['files']) == 40,
             'A10_UPPER_FIT_EXACT_41_MEMBER_CLOSURE')
    return inventory


def hold_evidence(sta, ledger, fit_report, tables):
    """Reject reinterpretation of these samples as external or period-limited."""
    counts = Counter()
    for row in ledger['hold']['paths']:
        gen.need(row['relationship_ns'] == 0 and row['native_sdc_exception'] == 'No SDC Exception on Path' and
                 row['native_corner'] == 'Slow 900mV 0C Model' and row['slack_ns'] < 0,
                 'A10_UPPER_INTERNAL_HOLD_RELATIONSHIP')
        source, destination = row['source'], row['destination']
        if re.fullmatch(r'child\|child\|row_tag\[\d+\]\[\d+\]\[\d+\]', source):
            match = re.fullmatch(r'child\|child\|row_tag\[(\d+)\]\[(\d+)\]\[(\d+)\]', source)
            expected = 'child|child|row_tag[%d][%s][%s]' % (int(match[1])+1, match[2], match[3])
            kind = 'row_tag'
        else:
            match = re.fullmatch(r'(child\|child\|arithmetic\[\d+\]\.butterfly\|shared_lower\|)(prefix_pipe|dif_pipe)\[(\d+)\](\[\d+\])?', source)
            gen.need(match is not None, 'A10_UPPER_HOLD_NOT_INTERNAL_PIPELINE')
            expected = match[1]+match[2]+'[%d]' % (int(match[3])+1)+(match[4] or '')
            kind = match[2]
        gen.need(destination == expected and row['native_logic_levels'] == 0 and
                 any(node['type'] == 'uTco' for node in row['observed_data_cone']) and
                 any(item['type'] == 'uTh' for item in row['native_required_constraints']),
                 'A10_UPPER_HOLD_REAL_ADJACENT_FF')
        counts[kind] += 1
    gen.need(counts == dict(row_tag=4, prefix_pipe=5, dif_pipe=1), 'A10_UPPER_EXACT_HOLD_CLASSES')
    sections = re.findall(r'^Path #1: Hold slack is [\s\S]+?(?=^Path #2: Hold slack is )', sta, re.M)
    gen.need(len(sections) == 1, 'A10_UPPER_HOLD_ACTUAL_DETAIL_NOT_TOC')
    body = sections[0]
    properties = dict(tables.table(body, 'Path Summary', ['Property', 'Value']))
    arrival = tables.table(body, 'Data Arrival Path', ['Total', 'Incr', 'RF', 'Type', 'Fanout', 'Location', 'HS/LP', 'Element'])
    required = tables.table(body, 'Data Required Path', ['Total', 'Incr', 'RF', 'Type', 'Fanout', 'Location', 'HS/LP', 'Element'])
    def value(rows, element, column=0):
        matches = [float(row[column]) for row in rows if row[-1] == element]
        gen.need(len(matches) == 1, 'A10_UPPER_HOLD_SINGLE_NATIVE_VALUE '+element)
        return matches[0]
    launch = value(arrival, 'clock path')
    latch = value(required, 'clock path')
    arrive = float(properties['Data Arrival Time']); needed = float(properties['Data Required Time'])
    worst = ledger['hold']['paths'][0]
    gen.need(round(arrive-launch, 3) == worst['data_delay_ns'] and
             round(latch-launch, 3) == worst['clock_skew_ns'] and
             round(arrive-needed, 3) == worst['slack_ns'], 'A10_UPPER_HOLD_RAW_EQUATION')
    summary = tables.table(fit_report, 'Estimated Delay Added for Hold Timing Summary',
                           ['Source Clock(s)', 'Destination Clock(s)', 'Delay Added in ns'])
    details = tables.table(fit_report, 'Estimated Delay Added for Hold Timing Details',
                           ['Source Register', 'Destination Register', 'Delay Added in ns'])
    setting = re.findall(r'^; Optimize Hold Timing\s*;\s*([^;]+);\s*([^;]+);\s*$', fit_report, re.M)
    gen.need(len(setting) == 1 and [x.strip() for x in setting[0]] == ['All Paths', 'All Paths'],
             'A10_UPPER_HOLD_OPTIMIZATION_ALREADY_ALL_PATHS')
    matching = [float(row[2]) for row in details if row[:2] == [worst['source'], worst['destination']]]
    gen.need(summary == [['kernel_clk', 'kernel_clk', '2032.4']] and matching == [.355],
             'A10_UPPER_NATIVE_HOLD_REPAIR_ESTIMATES')
    return dict(classification='REAL_INTERNAL_SAME_CLOCK_FF_MIN_DELAY_FAILURE', classes=dict(counts),
        worst_corner=worst['native_corner'], launch_clock_ns=launch, latch_clock_after_pessimism_ns=latch,
        removed_pessimism_ns=value(required, 'clock pessimism removed', 1),
        clock_uncertainty_ns=value(required, 'clock uncertainty', 1),
        arrival_ns=arrive, required_ns=needed, slack_ns=worst['slack_ns'],
        hold_requirement_ns=next(row['incremental_ns'] for row in worst['native_required_constraints'] if row['type'] == 'uTh'),
        period_reduction_alone_repairs_hold=False, optimize_hold_timing='All Paths already effective',
        native_estimated_added_delay_summary_ns=2032.4, worst_pair_estimated_added_delay_ns=.355,
        repair_estimate_limitation='Fitter estimates are not additional STA delay to add to the retained .518ns path; different native tables/scopes.',
        changed_upper_launch_register_is_endpoint=False)


def consume():
    gen.measured_guard()
    gen.need(sha(DOSSIER/'receipt.json') == RECEIPT_SHA, 'A10_UPPER_FIT_TERMINAL_PIN')
    receipt = json.loads((DOSSIER/'receipt.json').read_text())
    gen.need(receipt['native_job_succeeded'] and receipt['collection_completed'] and receipt['terminal_proven'] and
             not receipt['findings'] and receipt['invocation_id'] == '35ed3abe745c4facb932be7d305c8819' and
             receipt['native_result']['quartus_returncode'] == receipt['native_result']['summarize_returncode'] == 0,
             'A10_UPPER_FIT_ACTUAL_NATIVE_TERMINAL_NOT_TIMING_PASS')
    inventory = closed_archive(DOSSIER, receipt)
    project = DOSSIER/'evidence/project'
    gen.need(sha(project/'manifest.json') == sha(PREPARED/'manifest.json') == MANIFEST_SHA and
             sha(project/'output_files/probe.sta.rpt') == STA_SHA, 'A10_UPPER_EXACT_PROJECT_STA')
    m = json.loads((project/'manifest.json').read_text()); context = json.loads((project/'execution-context.json').read_text())
    gen.need(sha(project/'manifest.json') == context['manifest_sha256'] and context['source_sha256'] == m['source_sha256'],
             'A10_UPPER_NATIVE_CONTEXT_SOURCE')
    for name, pin in m['source_sha256'].items():
        gen.need(sha(project/'rtl'/name) == sha(PREPARED/'rtl'/name) == pin, 'A10_UPPER_ALL_NINE_NATIVE_RTL_PINS')
    for name in ('probe.sdc', 'probe.qpf', 'run.tcl'):
        gen.need(sha(project/name) == sha(PREPARED/name) == m['control_sha256'][name] == context['control_sha256'][name],
                 'A10_UPPER_UNCHANGED_CONTROL '+name)
    gen.need((project/'probe.qsf').read_text() == (PREPARED/'probe.qsf').read_text()+
             'set_global_assignment -name LAST_QUARTUS_VERSION "26.1.0 Pro Edition"\n' and
             sha(PREPARED/'probe.qsf') == m['control_sha256']['probe.qsf'], 'A10_UPPER_ONLY_VENDOR_VERSION_APPEND')
    gen.need((project/'rtl'/Path(gen.TARGET).name).read_text() == gen.cell_source() and
             (project/'rtl'/Path(gen.ENGINE).name).read_text() == gen.engine_source(), 'A10_UPPER_LITERAL_SOURCE_DELTA')
    shared = parser(); ledger = shared.collect(DOSSIER, RECEIPT_SHA)
    saved = json.loads((OUTPUT/'path-ledger-v2.json').read_text())
    saved.pop('generated_at_utc'); ledger.pop('generated_at_utc')
    gen.need(saved == ledger, 'A10_UPPER_SAVED_PATH_LEDGER_REPLAY')
    sta = (project/'output_files/probe.sta.rpt').read_text()
    fit_report = (project/'output_files/probe.fit.rpt').read_text()
    hold = hold_evidence(sta, ledger, fit_report, shared.v1)
    summary = (project/'output_files/probe.fit.summary').read_text()
    registers = int(re.findall(r'^Total registers : (\d+)$', summary, re.M)[0])
    resources = ledger['native_resources']
    fields = dict(needed_ALM=resources['needed_alm'], raw_placed_ALM=resources['raw_placed_alm'],
        LAB=resources['labs'], final_registers=registers, place_registers=resources['registers'],
        M20K=resources['m20k'], DSP=resources['needed_dsp'],
        RAM_bits=int(re.findall(r'^Total block memory bits : ([\d,]+) /', summary, re.M)[0].replace(',', '')))
    parent = point.consume()
    setup = ledger['setup']['paths']; setup_counts = Counter()
    gen.need(all('.data_ram|' in row['destination'] and row['native_sdc_exception'] == 'No SDC Exception on Path'
                 for row in setup), 'A10_UPPER_SETUP_REAL_RAM_WRITE_DESTINATIONS')
    gen.need(any('bf_write_option' in row['element'] for row in setup[0]['observed_data_cone']) and
             any('|data_w[' in row['element'] for row in setup[0]['observed_data_cone']), 'A10_UPPER_MEASURED_WRITEBACK_CONE')
    for row in setup:
        source = row['source']
        if '|shared_lower|y' in source: kind = 'butterfly_data'
        elif source.startswith('launch_size_log2_q['): kind = 'registered_runtime_size'
        elif source.startswith('launch_vector_addr_q['): kind = 'registered_vector_address'
        elif source.startswith('child|child|orientation_pipe['): kind = 'orientation_pipeline'
        else: raise ValueError('A10_UPPER_UNCLASSIFIED_SETUP_SOURCE')
        setup_counts[kind] += 1
    gen.need(setup_counts == dict(butterfly_data=3, registered_runtime_size=5, orientation_pipeline=1,
                                 registered_vector_address=1), 'A10_UPPER_EXACT_SETUP_CLASSES')
    slacks = dict(setup=-1.017, hold=-.140, minimum_pulse_width=3.352)
    timing_summary = (project/'output_files/probe.sta.summary').read_text()
    for kind, value in (('Setup', slacks['setup']), ('Hold', slacks['hold']), ('Minimum Pulse Width', slacks['minimum_pulse_width'])):
        gen.need(re.search(r'Type\s*: '+kind+r" 'kernel_clk'\nSlack : "+format(value, '.3f')+r'\n', timing_summary),
                 'A10_UPPER_NATIVE_SUMMARY_SLACK '+kind)
    return dict(schema='a10-upper-fit-consumption-v2', scope='matched_one_field_component_only',
        status='SOURCE_BOUND_NATIVE_COMPLETE_SETUP_AND_HOLD_FAIL', native_receipt_sha256=RECEIPT_SHA,
        raw_archive_sha256=receipt['archive']['sha256'], inventory_sha256=receipt['inventory_sha256'],
        raw_STA_sha256=STA_SHA, source_manifest_sha256=MANIFEST_SHA, invocation=receipt['invocation_id'],
        source_files=len(m['source_sha256']), collected_files=inventory['count'], archived_regular_files=41,
        native_manager=receipt['native_journal_proof'], native_tool_context=context,
        target_period_ns=8, seed=1, slacks=slacks, parent_slacks=parent['slacks'],
        slack_delta_ns={key:round(value-parent['slacks'][key], 3) for key,value in slacks.items()},
        resources=fields, matched_resource_delta={key:value-parent['resources'][key] for key,value in fields.items()},
        worst_setup=setup[0], worst_hold=ledger['hold']['paths'][0], hold_diagnosis=hold,
        setup_source_counts=dict(setup_counts),
        setup_cone='Registered butterfly/engine/wrapper control -> writeback selection/mux/routing -> RAM write input; worst IC8.278ns/91%,3logic levels.',
        source_cycle_delta=gen.ledger()['engine_cycle_delta'], accepted_to_output_edges=5, II=1,
        reported_Fmax_MHz=110.9, audited_clock=False, whole_core_clock_claim=False, promotion_allowed=False,
        QDB_local=False, QDB_scope='Native final225file/472854371byte DB inventory retained; private DB not locally copied/replayed.',
        next='Consume separately native-qualified upper WHOLE fit before choosing writeback RTL: component runtime-size/vector boundaries may prune in whole. If writeback persists, isolate bank-local registered write bundle with full valid/address/data/ownership/drain ledger and native gates; preserve external block E0/E1. Resolve real hold via physical min-delay/clock-routing closure, not lower MHz or false paths.',
        limitation='Finite MCMM top10 samples, not exhaustive path coverage. Reported Fmax does not include a hold repair. Same8ns/seed1/worker6/libs/registered-shell recipe; placement changes. Needed/Place/final counts differ; no blanket area or causal host-runtime claim. Virtual I/O and reset-release excluded; wrapper-native and whole physical clocks remain separate.')


if __name__ == '__main__':
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument('--output', type=Path, required=True)
    result = consume(); destination = args.parse_args().output
    with destination.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps(dict(status=result['status'], slacks=result['slacks'], resources=result['resources'],
                         matched_resource_delta=result['matched_resource_delta']), indent=2))
