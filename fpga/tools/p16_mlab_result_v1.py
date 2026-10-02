"""Interpret the exact matched P2 leaf native collection; never dispatch."""
import argparse,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/'queue/standing-fit-state/terminal'

def table_rows(text):
    for line in text.splitlines():
        if line.startswith(';'):yield [x.strip() for x in line.split(';')[1:-1]]
def number(text):return float(text.split()[0].replace(',',''))
def interpret(label):
    identifier='s4-p2-mlab-'+label+'-p16-v1';root=STATE/identifier
    receipt=json.loads((root/'receipt.json').read_text())
    assert receipt['native_job_succeeded'] and receipt['collection_completed']
    summary=json.loads((root/'evidence/root'/('fit-'+identifier+'-summary.json')).read_text())['fit-'+identifier]
    report=(root/'evidence/project/output_files/probe.fit.rpt').read_text()
    entity=report.split('; Fitter Resource Utilization by Entity',1)[1]
    by_geometry={};top=None
    for row in table_rows(entity):
        if len(row)<19:continue
        if row[0]=='|':top=row
        match=re.fullmatch(r'\|(candidate|parent)_\d+_w(\d+)_d(\d+)\.fifo\|',row[0])
        if not match:continue
        key='w'+match[2]+'_d'+match[3]
        result=by_geometry.setdefault(key,dict(instances=0,alms_needed=0,alms_placed=0,registers=0,mlabs=0))
        result['instances']+=1;result['alms_needed']+=number(row[1]);result['alms_placed']+=number(row[2]);result['registers']+=number(row[7])
    assert top is not None and len(by_geometry)==12 and all(x['instances']==8 for x in by_geometry.values())
    mapped=0;m20k=0;mlabs=0
    if '; Fitter RAM Summary' in report:
        ram=report.split('; Fitter RAM Summary',1)[1].split('; Fitter Resource Usage Summary',1)[0]
        for row in table_rows(ram):
            if len(row)<20 or row[1] not in ('MLAB','M20K'):continue
            match=re.match(r'candidate_\d+_w(\d+)_d(\d+)\.fifo\|',row[0]);assert match
            key='w'+match[1]+'_d'+match[2]
            assert int(row[4])==int(match[2]) and int(row[5])==int(match[1])
            mapped+=1;m20k+=number(row[18]);mlabs+=number(row[19]);by_geometry[key]['mlabs']+=number(row[19])
    if label=='candidate':assert mapped==96 and mlabs==160 and m20k==0
    else:assert mapped==0 and mlabs==0 and m20k==0
    sta=(root/'evidence/project/output_files/probe.sta.rpt').read_text()
    pulse=sta.split('; Minimum Pulse Width Summary',1)[1]
    pulse_slack=next(number(row[1]) for row in table_rows(pulse) if row and row[0]=='kernel_clk')
    return dict(host=receipt['host'],bundle_sha256=receipt['archive']['sha256'],needed_ALMs=summary['alms_needed'],
        placed_ALMs=summary['alms_placed'],registers=summary['registers'],M20K=m20k,MLAB=mlabs,
        virtual_IO_unavailable_ALMs=number(top[4]),setup_ns=summary['setup_slack_ns'],hold_ns=summary['hold_slack_ns'],
        pulse_width_ns=pulse_slack,by_geometry=by_geometry,
        evidence=str(root.relative_to(ROOT)),internal_timing_met=summary['internal_timing_met'])

def main(out):
    assert not out.exists()
    parent=interpret('parent');candidate=interpret('candidate')
    assert parent['virtual_IO_unavailable_ALMs']==candidate['virtual_IO_unavailable_ALMs']
    delta={key:parent[key]-candidate[key] for key in ('needed_ALMs','placed_ALMs','registers')}
    by_geometry={key:{name:parent['by_geometry'][key][name]-candidate['by_geometry'][key][name]
                     for name in ('alms_needed','alms_placed','registers')} for key in parent['by_geometry']}
    result=dict(status='PASS_matched_component_ONLY',period_ns=10,seed=1,parent=parent,candidate=candidate,savings=delta,
        savings_by_geometry=by_geometry,scope='96 independent FIFO leaves,8 perWIDTH10/28/29 xDEPTH4/8/16/32. Equal virtualIO overhead cancels; packedP1stage/field/wholeP16 savings andclock unmeasured. Fourcorner internalSTA; resetrelease/boardIO excluded.',promotion_allowed=False)
    with out.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(status=result['status'],parent={k:v for k,v in parent.items() if k not in ('by_geometry','evidence')},candidate={k:v for k,v in candidate.items() if k not in ('by_geometry','evidence')},savings=delta)))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);main(parser.parse_args().output.resolve())
