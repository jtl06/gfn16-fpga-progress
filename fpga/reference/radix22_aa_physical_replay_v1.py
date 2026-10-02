"""Retained A-a/point field comparison only; no vendor, QDB, remote or refit.

Reuse existing frozen terminal and report readers. Field area is measured;
whole placement benefit remains an experiment and component timing failed.
"""
import argparse
import json
from pathlib import Path
import re

from fpga.reference import radix22_selector_physical_replay_v1 as p
from fpga.reference import a10_point_fit_consume_v3 as parent_reader
from fpga.reference import radix22_aa_pointdata27_v1 as source

ROOT = source.ROOT
DOSSIER = ROOT/'queue/fit-r54-controller-field2h-v12/terminal/aa-pointdata27-sizing'
RECEIPT = '43835d6a2ad529d0a35bd4ded8f09571734092ccf5257d46e1594f4ddefbc224'
PROJECT = ROOT/'artifacts/aa-pointdata27-v1/candidate-field-workers6'
SOURCE_PINS = {
    'reference/radix22_selector_physical_replay_v1.py': 'b5857ffcc53269d11b73d89e011be6539450b4fca99fca04a3b3a8dc4a720913',
    'reference/a10_point_fit_consume_v3.py': '75fcd8481693813faf13d527f2c86161e752ffebb2ada7032ea4aa4a957b8abb',
    'reference/radix22_aa_pointdata27_v1.py': 'ad5dab15bac378c652757ea34d6aebc7cad97ad0a8c6b5d24eab4aee5701fc90',
}
LABELS = {
    'needed_ALM': 'ALMs needed [=A-B+C]',
    'placed_ALM': '[A] ALMs used in final placement [=a+b+c+d]',
    'LAB': 'Total LABs:  partially or completely used',
    'final_registers': 'Total registers',
    'M20K': 'Total RAM Blocks', 'DSP': 'Total DSP Blocks',
    'RAM_bits': 'Total block memory bits',
    'logic_ALUT': 'Combinational ALUT usage for logic',
    'route_ALUT': 'Combinational ALUT usage for route-throughs',
}


def need(ok, why):
    if not ok:
        raise ValueError(why)


def memories(text, width, final=False):
    need(type(width) is int and width in (27, 32), 'known storage width')
    rows = [p.cells(line) for line in text.splitlines()
            if line.startswith('; child|child|memories[') and '.data_ram|' in line
            and 'Simple Dual Port' in line]
    banks = set()
    for row in rows:
        banks.add(int(re.search(r'memories\[(\d+)\]', row[0])[1]))
        if final:
            need(row[1:4] == ['M20K', 'Simple Dual Port', 'Single Clock']
                 and row[4:8] == ['512', str(width), '512', str(width)]
                 and row[12:18] == [str(512*width), '512', str(width), '512', str(width), str(512*width)]
                 and row[18:20] == ['1.000', '0.000'], 'final implemented RAM geometry/one M20K per bank')
        else:
            need(row[1:3] == ['M20K block', 'Simple Dual Port']
                 and row[3:13] == ['512', str(width), '512', str(width), str(512*width),
                                  '512', str(width), '512', str(width), str(512*width)], 'synthesis logical/implemented geometry')
    need(len(rows) == 128 and banks == set(range(128)), 'exact unique complete128 data-bank inventory')
    return dict(banks=128, rows=512, logical_width=width, implemented_width=width,
                utilized_data_bits=128*512*width, allocated_data_M20K=128 if final else None)


def retained_candidate():
    h = p.h
    need(h.digest(DOSSIER/'receipt.json') == RECEIPT, 'exact actual terminal receipt')
    r = h.read(DOSSIER/'receipt.json'); e = DOSSIER/'evidence'; project = e/'project'
    need(r['native_job_succeeded'] and r['terminal_proven'] and not r['findings']
         and r['host'] == 'gfn16-aws-m8i', 'actual native/source terminal, not timing admission')
    archive = h.archive(DOSSIER/'native-reports.tar.gz')
    need(h.digest(DOSSIER/'native-reports.tar.gz') == r['archive']['sha256']
         and (DOSSIER/'native-reports.tar.gz').stat().st_size == r['archive']['size'], 'archive identity')
    inventory = h.read(e/'collection/collection-inventory-v1.json')
    need(h.digest(e/'collection/collection-inventory-v1.json') == r['inventory_sha256']
         and inventory['count'] == len(inventory['files']) == 41, '41-file exact inventory')
    need(set(archive) == set(inventory['files']) | {'collection/collection-inventory-v1.json'}
         and archive == {str(x.relative_to(e)): x.read_bytes() for x in e.rglob('*') if x.is_file()}, '42-member complete local archive')
    for name, item in inventory['files'].items():
        need(h.sha(archive[name]) == item['sha256'] and len(archive[name]) == item['size'], 'inventory hash/size '+name)
    need(sum(x['size'] for x in inventory['files'].values()) == inventory['bytes'], 'inventory byte sum')
    m, c, request = (h.read(project/'manifest.json'), h.read(project/'execution-context.json'), h.read(e/'request.json'))
    need(h.digest(project/'manifest.json') == h.digest(PROJECT/'manifest.json') == c['manifest_sha256']
         == request['project']['manifest_sha256'], 'exact prepared/executed manifest')
    need(m['source_sha256'] == c['source_sha256'] == request['project']['source_sha256'], 'source context identity')
    need(len(m['source_sha256']) == 10, 'isolated10-RTL candidate')
    for name, pin in m['source_sha256'].items():
        need(h.digest(project/'rtl'/name) == pin == h.digest(PROJECT/'rtl'/name), 'actual prepared RTL '+name)
    need((project/'rtl'/Path(source.TARGET).name).read_text() == source.source(), 'exact ONE RAM-only reverse source delta')
    for name, pin in c['control_sha256'].items():
        need(pin == request['project']['control_sha256'][name] == h.digest(PROJECT/name), 'source-bound control '+name)
        actual = (project/name).read_bytes(); expected = (PROJECT/name).read_bytes()
        if name == 'probe.qsf':
            expected += b'set_global_assignment -name LAST_QUARTUS_VERSION "26.1.0 Pro Edition"\n'
        need(actual == expected, 'only allowed vendor QSF version metadata suffix')
    need(m['core_parameters'] == c['qsf_parameters'] == dict(AW=16, LANES=64, HOST_LANES=16, P=104857601, Q=4190109697)
         and m['clock_period_ns'] == 8 and m['seed'] == 1 and m['compile_processors'] == 6, 'field source geometry/clock/seed')
    need(h.digest(e/'request.json') == r['source_request_sha256'], 'actual request identity')
    need((c['quartus_workers'], c['cpu_max'], c['memory_max'], c['swap_max'], c['timeout_seconds'],
          c['outer_runtime_max_seconds'], c['outer_timeout_stop_seconds'])
         == (6, '600000 100000', str(20<<30), '0', 7200, 7200, 60), 'actual FIELD2H caps/finite envelope')
    need(c['slot'] == 'b' and c['affinity'] == c['allowed_cpus'] == list(range(6,12))
         and c['physical_cores'] == [c['topology'][str(x)] for x in c['affinity']]
         and len(set(map(tuple,c['physical_cores']))) == 6, 'actual six distinct physical cores')
    need(h.read(project/'plain-final-source-guard.json') == dict(unchanged=True, drift=[], vendor_returncode=0, promotion_allowed=False), 'final source guard')
    result = h.read(project/'execution-result.json')
    need(result == r['native_result'] and result['context_sha256'] == h.digest(project/'execution-context.json')
         and result['quartus_returncode'] == result['summarize_returncode'] == 0, 'actual source-bound vendor completion')
    proof = h.read(e/'collection/native-journal-proof.json')
    need(proof == r['native_journal_proof'] and proof['terminal_proven'] and proof['invocation_id'] == r['invocation_id'], 'terminal invocation closure')
    journal = [json.loads(line) for line in (e/'collection/native-journal.jsonl').read_text().splitlines()]
    trusted = [x for x in journal if x.get('_PID') == '1' and x.get('UNIT') == r['unit'] and x.get('INVOCATION_ID') == r['invocation_id']]
    need(any(x.get('MESSAGE') == proof['manager_terminal_message'] for x in trusted)
         and all(x in trusted for x in proof['resource_journal']), 'actual trusted manager terminal/resource records')
    database = h.read(project/'database-inventory-final.json')
    need(len(database) == r['compiled_db_files'] == 225 and sum(x['size'] for x in database.values()) == r['compiled_db_bytes']
         and not inventory['raw_qdb_included'], '225 QDB files inventory only, no local rehash')
    return dict(receipt_sha256=RECEIPT, archive_sha256=r['archive']['sha256'], inventory_members=41, archive_members=42,
                manifest_sha256=c['manifest_sha256'], invocation=r['invocation_id'], source_files=10,
                manager_elapsed_seconds=proof['manager_elapsed_seconds'], peak_bytes=int(proof['resource_journal'][0]['MEMORY_PEAK']),
                CPU_seconds=int(proof['resource_journal'][0]['CPU_USAGE_NSEC'])/1e9,
                database_inventory_only_files=225, database_inventory_only_bytes=r['compiled_db_bytes'],
                host_slot='AWSB', physical_cores=c['physical_cores'], timeout_seconds=7200)


def metrics(output):
    h = p.h
    fit, sta, syn, place = [(output/n).read_text() for n in ('probe.fit.rpt','probe.sta.rpt','probe.syn.rpt','probe.fit.place.rpt')]
    need('26.1.0 Build 110 03/26/2026 SC Pro Edition' in fit and '10AX115N4F40E3SG' in fit
         and re.search(r'; Fitter Status\s*; Successful',fit), 'actual native device/tool/fit completion')
    need(re.search(r'; kernel_clk ; Base ; 8.000\s*; 125.0 MHz ; 0.000 ; 4.000',sta), 'actual matched8ns clock')
    for corner in ('Slow 900mV 100C Model','Slow 900mV 0C Model','Fast 900mV 100C Model','Fast 900mV 0C Model'):
        need(corner in sta, 'four-corner report coverage')
    return dict(resources={name:p.number(fit,label) for name,label in LABELS.items()},
                synthesis_registers=p.number(syn,'Total registers'), place_registers=p.number(place,'Dedicated logic registers'),
                timing={name:p.timing(sta,label) for name,label in {'setup':'Setup Summary','hold':'Hold Summary','pulse':'Minimum Pulse Width Summary'}.items()},
                raw_report_sha256={n:h.digest(output/n) for n in ('probe.fit.rpt','probe.sta.rpt','probe.syn.rpt','probe.fit.place.rpt')})


def replay():
    h = p.h
    need(all(h.digest(ROOT/name) == pin for name,pin in SOURCE_PINS.items()), 'frozen reused readers/source helper')
    old = parent_reader.consume(); actual = retained_candidate()
    parent_output = source.DOSSIER/'evidence/project/output_files'; output = DOSSIER/'evidence/project/output_files'
    before, after = metrics(parent_output), metrics(output)
    for label in ('synthesis','final'):
        report = 'probe.syn.rpt' if label == 'synthesis' else 'probe.fit.rpt'
        before[label+'_RAM'] = memories((parent_output/report).read_text(),32,label=='final')
        after[label+'_RAM'] = memories((output/report).read_text(),27,label=='final')
    delta = {name:after['resources'][name]-value for name,value in before['resources'].items()}
    need(delta['RAM_bits'] == -327680 and delta['M20K'] == delta['DSP'] == 0, 'exact5*N utilized bits only; no physical block saving')
    need(before['timing']['setup']['slack_ns'] < 0 and after['timing']['setup']['slack_ns'] < 0, 'both setup failures preserved')
    return dict(schema='A-a-pointdata27-physical-owner-replay-v1',scope='matched_source_one_field_component_only',
                status='SOURCE_NATIVE_TERMINAL_REPLAY_PASS_AREA_SAVING_TIMING_REGRESSION',candidate=actual,
                parent_receipt_sha256=old['native_receipt_sha256'],parent_archive_sha256=old['raw_archive_sha256'],
                parent_manifest_sha256=old['source_manifest_sha256'],parent_inventory_members=40,parent_archive_members=41,
                parent=before, candidate_metrics=after, candidate_minus_parent=delta,
                synthesis_register_delta=after['synthesis_registers']-before['synthesis_registers'],
                place_register_delta=after['place_registers']-before['place_registers'],
                setup_delta_ns=round(after['timing']['setup']['slack_ns']-before['timing']['setup']['slack_ns'],3),
                setup_TNS_delta_ns=round(after['timing']['setup']['TNS_ns']-before['timing']['setup']['TNS_ns'],3),
                setup_failing_endpoint_delta=after['timing']['setup']['failing_endpoints']-before['timing']['setup']['failing_endpoints'],
                needed_ALM_saving_percent=round(100*(before['resources']['needed_ALM']-after['resources']['needed_ALM'])/before['resources']['needed_ALM'],3),
                recommendation='Retain_ONE_separate_point_RAM27_whole_area_integration_experiment_after_range_source_gates_NO_clock_promotion',
                native_gate_owner_receipt_sha256='6d6e27807ead841d4cce6e2b6b88dd82637f99177fbbeac463546e9f83f7aebb',
                measured_versus_hypothesis='6208_needed_ALMs_and7027_placed_saved_per_field_not_advisor8to12K; M20K322/DSP128unchanged; wholearea_andtiming_NOT_measured',
                host_context_caveat='SameAWSdevice/tools/sourceboundary/clock8ns/seed1/workers6; parentAWSA0-5/6h_vs_candidateAWSB6-11/2h. Differentplacement/neighborworkload, no causalwall/runtime claim.',
                hardware_badword_or_whole_block_atomicity_proved=False, native_assertions_simulation_only=True,
                full_N_numeric_or_HDL_vendor_rerun_on_Mac=False, remote_or_QDB_or_refit=False,
                scaled_three_field_or_whole_saving_claim=False, usable_or_audited_clock_claim=False,
                independent_review=False, promotion_allowed=False)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=replay()
    if args.output:
        with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))
