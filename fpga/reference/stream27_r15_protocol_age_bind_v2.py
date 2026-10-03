"""Additive declaration-width repair over frozen AGE60 v1.

All callers/CLI use unsigned32 flag parameters. The protocol declaration now
matches that width, avoiding typed WIDTHTRUNC on -GEPOCH_AGE_REG=1. Values0/1
retain identical constant selection, age state, tuple/calendar/fault authority.
"""
import copy
from fpga.reference import stream27_r15_protocol_age_bind as parent

ROOT=parent.ROOT
SELF='reference/stream27_r15_protocol_age_bind_v2.py'
BEFORE='parameter bit EPOCH_AGE_REG=0,'
AFTER='parameter int unsigned EPOCH_AGE_REG=0,'


def prepare(n=256,epoch_age_reg=0):
    parent.need(type(epoch_age_reg) is int and epoch_age_reg in (0,1),'V2_BINARY_FLAG')
    if epoch_age_reg==0:return parent.prepare(n,0)
    out=copy.deepcopy(parent.prepare(n,1));name=parent.PRIVATE_LEAF
    text=out['files'][name]
    parent.need(text.count(BEFORE)==1,'V2_FLAG_WIDTH_ANCHOR')
    out['files'][name]=text.replace(BEFORE,AFTER,1)
    parent.need(out['files'][name].replace(AFTER,BEFORE,1)==text,'V2_WIDTH_REVERSE')
    out['generated_sha256'][name]=parent.sha(out['files'][name])
    out['source_dependencies']=list(dict.fromkeys(out['source_dependencies']+[SELF]))
    out['source_sha256'][SELF]=parent.sha((ROOT/SELF).read_bytes())
    # Keep primitive reversal metadata accurate for the new declared leaf.
    out['r15_protocol_age']['primitive_edits']=[
        [old,new.replace(BEFORE,AFTER,1)] for old,new in out['r15_protocol_age']['primitive_edits']]
    out['r15_protocol_age']['parameter_width_successor']=dict(
        declaration_width=32,accepted_compile_values=[0,1],only_declaration_changed=True,
        reverse_exact_v1=True,v1_lint_failure_preserved=True,v1_native_outcome_inherited=False,
        new_native_qualified=False,clock_area_claim=False)
    return out
