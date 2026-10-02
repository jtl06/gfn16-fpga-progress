"""Event-only +1 point phase; no native or timing promotion implied."""
from fpga.reference.anext_composition_contract_v1 import schedule as parent

def schedule(aw,**kwargs):
    result=parent(aw,**kwargs)
    for name in ('point_engine_cycles','ntt_controller_cycles','warm_backend','warm_host',
                 'cold_cached_backend','cold_cached_host','cold_loaded_backend','cold_loaded_host'):
        result[name]+=1
    result['assumptions']=result['assumptions']+['Point operand/valid/type/row/half advance one additional registered edge; block E0/E1 unchanged.']
    return result
