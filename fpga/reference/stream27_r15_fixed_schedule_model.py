"""R15 internal proposal calendar only; external I/O is never clock-stalled.

Edges below are PRE-edge sampling ages from an ACTUAL accepted cold frame.
The existing ingress register adds the final edge. Absolute host timestamps
are deliberately absent: the phase counter wraps modulo the proved interval.
"""
from dataclasses import dataclass


@dataclass
class Calendar:
    interval: int
    rows: int
    boundary_preedge: int
    phase: int = 0
    armed: bool = False
    tail: bool = False

    def proposal(self, *, active, remaining, feedback_enabled, local_error=False):
        first = self.armed and active and remaining != 0 and self.phase == self.interval-1
        row_tail = self.armed and active and self.tail and self.phase < self.rows-1
        feedback = (first or row_tail) and not local_error
        correction = (self.armed and feedback_enabled and
                      self.phase == self.boundary_preedge % self.interval and not local_error)
        return feedback, first and feedback, correction

    def edge(self, *, cold_accept=False, active=False, remaining=0, reset=False):
        if reset:
            self.phase, self.armed, self.tail = 0, False, False
        elif cold_accept:
            self.phase, self.armed, self.tail = 1, True, False
        elif self.armed:
            if self.phase == self.interval-1:
                self.tail = active and remaining != 0
            elif self.phase == self.rows-2:
                self.tail = False
            self.phase = 0 if self.phase == self.interval-1 else self.phase+1


def constants(g):
    interval = g['warm_interval']
    rows = g['n']//g['p']
    fifo = g['feedback_delay']-1
    assert fifo >= 0 and interval == g['first_digit']+1+fifo+1
    # correction enabled is latched by the actual digit-start. The first
    # modular boundary residue must precede that start or be the first real
    # boundary: this suppresses a false first-period correction proposal.
    boundary = g['boundary_output']+1
    residue = boundary % interval
    assert boundary < 2*interval and (boundary < interval or residue <= g['first_digit'])
    assert rows < interval and rows >= 2
    return interval, rows, boundary


def prove(g, counts=(1, 2, 17, 100, 1000)):
    interval, rows, boundary = constants(g)
    comparisons = 0
    # Enumerate only event neighborhoods, not billions of fake datapath edges.
    for count in counts:
        for ordinal in range(count):
            frame = ordinal*interval
            has_next = ordinal+1 < count
            for offset in (0, 1, rows-2, rows-1, interval-2, interval-1):
                age = frame+offset
                first = has_next and offset == interval-1
                tail = ordinal > 0 and offset < rows-1
                expected = (first or tail) and ordinal < count
                # The final frame also has the tail of its prior input.
                actual = ((has_next and offset == interval-1) or
                          (ordinal > 0 and offset < rows-1))
                assert actual == expected
                comparisons += 1
            for correction_ordinal in (ordinal,):
                age = correction_ordinal*interval+boundary
                phase = age % interval
                # Actual feedback_enabled belongs to this result until the
                # next result's digit-start; correction rows remain literal.
                assert phase == boundary % interval
                assert bool(has_next) == bool(correction_ordinal+1 < count)
                comparisons += 1
    # A free-running counter does not alias a 32/64-bit absolute host timer.
    for wraps in (1, 2, 3):
        age = wraps*(1 << 32)
        assert age % interval == (age+interval) % interval
    return dict(event_comparisons=comparisons, preedge_feedback_first=interval-1,
                ingress_accept=interval, boundary_preedge=boundary,
                latency_delta=0, external_backpressure_removed=False,
                descriptor_missing_at_due_is_fault=True,
                complete_payload_and_owner_transport_unchanged=True,
                cancel_is_not_numeric_pipeline_flush=True,
                healthy_calendar_model_only=True, native_qualified=False)
