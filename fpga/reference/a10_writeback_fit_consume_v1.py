"""Read-only F3 sizing consumption: source closure, MCMM cone and cost ledger.

AWS six-worker upper parent versus F16 four-worker F3 is not a perfect physical
comparison. Native fit exit zero is not 8ns closure or a whole-core clock.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
from fpga.reference import a10_upper_fit_consume_v2 as upper
from fpga.reference import a10_writeback_field_probe_v1 as prep

ROOT = prep.ROOT
DOSSIER = ROOT/'queue/fit-r54-controller-field2h-v12/terminal/a10-writeback-sizing'
RECEIPT_SHA = 'ee2f6e992263825126cd8caf6fe1fc9f93ca4a3f07fa35a535d5a5b126bde7b7'
STA_SHA = 'b01ddd7014cb3b4d7343b3f8a5f1cde6761969dba65c9debdfb1a170ea891644'
MANIFEST_SHA = 'b25f6854220d5e0335c8c0cb64c227fa02206a23b94d78c5a34266c5a969766c'
PREPARED = ROOT/'results/throughput-20260929/a10-writeback-field-probe-v1/project-workers4'
OUTPUT = ROOT/'results/throughput-20260929/a10-writeback-field-fit-consumption-v1'
need = prep.candidate.gen.upper.need
sha = upper.sha


def cones(ledger):
    setup = ledger['setup']['paths']; hold = ledger['hold']['paths']
    need(len(setup) == len(hold) == 10, 'A10_F3_FIT_FINITE_10_SAMPLES')
    for row in setup:
        need(re.fullmatch(r'launch_size_log2_q\[[13]\](~DUPLICATE)?', row['source']) and
             '.data_ram|' in row['destination'] and row['relationship_ns'] == 8 and
             row['native_sdc_exception'] == 'No SDC Exception on Path' and
             row['native_corner'] == 'Slow 900mV 100C Model', 'A10_F3_FIT_REAL_RUNTIME_SIZE_TO_RAM')
    worst = setup[0]; elements = [item['element'] for item in worst['observed_data_cone']]
    need(any('LessThan_6' in x for x in elements) and any('vector_write_route' in x for x in elements) and
         any('|data_w[' in x for x in elements) and any('.ram_write_data[' in x for x in elements) and
         any('|portadatain[' in x for x in elements), 'A10_F3_FIT_ACTUAL_IDLE_WRITE_PAYLOAD_CONE')
    counts = Counter()
    for row in hold:
        need(row['relationship_ns'] == 0 and row['slack_ns'] == .018 and
             row['native_sdc_exception'] == 'No SDC Exception on Path' and
             row['native_corner'] == 'Fast 900mV 0C Model' and row['native_logic_levels'] == 0,
             'A10_F3_FIT_INTERNAL_MIN_DELAY')
        tag = re.fullmatch(r'child\|child\|row_tag\[(\d+)\]\[(\d+)\]\[(\d+)\]', row['source'])
        prefix = re.fullmatch(r'(child\|child\|arithmetic\[\d+\]\.butterfly\|shared_lower\|prefix_pipe)\[(\d+)\](\[\d+\])', row['source'])
        if tag:
            expected = 'child|child|row_tag[%d][%s][%s]' % (int(tag[1])+1,tag[2],tag[3]); counts['row_tag'] += 1
        else:
            need(prefix is not None, 'A10_F3_FIT_HOLD_REAL_PIPELINE')
            expected = prefix[1]+'[%d]' % (int(prefix[2])+1)+prefix[3]; counts['prefix_pipe'] += 1
        need(row['destination'] == expected, 'A10_F3_FIT_HOLD_ADJACENT_STAGE')
    need(counts == dict(row_tag=8,prefix_pipe=2), 'A10_F3_FIT_EXACT_HOLD_CLASSES')
    return dict(setup_class='RUNTIME_HOST_SIZE_VECTOR_ROUTING_TO_IDLE_RAM_WRITE_DATA', hold_classes=dict(counts),
                no_butterfly_output_in_retained_setup_top10=True)


def hold_equation(sta, ledger, tables):
    sections = re.findall(r'^Path #1: Hold slack is [\s\S]+?(?=^Path #2: Hold slack is )', sta, re.M)
    need(len(sections) == 1, 'A10_F3_FIT_NATIVE_HOLD_DETAIL')
    props = dict(tables.table(sections[0], 'Path Summary', ['Property','Value']))
    headers = ['Total','Incr','RF','Type','Fanout','Location','HS/LP','Element']
    arrival = tables.table(sections[0], 'Data Arrival Path', headers)
    required = tables.table(sections[0], 'Data Required Path', headers)
    def value(rows, element, column=0):
        matches = [float(row[column]) for row in rows if row[-1] == element]
        need(len(matches) == 1, 'A10_F3_FIT_NATIVE_HOLD_SINGLE_VALUE'); return matches[0]
    launch = value(arrival,'clock path'); latch = value(required,'clock path')
    a = float(props['Data Arrival Time']); r = float(props['Data Required Time']); worst = ledger['hold']['paths'][0]
    need(round(a-r,3) == worst['slack_ns'] and round(a-launch,3) == worst['data_delay_ns'] and
         round(latch-launch,3) == worst['clock_skew_ns'], 'A10_F3_FIT_HOLD_RAW_EQUATION')
    return dict(launch_clock_ns=launch,latch_clock_after_pessimism_ns=latch,
        removed_pessimism_ns=value(required,'clock pessimism removed',1),arrival_ns=a,required_ns=r,
        slack_ns=worst['slack_ns'],data_delay_ns=worst['data_delay_ns'],
        hold_requirement_ns=worst['native_required_constraints'][0]['incremental_ns'],
        missing_IC_statistic_is_not_measured_zero=worst['native_data_statistics']['IC'] is None)


def consume():
    prep.candidate.verify()
    need(sha(DOSSIER/'receipt.json') == RECEIPT_SHA, 'A10_F3_FIT_ACTUAL_TERMINAL_PIN')
    receipt = json.loads((DOSSIER/'receipt.json').read_text())
    need(receipt['native_job_succeeded'] and receipt['collection_completed'] and receipt['terminal_proven'] and
         not receipt['findings'] and receipt['invocation_id'] == '658876b5b0a142fcbfd778b8b5057557' and
         receipt['native_result']['quartus_returncode'] == receipt['native_result']['summarize_returncode'] == 0,
         'A10_F3_FIT_NATIVE_TERMINAL_NOT_TIMING_PASS')
    inventory = upper.closed_archive(DOSSIER,receipt); project = DOSSIER/'evidence/project'
    need(sha(project/'manifest.json') == sha(PREPARED/'manifest.json') == MANIFEST_SHA and
         sha(project/'output_files/probe.sta.rpt') == STA_SHA, 'A10_F3_FIT_PROJECT_RAW_STA')
    m = json.loads((project/'manifest.json').read_text()); context = json.loads((project/'execution-context.json').read_text())
    need(sha(project/'execution-context.json') == receipt['native_result']['context_sha256'] and
         context['manifest_sha256'] == MANIFEST_SHA and context['source_sha256'] == m['source_sha256'],
         'A10_F3_FIT_NATIVE_CONTEXT')
    files,_ = prep.source_inputs()
    need(set(files) == set(m['source_sha256']) and len(files) == 9, 'A10_F3_FIT_EXACT_COMPILED_NINE')
    for name,raw in files.items():
        need((project/'rtl'/name).read_bytes() == (PREPARED/'rtl'/name).read_bytes() == raw and
             sha(project/'rtl'/name) == m['source_sha256'][name], 'A10_F3_FIT_EXACT_NATIVE_RTL '+name)
    for name in ('probe.sdc','probe.qpf','run.tcl'):
        need(sha(project/name) == sha(PREPARED/name) == m['control_sha256'][name] == context['control_sha256'][name],
             'A10_F3_FIT_EXACT_CONTROL '+name)
    need((project/'probe.qsf').read_text() == (PREPARED/'probe.qsf').read_text()+
         'set_global_assignment -name LAST_QUARTUS_VERSION "26.1.0 Pro Edition"\n' and
         sha(PREPARED/'probe.qsf') == m['control_sha256']['probe.qsf'], 'A10_F3_FIT_ONLY_VENDOR_APPEND')
    need(context['quartus_workers'] == m['compile_processors'] == 4 and context['timeout_seconds'] == 7200 and
         context['cpu_max'] == '400000 100000' and context['memory_max'] == str(24*(1<<30)) and
         context['swap_max'] == '0', 'A10_F3_FIT_ACTUAL_FIELD2H_F16_CAPS')
    shared = upper.parser(); ledger = shared.collect(DOSSIER,RECEIPT_SHA)
    saved = json.loads((OUTPUT/'path-ledger-v2.json').read_text())
    saved.pop('generated_at_utc'); ledger.pop('generated_at_utc')
    need(saved == ledger, 'A10_F3_FIT_SAVED_LEDGER_REPLAY')
    classification = cones(ledger); sta = (project/'output_files/probe.sta.rpt').read_text()
    hold = hold_equation(sta,ledger,shared.v1)
    fit_report = (project/'output_files/probe.fit.rpt').read_text()
    need(re.search(r'^; Optimize Hold Timing\s*;\s*All Paths\s*;\s*All Paths\s*;',fit_report,re.M),
         'A10_F3_FIT_HOLD_ALL_PATHS')
    summary = (project/'output_files/probe.fit.summary').read_text(); res = ledger['native_resources']
    resources = dict(needed_ALM=res['needed_alm'],raw_placed_ALM=res['raw_placed_alm'],LAB=res['labs'],
        final_registers=int(re.findall(r'^Total registers : (\d+)$',summary,re.M)[0]),place_registers=res['registers'],
        M20K=res['m20k'],DSP=res['needed_dsp'],
        RAM_bits=int(re.findall(r'^Total block memory bits : ([\d,]+) /',summary,re.M)[0].replace(',','')))
    slacks = dict(setup=-.743,hold=.018,minimum_pulse_width=3.350)
    timing = (project/'output_files/probe.sta.summary').read_text()
    for kind,value in (('Setup',slacks['setup']),('Hold',slacks['hold']),('Minimum Pulse Width',slacks['minimum_pulse_width'])):
        need(re.search(r'Type\s*: '+kind+r" 'kernel_clk'\nSlack : "+format(value,'.3f')+r'\n',timing),
             'A10_F3_FIT_EXACT_MCMM_SUMMARY '+kind)
    parent = upper.consume()
    seq = ROOT/'rtl/kernel/genefer_anext_upper_ntt_sequencer_v1.sv'
    need(sha(seq) == '6da1f271db2a6cd820d48e9a68fb12b2401dfe4384d91c17f9964fede8b7b295' and
         '.vector_load_we(1\'b0),.vector_read_en(1\'b0)' in seq.read_text() and
         '.size_log2(5\'(AW))' in seq.read_text(), 'A10_F3_FIT_ACTUAL_WHOLE_UNUSED_VECTOR_ABI')
    return dict(schema='a10-writeback-fit-consumption-v1',scope='one_field_component_only',
        status='SOURCE_BOUND_NATIVE_COMPLETE_SETUP_FAIL_HOLD_PASS',native_receipt_sha256=RECEIPT_SHA,
        raw_archive_sha256=receipt['archive']['sha256'],inventory_sha256=receipt['inventory_sha256'],raw_STA_sha256=STA_SHA,
        source_manifest_sha256=MANIFEST_SHA,invocation=receipt['invocation_id'],source_files=9,collected_files=inventory['count'],
        archived_regular_files=41,native_manager=receipt['native_journal_proof'],native_tool_context=context,
        target_period_ns=8,seed=1,slacks=slacks,setup_TNS_ns=-140.731,
        parent_slacks=parent['slacks'],slack_delta_ns={k:round(v-parent['slacks'][k],3) for k,v in slacks.items()},
        resources=resources,resource_delta={k:v-parent['resources'][k] for k,v in resources.items()},
        parent_manifest_sha256=parent['source_manifest_sha256'],parent_host='AWS M8azn six workers',candidate_host='Azure F16 four workers',
        comparison_is_perfectly_host_worker_matched=False,hold_repair_causally_proven=False,
        classifications=classification,worst_setup=ledger['setup']['paths'][0],worst_hold=ledger['hold']['paths'][0],hold_equation=hold,
        component_native_transform_cycles=8352,component_native_point_cycles=1033,component_BF_k_plus=5,
        component_II=1,whole_NTT_delta_cycles=33,whole_integration_owned_elsewhere=True,
        reported_Fmax_MHz=114.38,audited_clock=False,whole_core_clock_claim=False,promotion_allowed=False,QDB_local=False,
        native_DB_inventory=dict(files=receipt['compiled_db_files'],bytes=receipt['compiled_db_bytes']),
        next='Do not chase retained runtime-vector probe ABI for whole A-next: actual sequencer ties it off. Preserve F3 whole native/fit as separate evidence; evaluate material +7051 needed ALM cost there. Current measured whole upper bottleneck is host cancel-to-payload/rangecheck/RAM acceptance and asynchronous recovery; isolate payload intent/latekill first, leaving recovery explicitly open.',
        limitation='Finite native MCMM top10, not exhaustive graph. Target8ns setup fails, reported Fmax is not admitted. Positive field hold is placement-specific and cannot erase upper parent hold failure or prove whole hold/reset-release. AWS6→F16four context confounds causal runtime/area/timing attribution. Needed/placed/Place-register/final-register scopes stay separate; no x3 area extrapolation.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(); result = consume()
    with args.output.open('x') as stream:
        json.dump(result,stream,indent=2,allow_nan=False); stream.write('\n')
    print(json.dumps({k:result[k] for k in ('status','slacks','resources','resource_delta','classifications')},indent=2))
