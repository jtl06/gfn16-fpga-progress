"""v4 registered admission schedule; exact unchanged AW5/AW8 vector identities."""
from fpga.reference.track_a4_core_output_v2 import parse as ancestor_parse

def parse(output,vectors,strict_schedule=True):
    result=ancestor_parse(output,vectors,strict_schedule=False)
    t=(1<<result['aw'])//16;discrepancies=[]
    for row in result['metrics']:
        predicted=dict(post=t+62,prefill=(t+10)*row['cold'],
            root=((2*result['aw']+2)*257+5)*row['load'],
            total=row['root']+row['ntt']+t+67+(t+12)*row['cold'],latency=row['total']+2)
        delta={k:dict(measured=row[k],source_hypothesis=v) for k,v in predicted.items() if row[k]!=v}
        if delta:discrepancies.append(dict(index=row['index'],differences=delta))
    if strict_schedule and discrepancies:raise ValueError('v4 registered admission schedule mismatch: '+str(discrepancies))
    result.update(source_schedule_hypotheses_match=not discrepancies,source_schedule_discrepancies=discrepancies,
        registered_admission_cycle_delta=1,status='replayed_v4_source_bound_native_output')
    return result
