"""Track A A4: additive block-strided carry/prefill planning model.

Exact arithmetic reuses the adopted S1 proof; local numeric work is N<=256.
Full N is addresses, events and scalar bounds only. No RTL cycle claim.
"""
import hashlib
import json
from pathlib import Path

from fpga.reference import stream_ntt_blockcarry_model as arithmetic

PROFILE = "track-a4-blockcarry16-digitpatch-v1"
ROOT = Path(__file__).resolve().parents[1]
DEPENDENCIES = (
    "reference/track_a4_blockcarry_model.py",
    "tests/test_track_a4_blockcarry_model.py",
    "reference/stream_ntt_blockcarry_model.py",
    "reference/stream_ntt_blockwrap2_proposal.py",
    "rtl/kernel/genefer_stream27_blockcarry_small_cell.sv",
    "rtl/kernel/genefer_stream27_signed_boundary_reduce27_pipe.sv",
    "rtl/kernel/genefer_div_recip_precision.sv",
    "rtl/kernel/genefer_digit_reduce27_pipe.sv",
    "rtl/kernel/genefer_crt3_27_mont_pipe.sv",
    "rtl/kernel/genefer_sdp_ram32.sv",
    "rtl/kernel/genefer_ntt_banked27_prefetch_r2_orient8_rootfused_engine.sv",
    "rtl/kernel/genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rootfused_engine.sv",
    "rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill.sv",
    "results/throughput-20260929/core27-prefill-aw16-normal-v1/report.json",
)


def bank_of(address):
    """Frozen 64-butterfly engine: 128 banks, XOR-fold j onto j%7."""
    bank = 0
    while address:
        bank ^= address & 127
        address >>= 7
    return bank


def address_row(n, offset):
    if n < 32 or n > 65536 or n & (n - 1):
        raise ValueError("AW5..16 power-of-two geometry")
    if not 0 <= offset < n // 16:
        raise ValueError("block offset")
    return tuple(k * (n // 16) + offset for k in range(16))


def route_row(n, offset):
    return tuple((bank_of(a), a >> 7) for a in address_row(n, offset))


def patch_residues(state, mutant=None):
    """Reduce canonical d and legal signed c separately, then modular add.

The shared signed reducer does NOT admit d+c. Store d plus c0/c1 metadata
for invariant checking and canonicalization; effective signed32 words are
the digit-domain image written to the next NTT's ordinary-residue RAM.
"""
    n = len(state.digits)
    if n > 256:
        raise ValueError("local arithmetic limited to N<=256")
    t = n // 16
    if len(state.c0) != 16:
        raise ValueError("A4 has sixteen blocks")
    rows = []
    for p, _ in arithmetic.core.FIELDS:
        row = [d % p for d in state.digits]
        for k in range(16):
            c0, c1 = state.c0[k], state.c1[k]
            if mutant == "drop-boundary":
                c0 = c1 = 0
            if mutant == "drop-c1":
                c1 = 0
            if mutant == "wrong-wrap-sign" and k == 0:
                c0, c1 = -c0, -c1
            for j, correction in enumerate((c0, c1)):
                row[k*t+j] = (row[k*t+j] + correction % p) % p
        rows.append(row)
    return rows


def direct_square(state, double_bit=0):
    """Independent quadratic negacyclic convolution, no numeric NTT."""
    n = len(state.digits)
    if n > 256:
        raise ValueError("local arithmetic limited to N<=256")
    if type(double_bit) is not int or double_bit not in (0, 1):
        raise ValueError("double bit")
    a = state.effective()
    out = [0] * n
    for i, x in enumerate(a):
        for j, y in enumerate(a):
            index = i + j
            out[index % n] += x*y*(1 if index < n else -1)
    return [v << double_bit for v in out]


def schedule(n=65536, *, independent_ports=True, epoch=1, cancel_edge=None):
    """Concrete proposed edge schedule. Each event is an accepted clock edge.

RAM read k -> CRT accepts k+1/output k+16 -> div77 k+17/output k+28
-> div47 k+29/output k+40 -> registered y k+41 -> small cell k+42
-> digit RAM/reducer accept k+43 -> reducer output k+46 -> boundary k+47
-> NTT RAM write k+48. Inter-cell connections consume the NEXT edge.
The 97-edge reciprocal setup starts with NTT and must finish before edge0.

    Final raw0 registers at lastread+43; normalization reuses small_cell at
    +44 with carry0/block_start false; high registers +45. Patch waits +49.
Two rows launch successively: d reducer aligned to signed c output at +4,
modular add +5, launch register +6, RAM write +7, child-error check +8.
"""
    t = n // 16
    address_row(n, 0)
    reads, writes = {}, {}
    read_edges, write_edges = [], []
    edge = 0
    # Legacy exclusive vector access must serialize every coincident write.
    for offset in range(t):
        while not independent_ports and edge in writes:
            edge += 1
        reads[edge] = offset
        writes[edge + 48] = offset
        read_edges.append(edge)
        write_edges.append(edge + 48)
        edge += 1
    last = read_edges[-1]
    normal_last = write_edges[-1]
    patch_launch = max(last + 46, normal_last + 1)
    patch_writes = {patch_launch + 7: 0, patch_launch + 8: 1}
    check = patch_launch + 9
    events = []
    bank_overlaps = 0
    for clock in range(check + 1):
        if cancel_edge is not None and clock >= cancel_edge:
            continue
        read = reads.get(clock)
        write = writes.get(clock)
        patch = patch_writes.get(clock)
        r = route_row(n, read) if read is not None else ()
        w = route_row(n, write if write is not None else patch) if write is not None or patch is not None else ()
        assert len({b for b, _ in r}) == len(r)
        assert len({b for b, _ in w}) == len(w)
        assert not (write is not None and patch is not None)
        rmap, wmap = dict(r), dict(w)
        bank_overlaps += len(rmap.keys() & wmap.keys())
        assert not any(rmap[b] == wmap[b] for b in rmap.keys() & wmap.keys())
        if read is not None or write is not None or patch is not None:
            events.append(dict(edge=clock, epoch=epoch, read_offset=read,
                               write_offset=write, patch_offset=patch))
    return dict(n=n, blocks=16, block_length=t, independent_ports=independent_ports,
                first_digit_edge=42, first_ntt_write_edge=48,
                last_read_edge=last, last_normal_write_edge=normal_last,
                boundary_pair_ready_edge=last+45, patch_launch_edge=patch_launch,
                patch_write_edges=list(patch_writes), check_edge=check,
                post_ntt_clocks=check+1, issue_stalls=last+1-t,
                simultaneous_read_write_edges=len(reads.keys() & writes.keys()),
                simultaneous_bank_read_write_pairs=bank_overlaps,
                same_address_collisions=0, per_bank_ports="one read plus one write",
                cancelled=cancel_edge is not None and cancel_edge <= check,
                eligible=cancel_edge is None or cancel_edge > check, events=events)


def bounds(n, base):
    p = arithmetic.proof(n, 16, base)
    # Maximum effective digit patch stays in signed32, despite being noncanonical.
    p.update(effective_c0_min=1-base, effective_c0_max=2*(base-1),
             effective_c1_min=-p["c1_abs_max"],
             effective_c1_max=base-1+p["c1_abs_max"])
    assert p["doubled_coefficient_bound"] < 2**77
    assert p["serial_carry_abs_bound"] < 2**47
    assert p["effective_c0_max"] < 2**31
    assert p["effective_c1_max"] < 2**31
    # From A/base^2 < 2N+22.5P, P16 has >=8 spare units before the
    # shared cell's Q=2N+23P guard. raw0=r1+q2_prev+c, c>=-2.
    q_cell = 2*n+23*16
    assert p["q2_abs_bound"]+2 <= q_cell
    assert base-1+p["q2_abs_bound"]+3 <= 2*(base-1)+q_cell
    p["boundary_raw0_admitted_by_shared_small_cell"] = True
    return p


def report():
    full = schedule()
    legacy = schedule(independent_ports=False)
    parent = json.loads((ROOT / DEPENDENCIES[-1]).read_text())
    # Resolve measured row by contents, without guessing the report array name.
    rows = [v for v in parent.values() if isinstance(v, list)]
    warm = next(row for rows_ in rows for row in rows_ if isinstance(row, dict)
                and row.get("cycles") == 28823 and row.get("conversion") == 0)
    full.pop("events")
    legacy.pop("events")
    return dict(status="planning_model_only", profile=PROFILE,
                source_sha256={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
                               for p in DEPENDENCIES},
                full_n=full, legacy_exclusive_port=legacy,
                bounds=[bounds(65536, b) for b in (131077, 10**9)],
                t5_warm_cycles=warm["cycles"], t5_ntt_cycles=warm["ntt"],
                t5_crt_cycles=warm["crt"], t5_carry_cycles=warm["carry"],
                proposed_warm_cycles=warm["ntt"]+full["post_ntt_clocks"],
                proposed_delta=full["post_ntt_clocks"]-warm["crt"]-warm["carry"],
                exclusions="No HDL/native/physical/full-N numeric NTT evidence. Proposed controller edges must be checked in RTL. Host canonicalization latency excluded from warm interval.")


if __name__ == "__main__":
    print(json.dumps(arithmetic.exact_json(report()), indent=2))
