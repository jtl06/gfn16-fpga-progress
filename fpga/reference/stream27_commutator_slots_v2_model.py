"""Additive S3 physical-slot successor with explicit chain/commit authority.

The frozen v1 cell provides physical permutation and local quarantine. This
wrapper owns fault aggregation and one-edge-later commit. Generation values
must not be reused until all old physical rows and pending commits have drained;
disable/re-enable of an unchanged canceled generation is likewise forbidden.
These are outer-controller obligations, not properties proven by this model.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path

from .stream27_commutator_slots_model import PhysicalRow, SlotPair, token_width_scenarios
from .stream27_commutator_sync_model import Token

FROZEN = {
    'reference/stream27_commutator_slots_model.py': '690eff692907bb34fea3a2dba84ac2ccf9bd711612e583ce981057c601e56ef6',
    'tests/test_stream27_commutator_slots_model.py': '687c4d9c098816b1ae1e2725a0891ae62ca65f32ec21e2f5c126e34c261d48e4',
    'reference/stream27_commutator_sync_model.py': '84fa950285704162ed1374bbf53c991abe390e17b21ce557a5a342ae332dd6c5',
    'reference/stream_ntt_schedule.py': '03c1c855e0f6e31f0fcb85d32ed2e604a935e482dfa725d7207e635cb1e963cc',
}


def verify_sources():
    root = Path(__file__).resolve().parents[1]
    for name, digest in FROZEN.items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise ValueError('slots v2 prerequisite changed: ' + name)
    return dict(FROZEN)


@dataclass(frozen=True)
class ChainRow(PhysicalRow):
    stage_errors: tuple = (False, False)


@dataclass(frozen=True)
class Commit:
    valid: bool = False
    frame_start: bool = False
    tokens: tuple | None = None


def commit_row(row, *, enabled=(True, True), generations=(0, 0),
               chain_error=False, reset=False):
    """Recheck current authority at the consuming edge; eligible is advisory.

    This function has no side effects. Its valid result is the sole write-enable
    for the modeled sink. A reset or any currently asserted stage fault blocks
    even an older valid row that is already pending at that sink.
    """
    if reset or chain_error or row.error or not row.slot_valid:
        return Commit()
    if row.tokens is None or len(row.tokens) != 2:
        raise ValueError('commit requires two physical lane tokens')
    owners = {(t.context, t.generation) for t in row.tokens}
    if len(owners) != 1:
        raise ValueError('commit owner mismatch')
    ctx, gen = next(iter(owners))
    if not 0 <= ctx < len(enabled) or ctx >= len(generations):
        raise ValueError('commit context outside live authority')
    if not enabled[ctx] or gen != generations[ctx]:
        return Commit()
    return Commit(True, row.frame_start, row.tokens)


class TwoCell:
    """Every stage fault is sticky and visible at the outer interface.

    A fault suppresses chain output immediately, including a downstream row
    emerging on the same edge. The whole chain stays quarantined until reset.
    Frozen local cells retain physical tags and do not filter canceled rows.
    """
    def __init__(self, first_depth, second_depth, frame_ticks, *, synchronous=True,
                 contexts=1, broken_link=False, same_edge=False):
        self.first = SlotPair(first_depth, frame_ticks, synchronous=synchronous, contexts=contexts)
        self.second = SlotPair(second_depth, frame_ticks, synchronous=synchronous, contexts=contexts)
        self.broken_link = broken_link
        self.same_edge = same_edge
        self.out = ChainRow()

    def edge(self, tokens=None, *, frame_start=False, reset=False,
             enabled=(True, True), generations=(0, 0)):
        if self.out.error and not reset:
            return self.out
        old = self.first.out
        new = self.first.edge(tokens, frame_start=frame_start, reset=reset,
                              enabled=enabled, generations=generations)
        link = new if self.same_edge else old
        valid = link.eligible if self.broken_link else link.slot_valid
        downstream = self.second.edge(link.tokens if valid else None,
            frame_start=link.frame_start and valid, reset=reset,
            enabled=enabled, generations=generations)
        faults = (new.error, downstream.error)
        if any(faults):
            self.out = ChainRow(error=True, tokens=self.out.tokens, stage_errors=faults)
        else:
            self.out = ChainRow(downstream.slot_valid, downstream.frame_start,
                                downstream.eligible, False, downstream.tokens, faults)
        return self.out


class Pipeline:
    """The terminal sink consumes the prior chain output, one edge later."""
    def __init__(self, first_depth, second_depth, frame_ticks, **kwargs):
        self.chain = TwoCell(first_depth, second_depth, frame_ticks, **kwargs)
        self.committed = Commit()

    def edge(self, tokens=None, *, frame_start=False, reset=False,
             enabled=(True, True), generations=(0, 0)):
        pending = self.chain.out
        out = self.chain.edge(tokens, frame_start=frame_start, reset=reset,
                              enabled=enabled, generations=generations)
        self.committed = commit_row(pending, enabled=enabled, generations=generations,
                                    chain_error=out.error, reset=reset)
        return out, self.committed
