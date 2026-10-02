"""Exact term-root/context contract; small event math, no numerical NTT.

Four contexts are necessary for the frozen four-stage Montgomery helper.
Full-N functions compute bounded32 seed vectors and11 factor constants only;
numeric event replay is restricted to N512 or smaller.
"""
from dataclasses import dataclass
from .stream_ntt_model import FIELDS,bit_reverse


def geometry(n):
    aw=n.bit_length()-1
    if n!=(1<<aw) or not 8<=aw<=16:raise ValueError('TERM_AW8_16')
    return aw,aw-3,n//8


def weight(n,field,row,lane):
    aw,tw,rows=geometry(n);p,g=FIELDS[field]
    if not 0<=row<rows or not 0<=lane<8:raise ValueError('TERM_ROOT_ADDRESS')
    psi=pow(g,(p-1)//(2*n),p);j=bit_reverse(lane,3)*rows+bit_reverse(row,tw)
    return pow(psi,2*j+1,p)*(1<<32)%p


def table_index(n,row):
    _,tw,rows=geometry(n)
    if not 0<=row<rows:raise ValueError('TERM_TABLE_ROW')
    return bit_reverse(row,tw)%8


def seed_vectors(n,field=0):
    _,tw,_=geometry(n)
    return tuple(tuple(weight(n,field,(segment<<(tw-3))|context,lane) for lane in range(8))
                 for segment in range(8) for context in range(4))


def factors(n,field=0):
    _,tw,_=geometry(n);width=tw-2;p,g=FIELDS[field];omega=pow(g,(p-1)//n,p)
    return tuple(pow(omega,-(1<<width)+3*(1<<(width-1-trailing)),p)*(1<<32)%p
                 for trailing in range(width))


def factor_index(row,n):
    _,tw,rows=geometry(n)
    if not 0<=row<rows-4:raise ValueError('TERM_UPDATE_END')
    group=row>>2;trailing=0
    while group&(1<<trailing):trailing+=1
    if trailing>=tw-2:raise ValueError('TERM_FACTOR_WRAP')
    return trailing


@dataclass
class Product:
    owner:tuple
    row:int
    values:tuple


def replay(n=512,field=0,*,coefficients=(0,7,0,19,31,0,11,1),seed_first=10,pw_first=50,
           drop_bypass=False,retain_old_coefficient=False,wrong_factor=False,cancel_at=None):
    """Pre-edge reads and next-edge captures, including all four contexts.

    Pointwise term output is registered for AddB one edge after AddA. Matured
    products are available as bypass before the same edge writes their cache.
    Cancellation never changes occupied transport or recurrence scheduling.
    """
    if n>512:raise ValueError('TERM_LOCAL_EVENT_N512_LIMIT')
    _,tw,rows=geometry(n);p,_=FIELDS[field];rinv=pow(1<<32,-1,p)
    mont=lambda a,b:a*b*rinv%p
    owner=(0,3);pending={};cache=[None]*4;tags=[None]*4;out=[];seed=seed_vectors(n,field)
    factor=factors(n,field);seams=feedback=bypasses=commits=0
    for tick in range(pw_first+rows+4):
        matured=pending.pop(tick,None)
        row=tick-pw_first
        if 0<=row<rows:
            ctx=row&3;value=cache[ctx]
            if matured is not None and matured.owner==owner and matured.row==row and not drop_bypass:
                value=matured.values;bypasses+=1
            elif tags[ctx]!=(owner,row):raise AssertionError('TERM_CACHE_TARGET_PREEDGE')
            expected=tuple(mont(coefficients[table_index(n,row)]%p,weight(n,field,row,lane)) for lane in range(8))
            if value!=expected:raise AssertionError('TERM_DIRECT_WEIGHT_MISMATCH')
            out.append(value)
            if cancel_at is None or tick<cancel_at:commits+=1
            target=row+4
            if target<rows:
                changed=table_index(n,target)!=table_index(n,row)
                if changed and not retain_old_coefficient:
                    segment=target>>(tw-3);rhs=seed[segment*4+(target&3)]
                    product=tuple(mont(coefficients[table_index(n,target)]%p,root) for root in rhs);seams+=1
                else:
                    root=factor[factor_index(row,n)]
                    if wrong_factor:root=factor[(factor_index(row,n)+1)%len(factor)]
                    product=tuple(mont(term,root) for term in value);feedback+=1
                if tick+4 in pending:raise AssertionError('TERM_SEED_UPDATE_COLLISION')
                pending[tick+4]=Product(owner,target,product)
        seedrow=tick-seed_first
        if 0<=seedrow<4:
            if tick+4 in pending:raise AssertionError('TERM_SEED_UPDATE_COLLISION')
            pending[tick+4]=Product(owner,seedrow,tuple(mont(coefficients[table_index(n,seedrow)]%p,root)
                                                       for root in seed[seedrow]))
        # Same-edge capture cannot satisfy the read above without the bypass.
        if matured is not None:
            cache[matured.row&3]=matured.values;tags[matured.row&3]=(matured.owner,matured.row)
    return dict(rows=rows,output=tuple(out),reseed_products=seams,feedback_products=feedback,
                bypass_reads=bypasses,commits=commits,pending_products=len(pending),
                full_N_numeric_NTT_performed=False)


def production_calendar(n=65536):
    from .stream27_epoch_protocol_v3 import geometry as field_geometry
    aw,tw,rows=geometry(n);g=field_geometry(n)
    old_pw_last=g['pointwise_accept']+rows-1
    new_correction=g['next_correction_accept'];seed_window=(new_correction+29,new_correction+32)
    return dict(n=n,contexts_per_lane=4,banks=2,owner_bits=24,product_tag_bits=24+tw,
        seed_vector_words=32,seed_vector_width=216,factor_words=tw-2,
        update_accept_to_registered_product=3,update_accept_to_same_edge_capture_and_bypass=4,
        first_epoch_pointwise_window=(g['pointwise_accept'],old_pw_last),
        next_correction_accept=new_correction,next_seed_window=seed_window,
        single_producer_seed_update_overlap=not(seed_window[0]>old_pw_last),
        interval=g['interval'],
        seed_update_arbitration=f"Any seed/update collision faults; declared{g['interval']}-edge calendar has no collision.",
        pointwise_term_registered_for_second_add=True,complete_warm_field_source_ready=False)
