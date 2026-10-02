"""Executable r17 edge/lease contract, independent of numeric NTT execution.

Requests/physical slots are sampled using PRE-edge registered stop. A current
diagnostic fault does not gate them. Sticky failure is visible after that edge
and blocks the following sample. Intrinsic owner/live checks always qualify
terminal writes immediately, including the fault-origin edge.
"""
from dataclasses import dataclass

from .stream27_epoch_protocol_v3 import geometry


@dataclass
class Lease:
    epoch:int
    generation:int
    start:int
    base:int
    received:bool=False
    ready:bool=False


@dataclass(frozen=True)
class Edge:
    stopped_before:bool
    fault_pending:bool
    frame_accept:bool
    correction_accept:bool
    pointwise_accept:bool
    commit:bool
    error_after:bool
    owners_after:int


class Protocol:
    """Two image leases in ONE chain; no two-test/context interleave.

    begin=(epoch,generation,base), correction/ready=(epoch,generation),
    pw/sink=(generation,frame_start). Their epochs/rows are reconstructed from
    the registered exact frame calendar, exactly as the RTL boundary does.
    external_fault represents current admission/child/join diagnostics.
    """
    def __init__(self,n=256,epoch_bits=16):
        self.g=geometry(n);self.mask=(1<<epoch_bits)-1;self.reset()

    def reset(self):
        self.owners=[];self.next_epoch=None;self.error=False;self.origin=None

    def edge(self,tick,*,begin=None,correction=None,ready=None,pw=None,sink=None,
             external_fault=False,quarantine=False,enabled=True,live_generation=0,reset=False):
        if reset:
            self.reset();return Edge(False,False,False,False,False,False,False,0)
        stop=self.error or quarantine
        def find(tag):
            return next((o for o in self.owners if (o.epoch,o.generation)==tag),None)
        expected_pw=[(o,tick-o.start-self.g['pointwise_accept']) for o in self.owners
                     if 0<=tick-o.start-self.g['pointwise_accept']<self.g['rows']]
        expected_sink=[(o,tick-o.start-self.g['sink_accept']) for o in self.owners
                       if 0<=tick-o.start-self.g['sink_accept']<self.g['rows']]
        frame_ok=bool(begin is not None and len(self.owners)<2 and
            not any(o.epoch==begin[0] for o in self.owners) and
            (self.next_epoch is None or begin[0]==self.next_epoch))
        prospective=Lease(*begin[:2],tick,begin[2]) if begin is not None else None
        corr=find(correction) if correction is not None else None
        if corr is None and correction is not None and prospective is not None and len(self.owners)<2 and correction==begin[:2]:
            corr=prospective
        corr_ok=bool(corr is not None and not corr.received and
                     (corr is not prospective or frame_ok))
        cache=find(ready) if ready is not None else None
        cache_ok=bool(cache is not None and cache.received and not cache.ready)
        def slot_ok(actual,expected,require_ready=False):
            return bool(actual is not None and len(expected)==1 and
                actual==(expected[0][0].generation,expected[0][1]==0) and
                (not require_ready or expected[0][0].ready))
        pw_ok=slot_ok(pw,expected_pw,True);sink_ok=slot_ok(sink,expected_sink)
        bad=bool((begin is not None and not frame_ok) or
                 (correction is not None and not corr_ok) or
                 (ready is not None and not cache_ok) or
                 (bool(pw is not None)!=bool(expected_pw)) or
                 (pw is not None and not pw_ok) or
                 (bool(sink is not None)!=bool(expected_sink)) or
                 (sink is not None and not sink_ok) or
                 len(expected_pw)>1 or len(expected_sink)>1)
        frame_accept=frame_ok and not stop
        correction_accept=correction is not None and corr_ok and not stop
        pointwise_accept=pw_ok and not stop
        # Current unrelated faults DO NOT enter this immediate intrinsic cone.
        commit=sink_ok and not stop and enabled and sink[0]==live_generation
        pending=self.error or (not stop and (bad or external_fault))
        if not stop:
            if frame_accept:
                self.owners.append(prospective);self.next_epoch=(prospective.epoch+1)&self.mask
            if correction_accept:corr.received=True
            if ready is not None and cache_ok:cache.ready=True
            if sink_ok and expected_sink[0][1]==self.g['rows']-1:
                self.owners.remove(expected_sink[0][0])
            if bad or external_fault:
                self.error=True;self.origin=tick
        return Edge(stop,bool(pending),bool(frame_accept),bool(correction_accept),
                    bool(pointwise_accept),bool(commit),self.error,len(self.owners))


class FaultGate:
    """Small compositional origin/tail oracle; no arithmetic or HDL model."""
    def __init__(self):self.error=False
    def edge(self,*,occupied=False,current_fault=False,owner_match=True,
             generation_match=True,enabled=True,reset=False):
        if reset:self.error=False;return dict(advance=False,commit=False,error=False)
        advance=occupied and not self.error
        commit=advance and owner_match and generation_match and enabled
        if current_fault:self.error=True
        return dict(advance=advance,commit=commit,error=self.error)


def fault_calendar(n=65536):
    g=geometry(n)
    return dict(origin_edge='k: at most one occupied work/valid old commit edge',
                stop_edge='k+1: all future work/commit inhibited until reset',
                immediate_terminal_checks=['lease owner','physical first-row tag','enabled','live generation'],
                legal_cycle_delta=0,pointwise_accept=g['pointwise_accept'],
                first_commit=g['sink_accept'],last_commit=g['last_sink'],
                unsupported_profile_transport_lease_may_accept=True,
                fault_invalidates_partial_image=True,rollback=False,
                full_N_numeric_NTT_performed=False)
