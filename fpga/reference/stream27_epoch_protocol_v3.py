"""Production warm-field epoch/deadline protocol, geometry-only at full N.

Two frame descriptors own late correction messages and terminal residue rows.
Epochs are reconstructed from physical frame order, not silently added to every
delay-RAM word. That specialization still requires composed native proof.
"""
from dataclasses import dataclass

from .stream27_field_plan import field_contract


def geometry(n=65536):
    contract=field_contract(n)['cycle_model']
    rows=n//8;interval=contract['dependent_whole_square_interval_conditional']
    first_pw=contract['first_forward_X_output']+1
    first_sink=contract['first_field_residue_output']+1
    boundary=interval+rows
    cache=boundary+37  # raw boundary -> signed/smallDFT/fourseed registered cache
    next_pw=interval+first_pw
    return dict(n=n,rows=rows,interval=interval,pointwise_accept=first_pw,
                sink_accept=first_sink,last_sink=first_sink+rows-1,
                next_raw_boundary=boundary,next_correction_accept=boundary+1,
                next_cache_capture=cache,next_pointwise_accept=next_pw,
                correction_margin_after_cache_register=next_pw-cache-1,
                cache_latency_after_raw_accept=36,
                minimum_stall_required=max(0,cache+1-next_pw),
                max_inflight_descriptors=2,
                epoch_RAM_bits_added=0,epoch_regeneration_native_proved=False)


@dataclass
class Owner:
    epoch:int
    generation:int
    start:int
    correction_received:bool=False
    cache_ready:bool=False
    cache_edge:int|None=None


class Protocol:
    def __init__(self,n=65536,epoch_bits=16):
        self.g=geometry(n);self.mask=(1<<epoch_bits)-1
        if epoch_bits<2:raise ValueError('EPOCH_WIDTH_MIN2')
        self.reset()

    def reset(self):
        self.owners=[];self.next_epoch=None;self.error=None;self.pw_count=0;self.sink_count=0
        self.commits=0;self.peak_owners=0

    def edge(self,tick,*,begin=None,correction=None,ready=None,pw=None,sink=None,
             enabled=True,live_generation=0,reset=False):
        """pw/sink are (epoch,generation,physical_row), not eligible rows.

        A cache-ready register written at this edge cannot satisfy a pointwise
        consumer on the same edge. Every expected physical row is mandatory,
        including canceled owners. First failure quarantines until reset.
        """
        if reset:self.reset();return False
        if self.error:return False
        def fail(code):
            self.error=f'{code} edge={tick}'
        def lookup(tag):
            candidates=[o for o in self.owners if (o.epoch,o.generation)==tag]
            if len(candidates)!=1:fail('EPOCH_OWNER_MISSING');return None
            return candidates[0]
        if begin is not None:
            epoch,gen=begin
            if epoch&~self.mask or not 0<=gen<256:fail('EPOCH_INPUT_RANGE')
            elif self.next_epoch is not None and epoch!=self.next_epoch:fail('EPOCH_SEQUENCE')
            elif len(self.owners)>=2 or any(o.epoch==epoch for o in self.owners):fail('EPOCH_BUSY_REUSE')
            else:
                self.owners.append(Owner(epoch,gen,tick));self.next_epoch=(epoch+1)&self.mask
                self.peak_owners=max(self.peak_owners,len(self.owners))
        if self.error:return False
        expected_pw=[(o,tick-o.start-self.g['pointwise_accept']) for o in self.owners
                     if 0<=tick-o.start-self.g['pointwise_accept']<self.g['rows']]
        expected_sink=[(o,tick-o.start-self.g['sink_accept']) for o in self.owners
                       if 0<=tick-o.start-self.g['sink_accept']<self.g['rows']]
        if len(expected_pw)>1 or len(expected_sink)>1:fail('EPOCH_CHANNEL_OVERLAP')
        def check(actual,expected,kind):
            if bool(actual)!=bool(expected):fail('EPOCH_'+kind+'_CADENCE');return None
            if actual:
                owner,row=expected[0]
                if actual!=(owner.epoch,owner.generation,row):fail('EPOCH_'+kind+'_OWNER');return None
                return owner
            return None
        pw_owner=check(pw,expected_pw,'POINTWISE')
        sink_owner=check(sink,expected_sink,'SINK')
        if pw_owner and not pw_owner.cache_ready:fail('EPOCH_CORRECTION_DEADLINE')
        ready_owner=lookup(ready) if ready is not None else None
        received_before=bool(ready_owner and ready_owner.correction_received)
        if correction is not None:
            owner=lookup(correction)
            if owner:
                if owner.correction_received:fail('EPOCH_DUPLICATE_CORRECTION')
                else:owner.correction_received=True
        if ready is not None:
            owner=ready_owner
            if owner:
                if not received_before or owner.cache_ready:fail('EPOCH_CACHE_ORDER')
                else:owner.cache_ready=True;owner.cache_edge=tick
        commit=bool(sink_owner and enabled and sink_owner.generation==live_generation and not self.error)
        if not self.error:
            self.pw_count+=int(pw_owner is not None);self.sink_count+=int(sink_owner is not None)
            self.commits+=int(commit)
            if sink_owner and expected_sink[0][1]==self.g['rows']-1:self.owners.remove(sink_owner)
        return commit


def scenario(n=65536,frames=4,*,extra_cache_delay=0,cancel_at=None,epoch_bits=16,first_epoch=0,
             wrong_correction=False,drop_canceled=False):
    """Geometry/event execution only: no numeric transform or coefficient work."""
    g=geometry(n);p=Protocol(n,epoch_bits);inputs={};corrections={};cache={};pw={};sink={}
    mask=(1<<epoch_bits)-1
    for f in range(frames):
        start=f*g['interval'];tag=((first_epoch+f)&mask,0);inputs[start]=tag
        corr=start if f==0 else (f-1)*g['interval']+g['next_correction_accept']
        corrections[corr]=(tag[0],1) if wrong_correction and f==1 else tag
        cache[corr+36+extra_cache_delay]=tag
        for row in range(g['rows']):
            pw[start+g['pointwise_accept']+row]=(*tag,row)
            sink[start+g['sink_accept']+row]=(*tag,row)
    end=(frames-1)*g['interval']+g['last_sink']+2
    for tick in range(end):
        live=int(cancel_at is not None and tick>=cancel_at)
        occupied_pw=pw.get(tick);occupied_sink=sink.get(tick)
        if drop_canceled and live:occupied_pw=None;occupied_sink=None
        p.edge(tick,begin=inputs.get(tick),correction=corrections.get(tick),ready=cache.get(tick),
               pw=occupied_pw,sink=occupied_sink,live_generation=live)
        if p.error:break
    return dict(geometry=g,error=p.error,peak_owners=p.peak_owners,pointwise_rows=p.pw_count,
                sink_rows=p.sink_count,commits=p.commits,owners_remaining=len(p.owners),
                full_N_numeric_NTT_performed=False)
