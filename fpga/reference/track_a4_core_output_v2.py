"""Strict vector-bound AW5/AW8 native metrics; measured and predicted separate."""
import argparse
import hashlib
import json
from pathlib import Path
from fpga.reference.track_a4_core_aw5_output_v1 import FIELDS, need, tokens

PROFILES={
    5:dict(commands=404,readbacks=256,holds=808,sha="5236ca15281ec76d3f048b85c11d530818897f5ec7c9655050ca9284670154ec"),
    8:dict(commands=3092,readbacks=2048,holds=6184,sha="30f2db61016b3a2d26632beae08e80ee42dd38244155a622419af346b7147080"),
}


def parse(output,vectors,strict_schedule=True):
    lines=vectors.splitlines();header=lines[0].split()
    need(len(header)==3 and header[0]=="A4CORE1" and header[1] in ("5","8"),"small-N vector header")
    aw=int(header[1]);profile=PROFILES[aw];t=(1<<aw)//16
    need(hashlib.sha256(vectors.encode()).hexdigest()==profile['sha'],"exact vector hash")
    need(int(header[2])==profile['commands'] and len(lines)==profile['commands']+1,"exact command count")
    commands=[list(map(int,line.split())) for line in lines[1:]]
    need(all(len(row)==10 for row in commands),"exact command fields")
    expected=[dict(index=i,cold=row[8],load=row[9],double=row[4]) for i,row in enumerate(commands) if row[0]==5]
    output_lines=output.splitlines();need(len(output_lines)==15,"fourteen metrics plus footer")
    rows=[tokens(line,'A4_CORE_SQUARE',FIELDS) for line in output_lines[:-1]]
    counts=dict(aw=aw,commands=profile['commands'],squares=14,cold_squares=8,profile_loads=4,
                readbacks=profile['readbacks'],hold_checks=profile['holds'])
    footer=tokens(output_lines[-1],'A4_CORE_PASS',tuple(counts)+('ticks','max_latency'))
    need(all(footer[k]==v for k,v in counts.items()),"fixed complete coverage")
    need(footer['ticks']>0 and footer['max_latency']>0,"positive measurements")
    discrepancies=[]
    for row,identity in zip(rows,expected):
        need({k:row[k] for k in identity}==identity,"ordered vector-bound identity")
        need(row['total']>0 and row['ntt']>0 and row['seed']>0 and 0<row['latency']<=footer['max_latency'],"positive phase measurements")
        prediction=dict(post=t+62,prefill=(t+10)*row['cold'],root=((2*aw+2)*257+5)*row['load'],
            total=row['root']+row['ntt']+t+66+(t+12)*row['cold'],latency=row['total']+2)
        delta={k:dict(measured=row[k],source_hypothesis=v) for k,v in prediction.items() if row[k]!=v}
        if delta:discrepancies.append(dict(index=row['index'],differences=delta))
    need(len({row['ntt'] for row in rows})==1 and len({row['seed'] for row in rows})==1,"invariant transform work")
    need(footer['ticks']>sum(row['latency'] for row in rows),"ticks include host traffic and holds")
    if strict_schedule:need(not discrepancies,"source schedule hypothesis mismatch: "+json.dumps(discrepancies))
    return dict(status='replayed_source_bound_native_output',aw=aw,footer=footer,metrics=rows,
        source_schedule_hypotheses_match=not discrepancies,source_schedule_discrepancies=discrepancies,
        vector_sha256=profile['sha'],promotion_allowed=False,
        scope='Normal whole-square/canonical readback/response hold/one reset only; no exhaustive faults, PRP soak or fit qualification.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-log',type=Path,required=True);parser.add_argument('--vectors',type=Path,required=True)
    parser.add_argument('--report-schedule-mismatch',action='store_true')
    args=parser.parse_args()
    print(json.dumps(parse(args.output_log.read_text(),args.vectors.read_text(),not args.report_schedule_mismatch),indent=2))
