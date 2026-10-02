"""Metadata correction: expose the already-budgeted F3 per-transform increment.

Frozen v1 native validators used only NTT/whole counts, which were correct.
Its auxiliary transform_engine_cycles field omitted +AW. No RTL, harness,
observed output contract, or existing result changes; preserve v1 snapshots.
"""
from fpga.reference.anext_writeback_contract_v1 import schedule as prior
def schedule(aw,**kwargs):
    r=prior(aw,**kwargs);r['transform_engine_cycles']+=aw
    if 2*r['transform_engine_cycles']+r['point_engine_cycles']+6!=r['ntt_controller_cycles']:
        raise ValueError('F3 component-to-controller cycle accounting')
    r['auxiliary_transform_metadata_corrected']=True
    return r
