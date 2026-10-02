"""Unchanged F3 normal value/cycle corpus, bound to the cold-legality top."""
from fpga.reference import anext_writeback_output_v1 as parent
def validate(stdout,stderr,rc,config,assets):
    result=parent.validate(stdout,stderr,rc,config,assets)
    result.update(candidate='A-next-cold-source-legality-v1',normal_cycle_delta=0,new_numeric_fault_ABI=True)
    return result
