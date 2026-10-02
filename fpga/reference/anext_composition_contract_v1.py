"""A-next source contract: scalar/event budgets only, not a native cycle claim.

T5b is the promoted arithmetic parent. A4b replaces carry/image/host service;
A10 replaces the five-pass format2 NTT with canonical merged CT/square/GS.
F2 recurrence lookahead cannot be summed into a design with no recurrence.
"""
from fpga.reference.track_a4_registered_schedule_v1 import registered_schedule


def root_contract(*, merged_a10=True, recurrence_f2=False):
    if merged_a10 and recurrence_f2:
        raise ValueError('ANEXT_F2_HAS_NO_RECURRENCE_IN_A10_FIXED_ROM')
    if not merged_a10:
        raise ValueError('ANEXT_FORMAT2_BRANCH_NOT_IMPLEMENTED')
    return dict(profile_format=3, header_words=4,
                header=['0x41313000', 'N', 'R^2/N mod P', 'primitive 2N psi'],
                phases=['canonical_CT_descending', 'Montgomery_square', 'canonical_GS_ascending'],
                domains=['ordinary_R0', 'ordinary_R0_bit_reversed_odd_frequencies', 'R_minus_1', 'ordinary_R0_natural'],
                final_upper_normalizer=True, centered_CRT_integer_doubling=True,
                seed_recurrence_present=False, f2_cycle_credit=0,
                reset_or_error_requires_reload=True)


def schedule(aw, *, block_response_edges=1, independent_read_write=True,
             merged_a10=True, recurrence_f2=False):
    root_contract(merged_a10=merged_a10, recurrence_f2=recurrence_f2)
    if aw not in (5, 8, 16):
        raise ValueError('ANEXT_BOUNDED_GEOMETRY')
    if block_response_edges != 1 or independent_read_write is not True:
        raise ValueError('ANEXT_REDERIVE_POST_SCHEDULE_FOR_PORT_CHANGE')
    n = 1 << aw
    groups = max(1, n//128)
    transform = aw*(groups+1+8)
    point = max(1, n//64)+7
    ntt = 2*transform+point+6
    events = registered_schedule(n, ntt)
    # A4b's preserved admission token is one edge beyond this frozen v3 model.
    warm = events['warm_backend_cycles']+1
    cached = warm+events['cold_backend_penalty']
    return dict(aw=aw, n=n, transform_engine_cycles=transform,
                point_engine_cycles=point, ntt_controller_cycles=ntt,
                cold_profile_cycles=9, recurrence_seed_cycles=0,
                post_child_cycles=events['internal_post_clocks'],
                cold_prefill_child_cycles=events['cold_prefill_child_cycles'],
                ram_to_ram_displacement=events['ram_to_ram_displacement'],
                warm_backend=warm, warm_host=warm+2,
                cold_cached_backend=cached, cold_cached_host=cached+2,
                cold_loaded_backend=cached+9, cold_loaded_host=cached+11,
                same_address_collisions=events['same_address_collisions'],
                native_measured=False, throughput_claim=False,
                assumptions=['New A10 independent block route preserves E0 RAM accept/E1 consumer.',
                             'A4b registered transfers, image patches and fault tails stay unchanged.',
                             'Three-phase start/done accounting matches A10 native source ledger.'])


def compatible_host_protocol(parent_protocol, successor_protocol):
    if parent_protocol != 'T5b_pulse_load_read_start' or successor_protocol != 'A4b_cmd_ready_rsp_valid':
        raise ValueError('ANEXT_EXPLICIT_HOST_ABI_IDENTITIES')
    return dict(drop_in=False, reason='T5b pulse host and A4b backpressured command host are not interchangeable.',
                required_gate='Explicit command-host successor harness; no inherited T5b host timing or canonical-read claim.')
