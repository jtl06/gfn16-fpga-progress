"""Interpret one frozen shadow component collection; no new execution/replay."""
import argparse,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
IDENTIFIER='s4-shadow-rowwrite-aw16-p16-v1'
EVIDENCE=ROOT/'queue/standing-fit-state/terminal'/IDENTIFIER
def rows(text):
    for line in text.splitlines():
        if line.startswith(';'):yield [x.strip() for x in line.split(';')[1:-1]]
def value(text):return float(text.split()[0].replace(',',''))
def collect(out):
    assert not out.exists()
    receipt=json.loads((EVIDENCE/'receipt.json').read_text());assert receipt['native_job_succeeded'] and receipt['collection_completed']
    summary=json.loads((EVIDENCE/'evidence/root'/('fit-'+IDENTIFIER+'-summary.json')).read_text())['fit-'+IDENTIFIER]
    report=(EVIDENCE/'evidence/project/output_files/probe.fit.rpt').read_text()
    ram=report.split('; Fitter RAM Summary',1)[1].split('; Fitter Resource Usage Summary',1)[0]
    contexts={};mapped=set();bits=0;mlabs=0;m20k=0
    for row in rows(ram):
        if len(row)<20 or row[1] not in ('M20K','MLAB'):continue
        match=re.search(r'contexts\[(\d+)\].*natural_blocks\[(\d+)\]',row[0]);assert match
        ctx,bank=map(int,match.groups());assert (ctx,bank) not in mapped;mapped.add((ctx,bank))
        assert row[1:4]==['M20K','Simple Dual Port','Single Clock'] and row[4:8]==['4096','32','4096','32']
        assert value(row[18])==7 and value(row[19])==0 and int(row[12])==131072
        item=contexts.setdefault(str(ctx),dict(banks=0,logical_bits=0,M20K=0))
        item['banks']+=1;item['logical_bits']+=int(row[12]);item['M20K']+=value(row[18])
        bits+=int(row[12]);m20k+=value(row[18]);mlabs+=value(row[19])
    assert mapped=={(c,b) for c in range(2) for b in range(16)} and bits==4194304 and m20k==224 and mlabs==0
    entity=report.split('; Fitter Resource Utilization by Entity',1)[1]
    top=next(row for row in rows(entity) if len(row)>19 and row[0]=='|')
    leaf=next(row for row in rows(entity) if len(row)>19 and row[0]=='|host_image|')
    sta=(EVIDENCE/'evidence/project/output_files/probe.sta.rpt').read_text()
    pulse=next(value(row[1]) for row in rows(sta.split('; Minimum Pulse Width Summary',1)[1]) if row and row[0]=='kernel_clk')
    result=dict(status='PASS_RAM_mapping_component_ONLY',host=receipt['host'],bundle_sha256=receipt['archive']['sha256'],
        geometry=dict(AW=16,P=16,contexts=2,owner_bits=56),logical_memories=32,logical_bits=bits,M20K=m20k,MLAB=mlabs,DSP=summary['dsp_blocks'],
        per_context=contexts,whole_probe=dict(needed_ALMs=summary['alms_needed'],placed_ALMs=summary['alms_placed'],registers=summary['registers'],virtual_IO_unavailable_ALMs=value(top[4])),
        leaf_hierarchy=dict(needed_ALMs=value(leaf[1]),placed_ALMs=value(leaf[2]),registers=value(leaf[7]),M20K=value(leaf[10])),
        external_sink_registers=727,period_ns=10,setup_ns=summary['setup_slack_ns'],hold_ns=summary['hold_slack_ns'],pulse_width_ns=pulse,
        native_response='E0 after NBA, II1; actualRAMq and full56-bit owner/context; no added payload FF',
        scope='Component only. External sink FFs add one physical-fixture edge; registered RAM-q/context-mux paths constrain10ns. Virtual request/owner inputs, resetrelease, controller/order/publication/drain/sharedfault recovery andwholeclock unqualified. Leaf hierarchy is attribution, not a literal integrated delta.',
        evidence=str(EVIDENCE.relative_to(ROOT)),promotion_allowed=False)
    with out.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);collect(parser.parse_args().output.resolve())
