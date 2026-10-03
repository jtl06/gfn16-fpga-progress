"""Routine matched source/resource/global-STA association, owner authored."""
import json
from pathlib import Path
from . import stream27_r15_canonical_foldstage_native as n
from . import stream27_r15_crt_storage_result as common

ROOT=n.ROOT
def ref(path):return dict(path=str(path.relative_to(ROOT)),sha256=n.sha(path.read_bytes()))

def one(variant):
    directory=ROOT/'queue/standing-fit-state/terminal'/('s4-p16-r15-canonical-foldstage-'+variant+'-12000-v1')
    receipt_path=directory/'receipt.json';receipt=json.loads(receipt_path.read_bytes())
    n.b.need(receipt['native_job_succeeded'] and receipt['terminal_proven'] and receipt['collection_completed'] and
      receipt['scope']=='component_probe' and not receipt['findings'],'ACTUAL_COMPONENT_SUCCESS')
    project=directory/'evidence/project';m=json.loads((project/'manifest.json').read_bytes())
    gate_path=ROOT/'queue/evidence'/n.identifier(16,'normal')/'gate-receipt.json';g=json.loads(gate_path.read_bytes())
    report_path=gate_path.parent/'attempt-0/collected/output/native/report.json';r=json.loads(report_path.read_bytes())
    n.b.need(g['status']=='PASS_expected_contracts' and n.sha(report_path.read_bytes())==g['report_sha256'],'ACTUAL_NATIVE_GATE')
    for name,pin in m['source_sha256'].items():
        n.b.need(n.sha((project/'rtl'/name).read_bytes())==r['sources'].get('rtl/'+name)==pin,'OWN_ACTUAL_SOURCE_JOIN:'+name)
    n.b.need(m['core_parameters']==dict(AW=16,P=16) and m['seed']==1 and m['clock_period_ns']==12,'MATCHED_PARAMETERS')
    n.b.need((project/'probe.sdc').read_text()=='create_clock -name kernel_clk -period 12.000 [get_ports {clk}]\nderive_clock_uncertainty\n','NO_TIMING_EXCEPTION_DELTA')
    fit=project/'output_files/probe.fit.rpt';sta=project/'output_files/probe.sta.rpt';lines=fit.read_text().splitlines()
    resources={key:common.first_value(lines,label) for key,label in {
      'needed_ALM':'ALMs needed [=A-B+C]','placed_ALM':'    [A] ALMs used in final placement [=a+b+c+d]',
      'LAB':'Total LABs:  partially or completely used','FF':'Total registers','M20K':'M20K blocks',
      'DSP':'DSP Blocks Needed [=A+B+C-D]','MLAB_bits':'Total MLAB memory bits'}.items()}
    text=sta.read_text();rows=[[s.strip() for s in l.split(';')[1:-1]] for l in text.splitlines() if l.startswith(';  kernel_clk')]
    summaries=[v for v in rows if len(v)==6 and v[1]!='0.000'];n.b.need(len(summaries)==1,'GLOBAL_SUMMARY')
    v=summaries[0];slack=dict(setup_ns=float(v[1]),hold_ns=float(v[2]),mpw_ns=float(v[5]))
    n.b.need(all(c in text for c in ('Slow 900mV 100C Model','Slow 900mV 0C Model','Fast 900mV 100C Model','Fast 900mV 0C Model')),'FOUR_CORNER_SCOPE')
    detail=text[text.index('Path #1:'):];path={}
    for key,label in [('from','From Node'),('to','To Node'),('exception','SDC Exception'),('corner','Worst-Case Operating Conditions')]:
        line=next(l for l in detail.splitlines() if l.startswith('; '+label+' '));path[key]=line.split(';')[2].strip()
    line=next(l for l in detail.splitlines() if l.startswith('; Data Delay '));path['data_delay_ns']=float(line.split(';')[2].strip())
    line=next(l for l in detail.splitlines() if l.startswith('; Number of Logic Levels '));path['logic_levels']=int(line.split(';')[3].strip())
    n.b.need(path['exception']=='No SDC Exception on Path','UNRESTRICTED_PATH')
    return dict(receipt=ref(receipt_path),resources=resources,global_STA=slack,worst_path=path,
      fit=ref(fit),sta=ref(sta),manifest=ref(project/'manifest.json'),QSF=ref(project/'probe.qsf'),SDC=ref(project/'probe.sdc'),
      archive_sha256=receipt['archive']['sha256'],device=m['device'],physical_cores=len(receipt['native_context_resources']['physical_cores']))

def report():
    old,new=one('parent'),one('candidate');n.b.need(old['device']==new['device'] and old['physical_cores']==new['physical_cores']==4,'MATCHED_DEVICE_CORES')
    delta={k:new['resources'][k]-v for k,v in old['resources'].items()}
    n.b.need(delta==dict(needed_ALM=135,placed_ALM=-58,LAB=1,FF=8,M20K=0,DSP=0,MLAB_bits=0),'ACTUAL_RESOURCE_DELTA')
    return dict(schema='r15-canonical-foldstage-matched-owner-result-v1',status='ACTUAL_MATCHED_COMPONENT_SUCCESS',
      parent=old,candidate=new,candidate_minus_parent=delta,global_setup_delta_ns=round(new['global_STA']['setup_ns']-old['global_STA']['setup_ns'],3),
      actual_full_service_delta=196608,normal_old_new=[589824,786432],special_old_new=[655360,851968],
      source_flag='future CANONICAL_FOLD_STAGE defaultOFF',component_only=True,whole_period_or_LAB_delta=None,
      full_fault_not_PASS_due_to_initial_quota_failure=True,independent_review=False,promotion_allowed=False,
      exclusions=['Global standard four-corner STA, not tightest-clock/board/I-O/reset-release signoff.',
        'One scratch leaf, not whole critical class closure or aggregate density offset.',
        'Whole source-owned serialized allocation/publication calendar must add measured3N per canonical job.'])

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();n.b.need(out.is_relative_to(n.BASE) and not out.exists(),'FRESH_MATCHED_RESULT')
    value=report()
    with out.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
    print(json.dumps(dict(path=str(out),sha256=n.sha(out.read_bytes()),delta=value['candidate_minus_parent'],setup_delta_ns=value['global_setup_delta_ns'])))
