"""F3 event ledger: each transform stage and point phase waits for RAM commit."""
from fpga.reference.anext_point_contract_v1 import schedule as parent
def schedule(aw,**kwargs):
    r=parent(aw,**kwargs);delta=2*aw+1
    r['point_engine_cycles']+=1
    for k in ('ntt_controller_cycles','warm_backend','warm_host','cold_cached_backend','cold_cached_host','cold_loaded_backend','cold_loaded_host'):r[k]+=delta
    r['assumptions']+=['F3 internal selected data/row/bank enables capture together; physical write E9, final commit precedes stage change/done. External block E0/E1 unchanged.']
    r['writeback_delta_from_upper']=delta
    return r
