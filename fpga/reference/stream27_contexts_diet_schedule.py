"""Actual P16 serialized-correction two-context port/calendar contract.

Integer edge model only: no full-size arithmetic or fitted-resource claim.
The initial context offset is floor(I/2); per-context feedback still advances
by the FULL I, so odd periods alternate floor/ceil gaps rather than truncate.
"""
from . import stream27_shared_field_v5 as fields
from . import s4_two_context_model_v1 as ports

SELF='reference/stream27_contexts_diet_schedule.py'


def geometry(n=65536,p=16):
    ports.need(p==16 and n in (32,256,65536),'S4_CTX_DIET_GEOMETRY')
    g=dict(fields.geometry(n,p,corr_serial_bfs=2))
    g.update(carry_busy_edges=g['carry_done']-g['sink_accept']+1,contexts=2,
        lease_banks=4,main_owner_bits=25,term_owner_bits=27)
    return g


def schedule(n=65536,p=16,*,counts=(4,4),capacity=4):
    g=geometry(n,p);interval=g['warm_interval'];offset=interval//2
    ports.need(len(counts)==2 and all(type(c) is int and 1<=c<=16 for c in counts),
               'S4_CTX_DIET_BOUNDED_COUNTS')
    frames=sorted([ports.Frame(ctx,11+12*ctx,(65534+ordinal)&65535,ordinal,
        ordinal*interval+ctx*offset,(604832956,1000000000)[ctx])
        for ctx in range(2) for ordinal in range(counts[ctx])],key=lambda frame:frame.start)
    for label,key,width in (('INPUT',None,g['rows']),('PW','pointwise_accept',g['rows']),
                            ('SINK','sink_accept',g['rows']),('DIGIT','first_digit',g['rows']),
                            ('CARRY','sink_accept',g['carry_busy_edges'])):
        ports.disjoint([(f.start+(g[key] if key else 0),
            f.start+(g[key] if key else 0)+width-1,f.tag) for f in frames],label)
    correction=ports.correction_calendar(frames,g,pair_interval=g['correction_pair_interval'])
    feedback_peak=ports.feedback_queues(frames,g)
    # Real protocol allocation is lowest PRE-edge free, not epoch parity.
    live={};allocation=[];peak=0
    for frame in frames:
        live={bank:old for bank,old in live.items() if old.start+g['last_sink']>=frame.start}
        free=[bank for bank in range(capacity) if bank not in live]
        ports.need(bool(free),'S4_CTX_DIET_PREFREE_LEASE')
        bank=free[0];live[bank]=frame
        live={bank:old for bank,old in live.items() if old.start+g['last_sink']>frame.start}
        peak=max(peak,len(live));allocation.append(dict(context=frame.context,
            ordinal=frame.ordinal,start=frame.start,bank=bank))
    return dict(status='PASS_MODEL_ONLY',n=n,p=p,geometry=g,
        per_context_interval=interval,context_offset=offset,launch_gaps=[offset,interval-offset],
        frame_starts=[frame.start for frame in frames],correction=correction,
        lease_allocation=allocation,lease_peak=peak,feedback_peak_rows=feedback_peak,
        correction_pair_interval=g['correction_pair_interval'],full_N_numeric_performed=False,
        scope='Actual CORR_SERIAL2 port/cache and full-period feedback schedule; excludes host setup/canonical/copy/physical timing.')
