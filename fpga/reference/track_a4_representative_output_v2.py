"""A4b/v4 measured representative metrics, one extra admission edge per square."""
from fpga.reference.track_a4_representative_output_v1 import parse as parent_parse

def parse(output,aw,strict_schedule=True):
    result=parent_parse(output,aw,strict_schedule=False);t=(1<<aw)//16;differences=[]
    for row in result['metrics']:
        prediction=dict(post=t+62,prefill=(t+10)*row['cold'],root=((2*aw+2)*257+5)*row['load'],
            total=row['root']+row['ntt']+t+67+(t+12)*row['cold'],latency=row['total']+2)
        if aw==16:prediction['ntt']=20558
        delta={k:dict(measured=row[k],source_hypothesis=v) for k,v in prediction.items() if row[k]!=v}
        if delta:differences.append(dict(index=row['index'],differences=delta))
    if strict_schedule and differences:raise ValueError('A4b representative budget mismatch: '+str(differences))
    result.update(status='replayed_A4b_representative_native_output',source_schedule_hypotheses_match=not differences,
        source_schedule_discrepancies=differences,registered_admission_cycle_delta=1)
    return result
