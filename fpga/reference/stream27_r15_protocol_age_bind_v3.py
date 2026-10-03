"""Additive explicit Boolean predicates over preserved width-v2 AGE60.

The unsigned32 CLI/parameter declaration remains; each of the three ternary
conditions is explicitly one-bit. Binary0/1 semantics and all state/check
bodies remain identical. No lint waiver, shared compute change or fit claim.
"""
import copy
from fpga.reference import stream27_r15_protocol_age_bind as original
from fpga.reference import stream27_r15_protocol_age_bind_v2 as parent

ROOT=original.ROOT
SELF='reference/stream27_r15_protocol_age_bind_v3.py'
BEFORE='EPOCH_AGE_REG ?'
AFTER="(EPOCH_AGE_REG != 32'd0) ?"


def prepare(n=256,epoch_age_reg=0):
    original.need(type(epoch_age_reg) is int and epoch_age_reg in (0,1),'V3_BINARY_FLAG')
    if epoch_age_reg==0:return original.capture(n)
    out=copy.deepcopy(parent.prepare(n,1));name=original.PRIVATE_LEAF
    text=out['files'][name]
    original.need(text.count(BEFORE)==3,'V3_BOOLEAN_TERNARY_ANCHORS')
    out['files'][name]=text.replace(BEFORE,AFTER)
    original.need(out['files'][name].replace(AFTER,BEFORE)==text,'V3_BOOLEAN_REVERSE')
    out['generated_sha256'][name]=original.sha(out['files'][name])
    out['source_dependencies']=list(dict.fromkeys(out['source_dependencies']+[SELF]))
    out['source_sha256'][SELF]=original.sha((ROOT/SELF).read_bytes())
    out['r15_protocol_age']['primitive_edits']=[
        [old,new.replace(BEFORE,AFTER)] for old,new in out['r15_protocol_age']['primitive_edits']]
    out['r15_protocol_age']['boolean_predicate_successor']=dict(
        ternary_condition_width=1,parameter_declaration_width=32,accepted_compile_values=[0,1],
        only_three_predicates_changed=True,reverse_exact_v2=True,v2_lint_failure_preserved=True,
        ancestor_native_outcome_inherited=False,new_native_qualified=False,clock_area_claim=False)
    return out
