"""Strict representative-native stdout replay using scalar recipe identities."""
import argparse
import json
from pathlib import Path
from fpga.reference.track_a4_core_aw5_output_v1 import FIELDS,need,tokens
from fpga.reference.track_a4_representative_recipe_v1 import geometry


def parse(output,aw,strict_schedule=True):
    g=geometry(aw);t=g['t'];lines=output.splitlines()
    need(len(lines)==17,'sixteen square rows plus footer only')
    rows=[tokens(line,'A4_CORE_SQUARE',FIELDS) for line in lines[:-1]]
    counts={k:g[k] for k in ('aw','commands','squares','cold_squares','profile_loads','readbacks','hold_checks')}
    footer=tokens(lines[-1],'A4_CORE_PASS',tuple(counts)+('ticks','max_latency'))
    need(all(footer[k]==v for k,v in counts.items()),'exact representative coverage')
    discrepancies=[]
    for row,identity in zip(rows,g['identities']):
        need({k:row[k] for k in identity}==identity,'ordered recipe-bound identity')
        need(0<row['latency']<=footer['max_latency'] and row['total']>0 and row['ntt']>0 and row['seed']>0,'positive measurements')
        prediction=dict(post=t+62,prefill=(t+10)*row['cold'],root=((2*aw+2)*257+5)*row['load'],
            total=row['root']+row['ntt']+t+66+(t+12)*row['cold'],latency=row['total']+2)
        if aw==16:prediction['ntt']=20558  # matched engine model; still checked, not silently substituted
        differences={k:dict(measured=row[k],source_hypothesis=v) for k,v in prediction.items() if row[k]!=v}
        if differences:discrepancies.append(dict(index=row['index'],differences=differences))
    need(len({r['ntt'] for r in rows})==1 and len({r['seed'] for r in rows})==1,'invariant transform phases')
    need(footer['ticks']>sum(r['latency'] for r in rows),'ticks include all loading/readback traffic')
    if strict_schedule:need(not discrepancies,'source budget mismatch: '+json.dumps(discrepancies))
    return dict(status='replayed_representative_native_output',aw=aw,footer=footer,metrics=rows,
        source_schedule_hypotheses_match=not discrepancies,source_schedule_discrepancies=discrepancies,
        promotion_allowed=False,scope='Signed monomial/dense all-max, min/max base, normal/double warm chains, full readback and one reset. Not random/full faults/PRP/1000-square soak/fit.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-log',type=Path,required=True);parser.add_argument('--aw',type=int,required=True,choices=(5,8,16))
    parser.add_argument('--report-schedule-mismatch',action='store_true');args=parser.parse_args()
    print(json.dumps(parse(args.output_log.read_text(),args.aw,not args.report_schedule_mismatch),indent=2))
