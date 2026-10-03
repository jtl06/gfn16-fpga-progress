"""Bounded scalar watchdog transition proof, never NTT/native qualification."""
from dataclasses import dataclass, field


@dataclass
class Watchdog:
    limit: int
    seen: list = field(default_factory=lambda: [0, 0])
    age: list = field(default_factory=lambda: [0, 0])
    error: list = field(default_factory=lambda: [False, False])

    def step(self, *, completed=(0, 0), new_job=(False, False), active=(True, True),
             demand=(True, True), aux_progress=(False, False), stop=(False, False), reset=False):
        if reset:
            self.seen, self.age, self.error = [0, 0], [0, 0], [False, False]
            return tuple(self.error)
        assert type(self.limit) is int and self.limit > 1
        for c in range(2):
            assert type(completed[c]) is int and 0 <= completed[c] <= 0xffffffff
            progress = completed[c] > self.seen[c]
            self.seen[c] = 0 if new_job[c] else completed[c]
            if new_job[c] or not active[c] or stop[c] or not demand[c] or progress or aux_progress[c]:
                self.age[c] = 0
            elif self.age[c] == self.limit - 1:
                self.error[c] = True
            else:
                self.age[c] += 1
        return tuple(self.error)


def old_falseabort():
    """Source-grounded reconstruction of the retained N256 R10 witness.

    The observed old trace had watchdog=1, local=0, age20479/limit20480,
    completed96/95 and started97/96 at host age20805. Last old progress325
    is inferred from the threshold, not a new measured trace.
    """
    limit, observed_age, last_old_progress = 20480, 20805, 325
    age = 0
    for edge in range(last_old_progress + 1, observed_age + 1):
        if age == limit - 1:
            break
        age += 1
    first, interval, carry = (204, 311), 214, 214
    started = [(observed_age - edge) // interval + 1 for edge in first]
    completed = [(observed_age - edge - carry - 1) // interval + 1 for edge in first]
    return dict(host_age=observed_age, watchdog_counter=age, limit=limit,
                started=started, completed=completed, watchdog=True, local_error=False,
                last_old_progress_inferred=last_old_progress, native_replay=False)


def repaired_same_trace():
    watch = Watchdog(20480)
    for edge in range(20806):
        completed = tuple(max(0, (edge - first - 215) // 214 + 1) for first in (204, 311))
        started = tuple(max(0, (edge - first) // 214 + 1) for first in (204, 311))
        watch.step(completed=completed, demand=tuple(started[c] > completed[c] for c in range(2)))
    return dict(error=watch.error, ages=watch.age, completed=watch.seen,
                counter_model_only=True, prior_native_PASS_inherited=False)
