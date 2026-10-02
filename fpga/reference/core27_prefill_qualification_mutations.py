"""Additive qualification mutants; frozen checkpoint mutation module unchanged."""
from .core27_prefill_mutations import MUTANTS, mutate

TEE_MUTANTS = {
    'omitted_tee': (
        'assign emit_commit_valid=rst_n && state==EMIT && emit_valid;',
        "assign emit_commit_valid=rst_n && state==EMIT && emit_valid && 1'b0;",
        'T5_MONITOR_TEE_VALID'),
    'corrupted_tee': (
        "assign emit_commit_data[e*96+:96]={{64{emit_data[e][31]}},emit_data[e][31:0]};",
        "assign emit_commit_data[e*96+:96]={{64{emit_data[e][31]}},emit_data[e][31:0]} ^ 96'd1;",
        'T5_MONITOR_TEE_DATA'),
}


def mutate_tee(source, name):
    before, after, fatal = TEE_MUTANTS[name]
    if source.count(before) != 1: raise ValueError('ambiguous tee mutation anchor')
    # The producer's old one-way assertion would otherwise intercept this
    # before the independent observer. Remove it in BOTH fresh control and
    # mutant, preserving the actual-commit equality assertion and all RTL.
    source = tee_control(source)
    return source.replace(before, after, 1), fatal


def tee_control(source):
    guard = '''            if(emit_data[e]!=$signed(emit_commit_data[e*96+:96]))
                $fatal(1,"T5_EMIT_SIGNED32_REPRESENTATION");
'''
    if source.count(guard) != 1: raise ValueError('ambiguous tee producer assertion')
    return source.replace(guard, '', 1)
