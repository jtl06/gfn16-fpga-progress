"""Offline audit of completed orient8/rootfused whole64 report archives."""
import argparse
import hashlib
import json
from pathlib import Path
import re

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def require(ok,message):
    if not ok:raise ValueError(message)

def audit(root,gate_path):
    root=Path(root);gate_path=Path(gate_path)
    context=json.loads((root/'execution-context.json').read_text())
    result=json.loads((root/'execution-result.json').read_text())
    manifest=json.loads((root/'manifest.json').read_text())
    candidates=list(root.glob('*-summary.json'));require(len(candidates)==1,'one summary')
    summaries=json.loads(candidates[0].read_text());require(len(summaries)==1,'one project')
    project,summary=next(iter(summaries.items()));gate=json.loads(gate_path.read_text())
    require(gate['status']=='passed' and gate['aw']==16,'full-N passed native gate')
    require(result['quartus_returncode']==result['summarize_returncode']==0,'successful native tools')
    require(result['context_sha256']==sha(root/'execution-context.json'),'execution context hash')
    require(context['manifest_sha256']==sha(root/'manifest.json'),'manifest binding')
    require(context['source_sha256']==manifest['source_sha256']==summary['manifest']['source_sha256'],'source closure')
    require(manifest==summary['manifest'],'summary manifest equality')
    require(manifest['address_width']==16 and manifest['core_parameters']['NTT_LANES']==64,'whole64 geometry')
    for name,value in context['source_sha256'].items():
        require(sha(root/'rtl'/name)==value,'archived RTL '+name)
        matches=[v for k,v in gate['sources'].items() if k=='rtl/kernel/'+name or k.endswith('/rtl/kernel/'+name)]
        require(matches==[value],'unique native simulation match '+name)
    controls={}
    for name,value in context['control_sha256'].items():
        raw=(root/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()==value:controls[name]='exact'
        else:
            suffix=b'set_global_assignment -name LAST_QUARTUS_VERSION "26.1.0 Pro Edition"\n'
            require(name=='probe.qsf' and raw.endswith(suffix) and hashlib.sha256(raw[:-len(suffix)]).hexdigest()==value,'control drift '+name)
            controls[name]='vendor version append only'
    log=(root/(project+'-fit.log')).read_text()
    require('Quartus Prime Fitter was successful. 0 errors' in log,'native fitter success')
    require('Timing requirements not met' in log,'target miss retained')
    require(summary['fit_success'] is True and summary['internal_timing_met'] is False,'summary classification')
    sta=(root/'output_files/probe.sta.rpt').read_text();fit=(root/'output_files/probe.fit.rpt').read_text()
    require(str(summary['fmax_mhz'])+' MHz' in sta,'reported Fmax in native STA')
    for key in ('setup_slack_ns','hold_slack_ns'):
        require(f"{summary[key]:.3f}" in sta,'native slack '+key)
    labs=re.search(r'Total LABs:.*?;\s*([\d,]+)\s*/\s*([\d,]+)',fit)
    require(labs is not None,'LAB utilization')
    used,total=(int(s.replace(',','')) for s in labs.groups())
    require(total==42720 and used<=total,'target device LAB capacity')
    metrics=[m for m in gate['metrics'] if m.get('case')=='full-random-s1-d1']
    require(len(metrics)==1 and metrics[0]['cycles']==32965,'matched representative cycles')
    artifacts={str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*')) if p.is_file()}
    return dict(status='source_matched_whole64_route_not_timing_closure',project=project,
        source_files_checked=len(manifest['source_sha256']),native_gate_sha256=sha(gate_path),
        control_checks=controls,source_match=True,finished_at=result['finished_at'],
        resources={k:summary[k] for k in ('alms_needed','alms_placed','registers','ram_blocks','dsp_blocks_needed','dsp_blocks_placed')},
        labs_used=used,labs_available=total,lab_percent=100*used/total,warm_cycles=32965,
        timing={k:summary[k] for k in ('fmax_mhz','setup_slack_ns','hold_slack_ns','internal_timing_met')},
        limitations=['Reported Fmax only; no selected-clock all-corner audit','Virtual I/O and reset false-path exclusions',
                    'No board, full PRP or physical-device sign-off'],artifacts=artifacts)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('archive',type=Path);parser.add_argument('gate',type=Path)
    parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    result=audit(args.archive,args.gate)
    with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='artifacts'},indent=2))
