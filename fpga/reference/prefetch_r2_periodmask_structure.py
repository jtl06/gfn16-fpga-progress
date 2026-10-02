"""Cached recurrence period mask: exact source and Python control evidence.

Standalone candidate on the frozen host-broadcast R2 baseline. No orient8,
root-fusion or row-compaction changes. No HDL or physical result is implied.
The existing 17-bit period register is replaced, at the same accepted-start
edge, by its 17-bit decremented mask. Arithmetic pipelines and latency stay
byte-identical. Moving subtraction to configuration may change physical
timing/fanout; only a later matched fit can establish its effect.
"""
import hashlib
from pathlib import Path

RECURRENCE='genefer_root_recurrence27'
ENGINE='genefer_ntt_banked27_prefetch_r2_engine'
HOST='genefer_ntt_banked27_prefetch_r2_host_broadcast_engine'
TOP='genefer_square_core27_stream_prefetch_r2_host_broadcast'
ANCESTORS={
    RECURRENCE:'c8adc265915192807efee46799a782f1649a4408313098baaed8b4a808afeb9e',
    ENGINE:'552d273972af97c3363b77df0798e08a962d283869bcc95159f378a0f0070b17',
    HOST:'0960922332ea919a72a1ee591a70006bba76af7f26bc5308b68f50e327583e29',
    TOP:'ea2b518880cb1c3191c71d35a232d2483aee82046ecd4d930d7ac7ffa07a80e1',
}
NAMES={RECURRENCE:RECURRENCE+'_periodmask',
       ENGINE:ENGINE.replace('_engine','_periodmask_engine'),
       HOST:HOST.replace('_engine','_periodmask_engine'),TOP:TOP+'_periodmask'}
BENCH='root_recurrence27.cpp'
NEW_BENCH='root_recurrence27_periodmask.cpp'
BENCH_SHA='3e98fcb127349740c9fc0368ef43d557af5ca879d37887afa865ca8722ddce90'
MASK=(1<<17)-1
LEGAL_PERIODS=(0,)+tuple(1<<bit for bit in range(17))
CHANGES=(
    ('logic [16:0] groups,repeat_period,issued,position;',
     'logic [16:0] groups,repeat_mask,issued,position;'),
    ("    assign position=repeat_period==0 ? issued : issued&(repeat_period-17'd1);",
     "    // Cache the 17-bit period-minus-one on accepted start; zero wraps to all ones.\n"
     "    assign position=issued&repeat_mask;"),
    ('groups<=0;repeat_period<=0;issued<=0;',"groups<=0;repeat_mask<=17'h1ffff;issued<=0;"),
    ('repeat_period<=config_period;active_lanes<=config_active_lanes;',
     "repeat_mask<=config_period-17'd1;active_lanes<=config_active_lanes;"),
)


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(text):return hashlib.sha256(text.encode()).hexdigest()


def once(text,old,new):
    require(text.count(old)==1,'ambiguous source anchor')
    return text.replace(old,new)


def expected(name,original):
    require(name in ANCESTORS and sha(original)==ANCESTORS[name],'frozen ancestor identity')
    text=once(original,'module '+name+' #(','module '+NAMES[name]+' #(')
    if name==RECURRENCE:
        for old,new in CHANGES:text=once(text,old,new)
    else:
        child={ENGINE:RECURRENCE,HOST:ENGINE,TOP:HOST}[name]
        text=once(text,child+' #(',NAMES[child]+' #(')
    return text


def expected_bench(original):
    require(sha(original)==BENCH_SHA,'frozen bench identity')
    require(original.count('V'+RECURRENCE)==2,'model name count')
    text=original.replace('V'+RECURRENCE,'V'+NAMES[RECURRENCE])
    return once(text,'                d.start=1;d.config_groups=0;d.config_active_lanes=0;d.config_step=TEST_P;',
        '                d.start=1;d.config_groups=0;d.config_active_lanes=0;d.config_step=TEST_P;\n'
        '                d.config_period=(elapsed&1) ? 0u : 131071u; // Busy configuration must not alter the cached mask.')


def validate_files(root):
    root=Path(root);result={}
    for old,new in NAMES.items():
        original=(root/'rtl/kernel'/(old+'.sv')).read_text()
        path='rtl/kernel/'+new+'.sv';actual=(root/path).read_text()
        require(actual==expected(old,original),'unreviewed period-mask delta: '+new)
        result[path]=sha(actual)
    actual=(root/'rtl/tb'/NEW_BENCH).read_text()
    require(actual==expected_bench((root/'rtl/tb'/BENCH).read_text()),'unreviewed component bench delta')
    result['rtl/tb/'+NEW_BENCH]=sha(actual)
    return result


def old_position(period,issued):
    require(type(period) is int and 0<=period<=MASK,'17-bit period')
    require(type(issued) is int and 0<=issued<=MASK,'17-bit issued')
    return issued if period==0 else issued&((period-1)&MASK)


def cached_mask(period):
    require(type(period) is int and 0<=period<=MASK,'17-bit period')
    return (period-1)&MASK


def config_valid(event,lanes=64,p=104857601):
    """Literal accepted-start predicate, with supplied per-bank seed validity."""
    groups=event.get('groups',8);period=event.get('period',0)
    active=event.get('active',lanes);step=event.get('step',1)
    if not (1<=groups<=65536 and 1<=active<=lanes and 0<=step<p and
            0<=period<=65536 and (period==0 or period&(period-1)==0)):
        return False
    contexts=min(4,groups,period or groups)
    valid=event.get('seed_valid',(0,0))[event.get('bank',0)]
    needed=sum(((1<<active)-1)<<(c*lanes) for c in range(contexts))
    return valid&needed==needed


def config_trace(events,lanes=64,p=104857601,wrong_busy_latch=False,wrong_zero_mask=False):
    """Control-only clock model: no Montgomery arithmetic or HDL simulation.

    Identical state transitions surround two distinct period representations.
    available/bypass inputs abstract the unchanged pipeline/context machinery.
    seed_valid is a supplied bank bitmap; arbitration and actual seed updates
    remain protected by the exact-source comparison, not modeled here.
    Samples include pre-edge position and readiness plus post-edge latches.
    """
    state='IDLE';period=0;mask=MASK;issued=groups=drain=bank=0;trace=[]
    for event in events:
        if event.get('reset',False):
            state='IDLE';period=0;mask=MASK;issued=groups=drain=bank=0
            trace.append(dict(reset=True,state=state,period=period,mask=mask,issued=issued))
            continue
        old=old_position(period,issued);new=issued&mask
        old_ready=state=='RUN' and issued<groups and (old<4 or event.get('available',False) or event.get('bypass',False))
        new_ready=state=='RUN' and issued<groups and (new<4 or event.get('available',False) or event.get('bypass',False))
        before=state;accepted=False;error=False;done=False
        if state=='IDLE' and event.get('start',False):
            if config_valid(event,lanes,p):
                accepted=True;period=event.get('period',0);mask=cached_mask(period)
                if wrong_zero_mask and period==0:mask=0
                issued=0;groups=event.get('groups',8);bank=event.get('bank',0);state='RUN'
            else:error=True;done=True
        elif state=='RUN' and old_ready and event.get('request',False):
            issued+=1
            if issued==groups:state='DRAIN';drain=4
        elif state=='DRAIN':
            drain-=1
            if drain==0:state='IDLE';done=True
        if wrong_busy_latch and before!='IDLE' and event.get('start',False):
            mask=cached_mask(event.get('period',0))
        trace.append(dict(reset=False,before=before,state=state,old_position=old,new_position=new,
            old_ready=old_ready,new_ready=new_ready,accepted=accepted,error=error,done=done,
            period=period,mask=mask,issued=issued,bank=bank))
    return trace
