"""Private scalar audit: post-full-guard carry history, not RTL qualification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

FPGA = Path(__file__).resolve().parents[1]
SOURCE = FPGA / "rtl/kernel/genefer_stream27_blockcarry_lane_localbase_v1.sv"
SYN = FPGA / "queue/standing-fit-state/terminal/s4-p16-timing-whole-9000-high-effort-v1/evidence/project/output_files/probe.syn.rpt"


def signed(value: int, width: int) -> int:
    value &= (1 << width) - 1
    return value - (1 << width) if value >> (width - 1) else value


def signed_bits(bound: int) -> int:
    return bound.bit_length() + 1


def history_step(history: tuple[int, int, int, int], q: int | None,
                 bound: int, width: int, last: bool = False, reset: bool = False):
    """Full signed48 check precedes the optional narrowed history capture."""
    if reset:
        return (0, 0, 0, 0), False
    if q is None:
        return history, False
    assert -(1 << 47) <= q < (1 << 47)
    if not -bound <= q <= bound:
        return history, True
    prev, prev2, tail_prev, tail = history
    return (signed(q, width), prev, prev if last else tail_prev,
            signed(q, width) if last else tail), False


def analyze() -> dict:
    source, syn = SOURCE.read_text(), SYN.read_text()
    bound = 2 * 65536 + 23 * 16
    assert bound == 131440
    exhaustive = 0
    for q in range(-bound, bound + 1):
        assert signed(q, 19) == signed(q, 33) == q
        exhaustive += 1
    assert signed(bound, 18) != bound
    old = new = (0, 0, 0, 0)
    transitions = 0
    for q in (0, bound, -bound, None, 131072, -131072, 3,
              (1 << 19) + 3, -(1 << 19) - 3, (1 << 32) + 3,
              -(1 << 32) - 3, (1 << 47) - 1, -(1 << 47), None):
        old, old_bad = history_step(old, q, bound, 33, last=True)
        new, new_bad = history_step(new, q, bound, 19, last=True)
        assert old == new and old_bad == new_bad
        # All downstream additions see exactly the same sign-extended integer.
        for remainder in (0, 999999999):
            for carry in (-4, -2, 0, 3):
                assert signed(remainder + old[2] + carry, 33) == signed(remainder + new[2] + carry, 33)
        transitions += 1
    aliases = []
    for q in ((1 << 19) + 3, -(1 << 19) - 3, (1 << 32) + 3, -(1 << 32) - 3):
        assert abs(q) > bound and abs(signed(q, 19)) <= bound
        aliases.append({"full48": q, "premature19": signed(q, 19)})
    limit = (1 << 77) - 1
    malformed = []
    for coefficient in ((1 << 80) + 3, -(1 << 80) - 3, -(1 << 95), (1 << 95) - 1):
        assert abs(coefficient) > limit
        malformed.append({"full96": coefficient, "premature80": signed(coefficient, 80)})
    groups = []
    for line in syn.splitlines():
        if "3:1" in line and "115 bits" in line and ".carry|" in line:
            cells = [part.strip() for part in line.split(";")][1:-1]
            assert cells[5] == "Yes" and cells[7] == "Yes"
            groups.append({"width": 115, "registered": True,
                           "restructured": True, "example": cells[6]})
    assert len(groups) == 16
    high_anchors = [g["example"] for g in groups if re.search(r"prev2?_q2\[(2[0-9]|3[0-2])\]", g["example"])]
    assert high_anchors
    assert "logic signed [32:0] prev_q2,prev2_q2,tail_prev_q2,tail_q2;" in source
    assert "parts_q2>=-48'(Q_SMALL) && parts_q2<=48'(Q_SMALL)" in source
    assert "if(state==ACTIVE && parts_valid && !fault_now)" in source
    return {
        "evidence_class": "scalar model + existing synthesis report; not native/new fit",
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "synthesis_sha256": hashlib.sha256(SYN.read_bytes()).hexdigest(),
        "full_profile_q_bound": bound, "minimum_signed_history_width": 19,
        "exhaustive_legal_q_checks": exhaustive, "transition_checks": transitions,
        "geometry_widths": [{"aw": aw, "p": p, "q_bound": 2 * (1 << aw) + 23 * p,
                             "signed_bits": signed_bits(2 * (1 << aw) + 23 * p)}
                            for aw in range(5, 17) for p in (8, 16)],
        "unsafe_pre_guard_aliases": aliases, "full96_malformed_checks": malformed,
        "registered_mux_groups": groups, "above19_history_anchors": high_anchors,
        "safe_seam": "Only capture/sign-extend19 after unchanged full48 parts_ok/fault_now. Preserve reset, bubbles, origin fault and all full96/reciprocal/divider precision.",
        "source_bit_opportunity_upper_bound": 4 * (33 - 19) * 16,
        "scope_limit": "Registered mux analysis has 115-bit groups and high history anchors, not a fitted per-bit FF inventory; no physical FF/ALM/LAB savings proved. Tail storage retention not separately enumerated. Histories are already33, not48. No ~7K saving supported.",
    }


if __name__ == "__main__":
    print(json.dumps(analyze(), indent=2))
