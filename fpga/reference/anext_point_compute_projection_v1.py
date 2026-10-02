"""Point-only scalar comparison; no point PRP/1000 or selected-clock adoption."""
from decimal import Decimal
from fpga.reference.anext_compute_projection_v1 import calculate as original,COUNT,ROOT,pinned,need,SAMPLE,SAMPLE_SHA
REPORT='queue/evidence/anext-point-representative-aw16-q1-v1/attempt-0/collected/output/native/report.json'
REPORT_SHA='2ae7a6367b3b436576204c0224117d914294434da02b90c0bc255923db68110d'
PHYSICAL='artifacts/anext-point-9668ps-aws6-plain-v1/project/manifest.json'
PHYSICAL_SHA='3f2ba54d86b39afe482484b2afb9aee03b3f8c4b84306600d6daf616354ac84f'
AUDIT='results/throughput-20260929/anext-point-9668-11196-timing-audit-v1/interpretation-v1.json'
AUDIT_SHA='961e1a8ec17ce3b88de967d4ca21a629386359e3c972e82ffab992d0375099cf'
def calculate(count=COUNT,period_ps=11196):
    r=original(count,period_ps);r['backend_cycles_by_phase']['ntt']+=count
    r['backend_cycles']+=count;r['command_square_latency_cycles']+=count
    seconds=lambda n:str(Decimal(n)*Decimal(period_ps)/Decimal(10**12))
    r['backend_seconds']=seconds(r['backend_cycles']);r['command_latency_sum_seconds']=seconds(r['command_square_latency_cycles'])
    need(r['backend_cycles']==25990+(count-1)*21873==sum(r['backend_cycles_by_phase'].values()),'point-only full operation sum')
    r.update(candidate='A-next-point-v1',same_base_native_chain_exists=False,point_specific_PRP_pass=False,point_specific_1000_pass=False,
        checkpoint_scope='No checkpoint in this fixed cached-chain projection. Point-only representative AW16 is16 squares/eight complete images, not original core1000 inherited.',
        numerical_scope='Point-only AW5/AW8 and representativeAW16 plus point-flight reset/cancel are observed. Exactsample604832956 PRP and point-only continuous1000 are unrun; no backward/forward inheritance.',
        measured_cycle_delta_from_original_per_square=1)
    return r
def project():
    n=pinned(REPORT,REPORT_SHA);a=pinned(AUDIT,AUDIT_SHA);p=pinned(PHYSICAL,PHYSICAL_SHA)
    need(a['point_manifest_sha256']==PHYSICAL_SHA and a['clock']['selected_period_ns']==11.196 and a['clock']['selected_all_measured_tns_ns']==0 and a['clock']['selected_all_measured_failing_endpoints']==0,'actual selected point-only audit')
    need(len(p['source_sha256'])==30 and all(n['sources']['rtl/kernel/'+k]==v for k,v in p['source_sha256'].items()),'same thirty point native/physical sources')
    v=n['validations']['anext-point-representative-aw16'];rows=v['metrics']
    need(len(rows)==16 and {x['double'] for x in rows}=={0,1},'representative both double settings')
    for x in rows:
        cost=21873+4108*x['cold']+9*x['load']
        wanted=dict(total=cost,latency=cost+2,ntt=17710,seed=0,root=9*x['load'],prefill=4106*x['cold'],post=4158)
        need(all(type(x[k]) is int and x[k]==z for k,z in wanted.items()),'point measured phase calendar')
    s=pinned(SAMPLE,SAMPLE_SHA)['projection'];need((s['n'],s['base'],s['exponent_bits_from_frozen_reference'])==(65536,604832956,COUNT),'unchanged scalar sample descriptor')
    result=calculate();result['evidence_pins']=dict(native_report=REPORT_SHA,physical_manifest=PHYSICAL_SHA,audit_interpretation=AUDIT_SHA,audit_terminal=a['terminal_receipt_sha256'],sample_descriptor=SAMPLE_SHA)
    result['audit_limitations']=a['limitations'];result['local_full_N_integer_computations']=0
    return result
if __name__=='__main__':
    import json
    print(json.dumps(project(),indent=2))
