"""Read-only matched component evidence association, not independent review."""
import json
from pathlib import Path
from fpga.reference import stream27_r15_storage_ram_bind as b

ROOT=b.ROOT
BASE=ROOT/'queue/standing-fit-state/terminal'
GATE=ROOT/'queue/evidence/s4-p16-r15-crt-numeric-pair-normal-q1-v1/gate-receipt.json'
NATIVE=GATE.parent/'attempt-0/collected/output/native/report.json'


def reference(path):
    return dict(path=str(path.relative_to(ROOT)),sha256=b.sha(path.read_bytes()))


def first_value(lines,label):
    hits=[l for l in lines if l.startswith('; '+label+' ') and l.split(';')[1].strip()==label.strip()]
    b.need(len(hits)==1,'UNIQUE_REPORT_RESOURCE:'+label)
    return int(hits[0].split(';')[2].strip().split('/')[0].strip().replace(',',''))


def one(variant):
    directory=BASE/('s4-p16-r15-crt-storage-'+variant+'-10000-v1')
    rp=directory/'receipt.json';receipt=json.loads(rp.read_text())
    b.need(receipt['native_job_succeeded'] and receipt['collection_completed'] and
           receipt['terminal_proven'] and not receipt['findings'] and receipt['scope']=='component_probe',
           'ACTUAL_COMPONENT_TERMINAL')
    project=directory/'evidence/project'
    m=json.loads((project/'manifest.json').read_text());native=json.loads(NATIVE.read_text())
    gate=json.loads(GATE.read_text())
    b.need(native['status']=='completed_native_commands_unreviewed' and
           b.sha(NATIVE.read_bytes())==gate['report_sha256'] and
           gate['status']=='PASS_expected_contracts' and m['native_source_gate']==GATE.parent.name,
           'ACTUAL_OWN_NATIVE_GATE')
    for name,pin in m['source_sha256'].items():
        b.need(b.sha((project/'rtl'/name).read_bytes())==native['sources'].get('rtl/'+name)==pin,
               'FULL_NATIVE_PHYSICAL_SOURCE_JOIN:'+name)
    b.need((project/'probe.sdc').read_text()=='create_clock -name kernel_clk -period 10.000 [get_ports {clk}]\nderive_clock_uncertainty\n',
           'NO_CHANGED_TIMING_EXCEPTIONS')
    fit=project/'output_files/probe.fit.rpt';sta=project/'output_files/probe.sta.rpt'
    lines=fit.read_text().splitlines()
    resources={
        'needed_ALM':first_value(lines,'ALMs needed [=A-B+C]'),
        'placed_ALM':first_value(lines,'    [A] ALMs used in final placement [=a+b+c+d]'),
        'LAB':first_value(lines,'Total LABs:  partially or completely used'),
        'FF':first_value(lines,'Total registers'),
        'M20K':first_value(lines,'M20K blocks'),
        'physical_DSP':first_value(lines,'DSP Blocks Needed [=A+B+C-D]')}
    mappings={}
    if variant=='candidate':
        header=next(l for l in lines if l.startswith('; Name ') and 'M20K blocks' in l and 'MLABs' in l)
        keys=[s.strip() for s in header.split(';')[1:-1]]
        for l in lines:
            if l.startswith('; r15_') and '; MLAB ;' in l:
                row=dict(zip(keys,[s.strip() for s in l.split(';')[1:-1]]))
                b.need(row['Mixed Port RDW Mode']=="Don't care" and row['Port A Depth']=='8' and
                       row['Port B Depth']=='8' and row['Mode']=='Simple Dual Port', 'EXACT_RAM_MAPPING')
                mappings[row['Name']]=row
        b.need(len(mappings)==3,'THREE_UNIQUE_MAPPED_RAMS')
    resources['MLAB']=sum(int(float(r['MLABs'])) for r in mappings.values())
    summaries=[l for l in sta.read_text().splitlines() if l.startswith(';  kernel_clk')]
    values=[[s.strip() for s in l.split(';')[1:-1]] for l in summaries]
    positive=[v for v in values if len(v)==6 and v[1]!='0.000']
    b.need(len(positive)==1,'UNRESTRICTED_CLOCK_SUMMARY')
    slack=dict(setup_ns=float(positive[0][1]),hold_ns=float(positive[0][2]),mpw_ns=float(positive[0][5]))
    corners=('Slow 900mV 100C Model','Slow 900mV 0C Model','Fast 900mV 100C Model','Fast 900mV 0C Model')
    b.need(all(c in sta.read_text() for c in corners),'FOUR_CORNER_REPORTS_PRESENT')
    return dict(receipt=reference(rp),resources=resources,slack=slack,RAM=mappings,
        source_join=native['sources'],source_manifest=reference(project/'manifest.json'),
        QSF=reference(project/'probe.qsf'),SDC=reference(project/'probe.sdc'),
        fit=reference(fit),sta=reference(sta),archive_sha256=receipt['archive']['sha256'],
        device=m['device'],period_ns=m['clock_period_ns'],seed=m['seed'],
        physical_cores=len(receipt['native_context_resources']['physical_cores']),
        source_tool_executable_scope='Native source-bound Quartus26.1 Build110; no board programming')


def report():
    gate=json.loads(GATE.read_text());b.need(gate['status']=='PASS_expected_contracts','OWN_NORMAL_PASS')
    parent,candidate=one('parent'),one('candidate')
    b.need((parent['device'],parent['period_ns'],parent['seed'],parent['physical_cores'])==
           (candidate['device'],candidate['period_ns'],candidate['seed'],candidate['physical_cores']),
           'MATCHED_PHYSICAL_CONTROLS')
    delta={k:candidate['resources'][k]-v for k,v in parent['resources'].items()}
    b.need(delta==dict(needed_ALM=135,placed_ALM=-3,LAB=-2,FF=-579,M20K=0,physical_DSP=0,MLAB=7),
           'MEASURED_RESULT_EXPECTED')
    return dict(schema='r15-storage-crt-matched-component-owner-result-v1',
        status='ACTUAL_MATCHED_COMPONENT_INFERENCE_AND_PLACE_PASS',
        own_normal_gate=reference(GATE),parent=parent,candidate=candidate,candidate_minus_parent=delta,
        decision='MLAB mapping succeeds; modest placed-LAB decrease, needed-ALM estimate increases. Keep whole decision contingent on own whole native/placement.',
        exact_default_off_switch='storage_to_ram; metadataOFF,numeric r1/d3/x12 ON',
        latency_delta=0,II=1,coefficient_edges=16,
        whole_native_pending=True,own_reset_suite_pending=True,
        whole_ALM_LAB_FF_or_clock_savings=None,physical_benefit_addition_assumed=False,
        independent_review=False,promotion_allowed=False,
        exclusions=['One CRT only; unconstrained standalone LABs are not additive to whole layouts.',
                    'Virtual-pin internal clock; no I/O delay, reset release or board signoff.',
                    'Standard four-corner global STA is reported, not a tightest-clock search.',
                    'No inherited P2 savings, term-payload RDW waiver, width truncation or arbitrary-memory-corruption immunity.'])


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();b.need(out.is_relative_to(ROOT) and not out.exists(),'FRESH_COMPONENT_RESULT')
    value=report();out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
    print(json.dumps(dict(path=str(out),candidate_minus_parent=value['candidate_minus_parent'],
                         sha256=b.sha(out.read_bytes()),promotion_allowed=False)))
