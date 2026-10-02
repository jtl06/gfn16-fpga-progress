"""Compact bank row tags: exact source delta and Python address-age evidence.

This is not HDL elaboration, arithmetic validation, or physical timing evidence.
At AW16/L64, declared row/control storage changes from 8064 to 1232 bits per
field: eight preserved 16-bank groups, each with two seven-stage nine-bit rows,
seven three-bit pairing tags and seven orientation bits. Existing global
orientation_pipe still selects write data. Local orientation tags select rows.
All selectors are explicitly aged; the proof does not rely on stage stability.
Each final row bus serves at most16 banks. Reconstruction adds write-side logic;
fanout, packing, route success and timing must be measured after fitting.
"""
import hashlib
from pathlib import Path

ENGINE='genefer_ntt_banked27_prefetch_r2_orient8_engine'
HOST='genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_engine'
TOP='genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8'
ANCESTORS={
    ENGINE:'e6d524b36eb26f791617bbafdd440f18fe2ef0abe08aba3a26c9aa896b0ea138',
    HOST:'03a3c3183bace1ec37e6f9c81462ca4debe90625b093e054f71af55b050fd68d',
    TOP:'5e02a3d2795c3b554990092ce98e651b7b236ec07a59b2ffbb8e51f67c7215cd',
}
NAMES={ENGINE:ENGINE.replace('_engine','_rowcompact_engine'),
       HOST:HOST.replace('_engine','_rowcompact_engine'),TOP:TOP+'_rowcompact'}
OLD_DECLARE='    logic [RW-1:0] row_tag [0:6][0:BANKS-1];\n'
NEW_DECLARE='''    // Compact common rows, locally replicated for sixteen physical banks.
    // All row selectors describe the RAM read seven register edges earlier.
    // Preserved local tags bound write-row bus fanout without new latency.
    localparam int ROW_TAG_BANKS=16,ROW_TAG_GROUPS=(BANKS+ROW_TAG_BANKS-1)/ROW_TAG_BANKS;
    logic [RW-1:0] issue_row_base,issue_row_toggle;
    assign issue_row_base=state==BF_READ && issue_fire ? RW'(base_addr>>KW) :
                          state==MUL_READ && issue_fire ? RW'(point_base>>KW) : '0;
    assign issue_row_toggle=state==BF_READ && issue_fire ? RW'(stage_toggle_mask>>KW) : '0;
    for(genvar group=0;group<ROW_TAG_GROUPS;group=group+1) begin : row_tags
        (* preserve, dont_merge *) logic [RW-1:0] base_pipe [0:6],toggle_pipe [0:6];
        (* preserve, dont_merge *) logic [PW-1:0] pairing_pipe [0:6];
        (* preserve, dont_merge *) logic [6:0] orientation_pipe;
        always_ff @(posedge clk or negedge rst_n) begin
            if(!rst_n) begin
                orientation_pipe<=0;
                for(int t=0;t<7;t=t+1) begin
                    base_pipe[t]<=0;toggle_pipe[t]<=0;pairing_pipe[t]<=0;
                end
            end else begin
                base_pipe[0]<=issue_row_base;toggle_pipe[0]<=issue_row_toggle;
                pairing_pipe[0]<=pairing;orientation_pipe<={orientation_pipe[5:0],orientation};
                for(int t=1;t<7;t=t+1) begin
                    base_pipe[t]<=base_pipe[t-1];toggle_pipe[t]<=toggle_pipe[t-1];
                    pairing_pipe[t]<=pairing_pipe[t-1];
                end
            end
        end
    end
'''
OLD_RESET='            for(int t=0;t<7;t=t+1) for(int b=0;b<BANKS;b=b+1) row_tag[t][b]<=0;\n'
NEW_RESET=''
OLD_SHIFT='''            for(int b=0;b<BANKS;b=b+1) begin
                row_tag[0][b]<=data_ra[b];
                for(int t=1;t<7;t=t+1) row_tag[t][b]<=row_tag[t-1][b];
            end
'''
NEW_SHIFT=''
OLD_BF="                data_we[bank]=1;data_wa[bank]=row_tag[6][bank];data_w[bank]=bf_write_option[pairing];\n"
NEW_BF="""                data_we[bank]=1;
                data_wa[bank]=row_tags[bank/ROW_TAG_BANKS].base_pipe[6] |
                    ((1'(bank>>row_tags[bank/ROW_TAG_BANKS].pairing_pipe[6])^
                      row_tags[bank/ROW_TAG_BANKS].orientation_pipe[6]) ?
                     row_tags[bank/ROW_TAG_BANKS].toggle_pipe[6] : RW'(0));
                data_w[bank]=bf_write_option[pairing];
"""
OLD_MUL="                data_we[bank]=1;data_wa[bank]=row_tag[6][bank];data_w[bank]=product[bank%LANES];\n"
NEW_MUL="                data_we[bank]=1;data_wa[bank]=row_tags[bank/ROW_TAG_BANKS].base_pipe[6];data_w[bank]=product[bank%LANES];\n"
SHADOW='''    // synthesis translate_off
    // Native simulation compares every compute write against the original
    // per-bank address-age pipeline. This shadow is absent from synthesis.
    logic [RW-1:0] legacy_row_tag [0:6][0:BANKS-1];
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            for(int t=0;t<7;t=t+1) for(int b=0;b<BANKS;b=b+1) legacy_row_tag[t][b]<=0;
        end else begin
            for(int b=0;b<BANKS;b=b+1) begin
                legacy_row_tag[0][b]<=data_ra[b];
                for(int t=1;t<7;t=t+1) legacy_row_tag[t][b]<=legacy_row_tag[t-1][b];
                if(data_we[b] && (state==BF_READ || state==BF_DRAIN || state==MUL_READ || state==MUL_DRAIN) &&
                   data_wa[b]!==legacy_row_tag[6][b]) $fatal(1,"compact row write address mismatch");
            end
        end
    end
    // synthesis translate_on
'''

def require(ok,message):
    if not ok:raise ValueError(message)

def sha(text):return hashlib.sha256(text.encode()).hexdigest()

def once(text,old,new):
    require(text.count(old)==1,'ambiguous source anchor')
    return text.replace(old,new)

def expected(name,original):
    require(name in ANCESTORS and sha(original)==ANCESTORS[name],'frozen ancestor identity')
    text=once(original,'module '+name+' #(','module '+NAMES[name]+' #(')
    if name==ENGINE:
        for old,new in ((OLD_DECLARE,NEW_DECLARE),(OLD_RESET,NEW_RESET),
                        (OLD_SHIFT,NEW_SHIFT),(OLD_BF,NEW_BF),(OLD_MUL,NEW_MUL)):
            text=once(text,old,new)
        text=once(text,'    always_comb begin\n        root_read_count=0;',
                  SHADOW+'    always_comb begin\n        root_read_count=0;')
    else:
        child=ENGINE if name==HOST else HOST
        text=once(text,child+' #(',NAMES[child]+' #(')
    return text

def validate_files(root):
    kernel=Path(root)/'rtl/kernel';result={}
    for old,new in NAMES.items():
        actual=(kernel/(new+'.sv')).read_text()
        require(actual==expected(old,(kernel/(old+'.sv')).read_text()),'unreviewed compact-row delta: '+new)
        result['rtl/kernel/'+new+'.sv']=sha(actual)
    return result

def geometry(aw,lanes=64):
    require(type(aw) is int and 1<=aw<=16,'address width')
    require(type(lanes) is int and lanes in (1,2,4,8,16,32,64),'lane geometry')
    lw=lanes.bit_length()-1;kw=lw+1;rw=max(aw-kw,1)
    pw=max((kw-1).bit_length(),1)
    return kw,rw,pw

def storage_bits(aw,lanes=64):
    _,rw,pw=geometry(aw,lanes)
    groups=(2*lanes+15)//16
    return 7*2*lanes*rw,groups*7*(2*rw+pw+1)

def bank_of(address,aw,kw):
    result=0
    for j in range(aw):result^=((address>>j)&1)<<(j%kw)
    return result

def stage_base(group,stage,aw,kw):
    """Literal fixed_position/fixed_index mapping from the frozen engine."""
    result=0;source=0
    for j in range(aw):
        if j!=stage and not (j<kw and j!=stage%kw):
            result|=((group>>source)&1)<<j;source+=1
    return result

def literal_rows(aw,lanes,mode,fire,base,toggle,pairing,orientation,point_base,point_half,mul_lanes):
    kw,rw,_=geometry(aw,lanes);mask=(1<<rw)-1
    require(mode in ('BF','MUL','DRAIN','IDLE'),'mode')
    require(0<=pairing<kw and orientation in (0,1),'bank selectors')
    if mode=='BF' and fire:
        return [((base|(toggle if ((bank>>pairing)&1)^orientation else 0))>>kw)&mask
                for bank in range(2*lanes)]
    if mode=='MUL' and fire:
        return [((point_base>>kw)&mask) if bank//lanes==point_half and bank%lanes<mul_lanes else 0
                for bank in range(2*lanes)]
    return [0]*(2*lanes)

def common_rows(aw,lanes,mode,fire,base,toggle,point_base):
    kw,rw,_=geometry(aw,lanes);mask=(1<<rw)-1
    return (((base if mode=='BF' else point_base)>>kw)&mask if fire and mode in ('BF','MUL') else 0,
            (toggle>>kw)&mask if fire and mode=='BF' else 0)

def write_row(common,pairing,orientation,bank,kind):
    base,toggle=common
    return base|(toggle if ((bank>>pairing)&1)^orientation else 0) if kind=='BF' else base

def age_trace(aw,events,lanes=64,wrong_age=False,wrong_live_pairing=False):
    """Pre-edge write comparison followed by simultaneous seven-register shift.

    Accepted read at edge k occupies slot0 after k and slot6 after k+6.
    Its compute write is observed immediately before edge k+7. Pending entries
    are proof-only valid/selection tokens; RTL arithmetic still owns validity.
    Reset events model an asynchronous assertion that clears both tag pipelines
    and eligibility. DRAIN events shift without accepting a read.
    """
    geometry(aw,lanes)
    legacy=[[0]*(2*lanes) for _ in range(7)]
    common=[(0,0)]*7;pair=[0]*7;orient=[0]*7;pending=[None]*7
    comparisons=[]
    for edge,event in enumerate(events):
        if event.get('reset',False):
            legacy=[[0]*(2*lanes) for _ in range(7)]
            common=[(0,0)]*7;pair=[0]*7;orient=[0]*7;pending=[None]*7
            continue
        token=pending[6]
        if token is not None:
            kind,banks=token
            for bank in banks:
                index=5 if wrong_age else 6
                selected_pair=event.get('pairing',0) if wrong_live_pairing else pair[index]
                old=legacy[6][bank]
                new=write_row(common[index],selected_pair,orient[index],bank,kind)
                comparisons.append((edge,bank,old,new,kind))
        mode=event.get('mode','DRAIN');fire=event.get('fire',False)
        base=event.get('base',0);toggle=event.get('toggle',0);pairing=event.get('pairing',0)
        orientation=event.get('orientation',0);point=event.get('point_base',0)
        half=event.get('point_half',0);mul_lanes=event.get('mul_lanes',lanes)
        rows=literal_rows(aw,lanes,mode,fire,base,toggle,pairing,orientation,point,half,mul_lanes)
        shared=common_rows(aw,lanes,mode,fire,base,toggle,point)
        token=None
        if fire and mode=='BF':token=('BF',tuple(range(min(2*lanes,event.get('n',1<<aw)))))
        elif fire and mode=='MUL':token=('MUL',tuple(half*lanes+j for j in range(mul_lanes)))
        legacy=[rows]+legacy[:6];common=[shared]+common[:6]
        pair=[pairing]+pair[:6];orient=[orientation]+orient[:6];pending=[token]+pending[:6]
    return comparisons
