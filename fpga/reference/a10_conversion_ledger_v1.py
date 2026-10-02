"""Exact A10/G4 unchanged conversion edge ledger; no numerical NTT.

This rejects a tempting but false extra three-cycle saving: R2 input fusion
already removed the standalone Montgomery conversion in the frozen G4 parent.
Both cores retain carry RAM response, four-stage digit reduction and the same
ordinary-domain boundary register before NTT RAM acceptance.
"""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENT = 'rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont.sv'
CANDIDATE = 'rtl/kernel/genefer_square_core27_a10_crtmont_v1.sv'
PINS = {
    PARENT: 'b6dbd4fccc6d7708fd295d3c82e2ebec444c4a2fbde8612851f10f979da04895',
    CANDIDATE: '8e7cb148b104cb2f9313e6200d7635d8e1b08436178cd1ccc2d4d740582d6103',
    'rtl/kernel/genefer_digit_reduce27_pipe.sv': '61e14bb13c2dbcc13b5030756578a0d0358269beb24fb207a5641b98795883e8',
    'rtl/kernel/genefer_carry_prefix_stream_precision.sv': 'ba7ce9d0c1a99ad959bfe9909c62f341fabd537c76f196c5bcb6394c161296d3',
    'rtl/kernel/genefer_sp_ram.sv': 'b97d2f43db1b1e1aa60b9b7fc2b720af1e302bd5ff9e35854c89b30e5fb610df',
    'rtl/kernel/genefer_sdp_ram32.sv': '993567fb68fdc216b9ff04489d1810f743b86564434e4b48261ad606b25d53b0',
}


def need(ok, why):
    if not ok: raise ValueError(why)


def source_guard():
    for name, pin in PINS.items():
        need(hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == pin,
             'A10_CONVERSION_SOURCE_DRIFT ' + name)
    parent = (ROOT/PARENT).read_text()
    child = (ROOT/CANDIDATE).read_text()
    begin = '            genefer_digit_reduce27_pipe'
    a = parent.split(begin,1)[1].split('        genefer_root_profile27_r2_rom',1)[0]
    b = child.split(begin,1)[1].split('        genefer_a10_profile3_rom_v1',1)[0]
    a = a.replace('// Format2 twist consumes ordinary canonical d, not d*R.',
                  '// Merged CT consumes ordinary canonical d; no R2 twist pointpass.')
    need(a == b, 'A10_CONVERSION_DATAPATH_REGISTER_DELTA')
    for s in (parent,child):
        need('conversion_cycles<=conversion_cycles+1;' in s and
             'if(&conversion_valid) begin' in s and
             'if(int\'(write_count)==N-IO_STEP) begin' in s,
             'A10_CONVERSION_COUNTER_BOUNDARY')
    return dict(PINS)


def edge_ledger(n):
    """Valid-token simulation of NBA boundaries, not coefficient arithmetic.

    Edge0 is the top-level accepted start (not a CONVERT count). The first
    counted edge1 accepts carry RAM read0; its response becomes observable
    after edge1. The reducer accepts it at edge2, responds after edge5; the
    ordinary boundary captures at edge6; NTT RAM/top consume at edge7.
    """
    need(type(n) is int and n >= 16 and n <= 65536 and n & (n-1) == 0,
         'A10_CONVERSION_GEOMETRY')
    groups = (n+15)//16
    read_response = reduce_output = boundary = None
    reduce_regs = [None]*3
    commits = []
    first = {}
    for edge in range(1,groups+7):
        # Consumers use OLD state, exactly as separate RTL always_ff blocks.
        commit = boundary
        if commit is not None:
            commits.append((edge,commit))
            first.setdefault('ntt_ram_commit',edge)
        new_boundary = reduce_output
        if new_boundary is not None: first.setdefault('ordinary_boundary',edge)
        new_reduce_output = reduce_regs[-1]
        if new_reduce_output is not None: first.setdefault('reducer_response',edge)
        new_reduce_regs = [read_response]+reduce_regs[:-1]
        if read_response is not None: first.setdefault('reducer_accept',edge)
        new_read_response = edge-1 if edge <= groups else None
        if new_read_response is not None: first.setdefault('carry_ram_response',edge)
        read_response,reduce_regs,reduce_output,boundary = (
            new_read_response,new_reduce_regs,new_reduce_output,new_boundary)
    need([index for _,index in commits] == list(range(groups)), 'A10_CONVERSION_COMMIT_ORDER')
    need(first == dict(carry_ram_response=1,reducer_accept=2,reducer_response=5,
                       ordinary_boundary=6,ntt_ram_commit=7), 'A10_CONVERSION_FIRST_EDGE')
    need(commits[-1][0] == groups+6, 'A10_CONVERSION_LAST_EDGE')
    return dict(n=n,groups=groups,conversion_cycles=groups+6,first_edges=first,
                last_commit_edge=commits[-1][0],unchanged_from_frozen_G4=True,
                removed_additional_conversion_cycles=0,numeric_NTT_performed=False)


def check_counter(observed,n):
    expected = edge_ledger(n)['conversion_cycles']
    need(type(observed) is int and observed == expected,
         'A10_CONVERSION_COUNTER_MISMATCH')
    return expected


if __name__ == '__main__':
    import json
    print(json.dumps(dict(source_pins=source_guard(),ledger=edge_ledger(65536)),indent=2))
