"""Named source-only mutants; each MUST have a freshly built passing control.

No RTL invocation here. A downstream gate must bind exact source hashes, native
logs, process status, event hit counters, and the named fatal. Merely generating
these strings, a syntax failure, or a data mismatch does not qualify a mutant.
"""

MUTANTS = {
    'eligibility_after_load': (
        'if(state==IDLE && !start && load_we)ntt_prefilled<=0;',
        'if(state==IDLE && !start && load_we)ntt_prefilled<=1;',
        'T5_MONITOR_FAST_ELIGIBILITY'),
    'write_address': (
        "assign addr=prefill_window ? prefill_boundary_addr :",
        "assign addr=prefill_window ? prefill_boundary_addr+AW'(IO_STEP) :",
        'T5_MONITOR_WRITE_ADDRESS'),
    'field_mask': (
        '.vector_lane_mask(prefill_window ? prefill_boundary_mask : IO_MASK)',
        ".vector_lane_mask(prefill_window ? (f==1 ? prefill_boundary_mask & 16'hfffe : prefill_boundary_mask) : IO_MASK)",
        'T5_MONITOR_WRITE_MASK'),
    'final_write_count': (
        "if(prefill_commit)prefill_written<=prefill_written+(AW+1)'(IO_STEP);",
        "if(prefill_commit && int'(prefill_written)!=N-IO_STEP)prefill_written<=prefill_written+(AW+1)'(IO_STEP);",
        'T5_MONITOR_COMPLETE_COUNT'),
    'base_tag': (
        'assign fast_eligible=ntt_prefilled && base==prefill_base &&',
        "assign fast_eligible=ntt_prefilled && 1'b1 &&",
        'T5_MONITOR_FAST_ELIGIBILITY'),
    'late_host_error': (
        'assign core_fault=carry_host_error || (|ntt_host_error) ||',
        "assign core_fault=carry_host_error || 1'b0 ||",
        'T5_MONITOR_LATE_ERROR'),
}


def mutate(source, name):
    before, after, fatal = MUTANTS[name]
    if source.count(before) != 1:
        raise ValueError('ambiguous T5 mutation anchor: '+name)
    return source.replace(before, after, 1), fatal
