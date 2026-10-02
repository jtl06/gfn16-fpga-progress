"""Source-bound measured duration admission and one-batch ticket activation.

Artifact/cycle/timing metadata only: no GMP, numeric reference, HDL, cloud
transport or launch. The dispatcher still checks current locks/resources,
host-hours/deadline and launches each immutable native packet. Estimates are
not worst-case guarantees; native finite stop guards remain mandatory.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]
SHORT='soak-t5b-aw16-short-native-q3-v1'
SHORT_CASE='5f156dd8fc7c8530b5f9c697b2a4e9bb479ba7d919f74a855f47db93c97e9801'
FULL_CASE='2730e05de298ecbf5d7125acb7d6859b581b21ed8c84fb1bbfd7d3aaccd007ba'
CORE='rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1.sv'
CORE_SHA='704f7fed433d724dbc8e56c7b725824ec36cce78d6ce8f021307837d2a96b8e7'
BENCH='rtl/tb/core27_t5b_soak_v1.cpp'
BENCH_SHA='c4972670a55bbb0c7b039e7a0175ee6918e5a95f3e0dd4a5a96c7dbc7175fab7'
RUNTIME_SHA='84fb40c8e6452d4b660d9302e83584dd3c4761aa6219495e57f2df582401cf0b'


def need(ok,message):
    if not ok:raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def dump(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')


def predict(steps,cold,warm,full_reference_seconds):
    n=65536;wanted={'soak-normal','soak-negative-boundary','soak-negative-loaded-state'}
    need(set(steps)==wanted and all(math.isfinite(x['seconds']) and x['seconds']>0 for x in steps.values()),
         'complete finite measured commands')
    need(type(cold) is int and type(warm) is int and cold>0 and warm>0,'measured cycle counts')
    ticks={'soak-normal':4*n+8+cold+warm,
           'soak-negative-boundary':3*n+6+cold,
           'soak-negative-loaded-state':2*n+4}
    rate=max(steps[name]['seconds']/count for name,count in ticks.items())
    chunk_ticks=3*n+105+cold+99*warm
    continuous_ticks=12*n+1014+cold+999*warm
    need(math.isfinite(full_reference_seconds) and full_reference_seconds>0,'finite reference replay cost')
    return dict(model_seconds_per_tick_upper_observed=rate,margin=1.75,
        measured_ticks=ticks,chunk_operations=100,chunk_model_ticks=chunk_ticks,
        chunk_command_seconds_estimate=1.75*rate*chunk_ticks,
        full_reference_replay_seconds_estimate=1.75*full_reference_seconds,
        continuous_operations=1000,continuous_model_ticks=continuous_ticks,
        continuous_command_seconds_estimate=1.75*rate*continuous_ticks)


def admission(short_ticket,full_reference_ticket):
    short_ticket=Path(short_ticket).resolve();ticket=json.loads(short_ticket.read_text())
    need(ticket['id']==SHORT and ticket['result']['status']=='needs_independent_review','actual T5b short result')
    props=ticket['result']['properties']
    need(props['Result']=='success' and props['ExecMainStatus']=='0' and props['MainPID']=='0'
         and props['ControlGroup']=='','terminal short unit and empty cgroup')
    gate=ticket['dependency_gate'];gate_path=Path(gate['path'])
    need(gate['status']=='PASS_expected_contracts' and sha(gate_path)==gate['sha256'],'source/config-bound native gate')
    receipt=json.loads(gate_path.read_text());evidence=Path(ticket['result']['evidence'])
    report_path=evidence/'output/native/report.json';report=json.loads(report_path.read_text())
    manifest_path=evidence/'manifest.json';manifest=json.loads(manifest_path.read_text())
    need(sha(report_path)==receipt['report_sha256']==ticket['result']['queue_report']['report_sha256']
         and sha(manifest_path)==gate['manifest_sha256']==report['manifest_sha256']
         and report['sources']==manifest['sources'],'native source/report/contract identity')
    need(ticket['package']['profile'] in ('gcp-c4d-static01-v1','gcp-c4d-static23-v1')
         and report['host']=='gfn16-pilot-c4d' and manifest['build']['parameters']==dict(AW=16,NTT_LANES=64)
         and manifest['sources'][CORE]==CORE_SHA and manifest['sources'][BENCH]==BENCH_SHA
         and manifest['sources']['soak/runtime.json']==RUNTIME_SHA
         and report['probe']==dict(context_threads=1,model_threads=1,expected_threads=1),
         'same T5b serial GCP build/runtime/geometry')
    validations=report['validations']
    need(set(validations)=={'soak-normal','soak-negative-boundary','soak-negative-loaded-state'}
         and validations['soak-normal']['status']=='passed_soak_segment_boundary_replay'
         and validations['soak-normal']['independent_gmpy2_boundary_replay'] is True
         and validations['soak-normal']['case_id']==SHORT_CASE
         and validations['soak-normal']['operations']==2 and validations['soak-normal']['readbacks']==3
         and all(validations[name]['status']=='passed_matched_soak_negative'
                 for name in ('soak-negative-boundary','soak-negative-loaded-state')),'complete short typed contracts')
    commands={row['name']:row for row in report['steps']}
    log_path=evidence/'output/native/soak-normal.log'
    need(sha(log_path)==commands['soak-normal']['sha256'],'native timing trace hash')
    rows=[json.loads(line.split(' ',1)[1]) for line in log_path.read_text().splitlines() if line.startswith('SOAK_STEP ')]
    need(len(rows)==2 and [row['step'] for row in rows]==[1,2]
         and all(row['case_id']==SHORT_CASE for row in rows),'complete two-operation timing trace')
    full_reference_ticket=Path(full_reference_ticket).resolve();full=json.loads(full_reference_ticket.read_text())
    need(full['id']=='soak-t5b-aw16-full-reference-q3-v1'
         and full['reference_execution_receipt']['status']=='PASS_reference_execution_outputs_not_HDL_or_import',
         'actual full reference cost contract')
    forecast=predict({name:commands[name] for name in validations},rows[0]['cycles'],rows[1]['cycles'],
                     full['result']['queue_report']['elapsed_seconds'])
    forecast['chunk_overall_seconds_estimate']=forecast['chunk_command_seconds_estimate'] \
        +1.75*(commands['lint']['seconds']+commands['build']['seconds']) \
        +forecast['full_reference_replay_seconds_estimate']+45
    need(forecast['chunk_command_seconds_estimate']<1800
         and forecast['chunk_overall_seconds_estimate']<3600,'100-square finite bounds; choose explicitly smaller chunks otherwise')
    return dict(schema='core27-t5b-soak-duration-admission-v1',status='PASS_bounded_chunk_duration_estimate',
        short_ticket_sha256=sha(short_ticket),short_gate_sha256=gate['sha256'],
        short_manifest_sha256=sha(manifest_path),short_report_sha256=sha(report_path),
        full_reference_ticket_sha256=sha(full_reference_ticket),short_functional_sha256=gate['functional_sha256'],
        host='gfn16-pilot-c4d',model_threads=1,source_model_build=manifest['build'],
        source_model_pins={name:manifest['sources'][name] for name in [*manifest['build']['sv_sources'],BENCH,
            'rtl/tb/native_runtime_context_v1.h','reference/core27_t5b_soak_v1.py',
            'reference/core27_t5b_soak_native_v1.py','soak/runtime.json']},
        forecast=forecast,admitted_bounds=dict(command_seconds=1800,overall_seconds=3600,outer_seconds=3700),
        compatible_hosts=['gfn16-pilot-c4d'],continuous_admitted=False,
        qualification_scope='Measured conservative estimate plus mandatory native finite stop guards; not arithmetic/native/promotion proof.')


def activate(batch,short_ticket,full_reference_ticket,output):
    output=Path(output).resolve();need(not output.exists(),'fresh chunk activation output')
    result=admission(short_ticket,full_reference_ticket)
    batch=Path(batch).resolve();output.mkdir(parents=True);dump(output/'duration-admission.json',result)
    tickets=[]
    for index in range(10):
        draft=json.loads((batch/f'chunk-{index:02d}/draft-ticket.json').read_text())
        need(draft['after']==[SHORT] and 'package' not in draft and 'packages' not in draft,
             'nonrunnable source-prepared draft')
        packages=draft.pop('candidate_packages');need(len(packages)==2,'two static GCP variants')
        for package in packages:
            need(sha(Path(package['archive']))==package['sha256'],'immutable prepared chunk archive')
            with tarfile.open(package['archive'],'r:gz') as archive:
                manifest=json.loads(archive.extractfile('manifest.json').read())
            need(manifest['build']==result['source_model_build']
                 and all(manifest['sources'].get(name)==pin for name,pin in result['source_model_pins'].items())
                 and manifest['soak']['case_id']==FULL_CASE and manifest['soak']['segment']==f'chunk-{index:02d}'
                 and len(manifest['steps'])==1 and manifest['steps'][0]['validator']['config']=={'negative':'none'},
                 'exact same admitted model/runtime and normal chunk geometry')
        draft.pop('blocked_reason');draft['packages']=packages
        draft['measured_runtime_admission']=dict(path=str(output/'duration-admission.json'),sha256=sha(output/'duration-admission.json'))
        path=output/f'chunk-{index:02d}-global-ticket.json';dump(path,draft);tickets.append(str(path))
    answer=dict(status='activated10_source_bound_chunk_tickets_not_dispatched',tickets=tickets,
        admission_sha256=sha(output/'duration-admission.json'),continuous_admitted=False)
    dump(output/'activation-receipt.json',answer);return answer


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('batch','short-ticket','full-reference-ticket','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();print(json.dumps(activate(args.batch,args.short_ticket,args.full_reference_ticket,args.output),indent=2))
