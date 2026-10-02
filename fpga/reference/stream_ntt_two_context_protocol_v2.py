"""S5 protocol-only successor: immutable, uniquely identified job snapshots.

This is an untimed small-integer host oracle, not a two-context RTL controller.
The frozen event schedule and its geometry are neither imported as a timing
proof here nor modified. Python job IDs are unbounded; hardware wrap/reuse must
be proved separately. Initial field integration remains CONTEXTS=1.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path

from .stream_ntt_two_context_model import ContextBank
from .stream_ntt_model import ModelMismatch

FROZEN = {
    'reference/stream_ntt_two_context_model.py': '2d467bdcb1c2c254c2dc4af818e1ed10efdc979afdf147ee7c6bd00fed12dc9f',
    'reference/stream27_commutator_sync_model.py': '84fa950285704162ed1374bbf53c991abe390e17b21ce557a5a342ae332dd6c5',
    'tests/test_stream27_commutator_sync.py': '3e00ee0ee37bb7c1208e283a25752b0ef3dc76e81bacae59f830a41b74b90004',
}


def verify_sources():
    root = Path(__file__).resolve().parents[1]
    for name, digest in FROZEN.items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest() != digest:
            raise ValueError('S5 protocol prerequisite changed: '+name)
    return dict(FROZEN)


@dataclass(frozen=True)
class Job:
    context: int
    generation: int
    job_id: int
    base: int
    value: int
    double: int


class ProtocolBank(ContextBank):
    """One host-visible active transaction per context, unique across resets.

    Automatic epochs inside a continuously running chain are not modeled as
    overlapping host transactions. Context/base/generation/value/double are
    immutable snapshots; a completion must equal its entire active job.
    Stale, duplicate or altered snapshots are discarded without state changes.
    """
    def __init__(self, n=32, *, mutant=None):
        if mutant not in (None, 'same-generation-only', 'global-abort'):
            raise ValueError('unknown protocol mutation')
        super().__init__(n)
        self._next_job_id = 0
        self._active = [None, None]
        self._mutant = mutant

    @staticmethod
    def _check_context(ctx):
        if type(ctx) is not int or ctx not in (0,1):
            raise ValueError('explicit context0|1')

    def _idle(self, ctx):
        self._check_context(ctx)
        return super()._idle(ctx)

    def start(self, ctx, double=0):
        state = self._idle(ctx)
        if not state['valid'] or type(double) is not int or double not in (0,1):
            raise ModelMismatch('S5-start', str(ctx))
        job = Job(ctx, state['generation'], self._next_job_id,
                  state['base'], state['value'], double)
        self._next_job_id += 1
        self._active[ctx] = job
        state['busy'] = True
        return job

    def complete(self, job):
        if type(job) is not Job: raise TypeError('immutable Job required')
        self._check_context(job.context)
        ctx = job.context; state = self.contexts[ctx]
        if (not state['valid'] or not state['busy'] or
                job.generation != state['generation']):
            return False
        if self._mutant != 'same-generation-only' and job != self._active[ctx]:
            return False
        if job.base != state['base']:
            return False
        state.update(value=pow(job.value,2,job.base**self.n+1)*(1<<job.double) %
                     (job.base**self.n+1), busy=False)
        self._active[ctx] = None
        return True

    def abort(self, ctx):
        self._check_context(ctx)
        targets = (0,1) if self._mutant == 'global-abort' else (ctx,)
        for target in targets:
            super().abort(target)
            self._active[target] = None

    def reset_context(self, ctx):
        self.abort(ctx)

    def error(self, ctx):
        self.abort(ctx)


def stale_completion_control(*, mutant=False):
    """Direct reproduction of the reviewed v1 same-generation bug."""
    bank = ProtocolBank(mutant='same-generation-only' if mutant else None)
    bank.load(0,[3]*32,173)
    old = bank.start(0); assert bank.complete(old)
    current = bank.start(0,1)
    assert current.generation == old.generation and current.job_id > old.job_id
    snapshot = dict(bank.contexts[0])
    if bank.complete(old) or bank.contexts[0] != snapshot:
        raise ModelMismatch('S5-stale-completion', 'old same-generation job changed active slot')
    if not bank.complete(current):
        raise ModelMismatch('S5-current-completion', 'current job lost')
    return True


def abort_isolation_control(*, mutant=False):
    bank = ProtocolBank(mutant='global-abort' if mutant else None)
    bank.load(0,[3]*32,173); bank.load(1,[5]*32,1009)
    a = bank.start(0); b = bank.start(1,1)
    bank.abort(0)
    if bank.complete(a): raise ModelMismatch('S5-abort-stale', 'A accepted')
    if not bank.complete(b): raise ModelMismatch('S5-abort-leakage', 'B lost')
    expected = (sum(5*1009**i for i in range(32))**2*2) % (1009**32+1)
    if bank.read(1) != expected: raise ModelMismatch('S5-abort-leakage', 'B data')
    return True
