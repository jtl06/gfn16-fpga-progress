"""Root clipping fused into XOR dimensions; source/model proof, not HDL validation.

The six L64 mux dimensions now select a source bit of zero when clipped,
or lane_bit XOR route_bit otherwise. No registers, masks, tags or cycles change.
This removes the preceding variable-index root mux in RTL; fitted resource and
timing effects must be measured, not inferred from this abstract network.
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
NAMES={ENGINE:ENGINE.replace('_engine','_rootfused_engine'),
       HOST:HOST.replace('_engine','_rootfused_engine'),TOP:TOP+'_rootfused'}
OLD='''    // The recurrence outputs logical seed lanes. Clip early-stage reuse,
    // then XOR into physical arithmetic lane order (proved independently).
    logic [KW-1:0] route_xor;
    logic [LW:0] point_bank_d;
    assign route_xor=active_op==0 ? (low_stage_d ? base_bank_d :
        KW'(remove_bit(int'(base_bank_d),int'(pairing_d)))) : KW'(point_bank_d);
    for(genvar d=0;d<=LW;d=d+1)begin: generated_route
        logic [31:0] words[0:LANES-1];
        for(genvar j=0;j<LANES;j=j+1)begin: lanes
            if(d==0)assign words[j]=(active_op==0 && low_stage_d) ?
                generated_roots[(j&((1<<stage_bit_d)-1))*32+:32] : generated_roots[j*32+:32];
            else assign words[j]=route_xor[d-1] ? generated_route[d-1].words[j^(1<<(d-1))] :
                                                           generated_route[d-1].words[j];
        end
    end
'''
NEW='''    // Fuse early-stage root reuse into the existing XOR dimensions.
    // Source index = (lane XOR route_xor) AND root_lane_mask.
    // Constant-index seed inputs; no extra register, latency or data mux layer.
    logic [KW-1:0] route_xor,root_lane_mask;
    logic [LW:0] point_bank_d;
    assign root_lane_mask=(active_op==0 && low_stage_d) ?
        KW'((32'd1<<stage_bit_d)-32'd1) : {KW{1'b1}};
    assign route_xor=active_op==0 ? (low_stage_d ? base_bank_d :
        KW'(remove_bit(int'(base_bank_d),int'(pairing_d)))) : KW'(point_bank_d);
    for(genvar d=0;d<=LW;d=d+1)begin: generated_route
        logic [31:0] words[0:LANES-1];
        for(genvar j=0;j<LANES;j=j+1)begin: lanes
            if(d==0)assign words[j]=generated_roots[j*32+:32];
            else begin : fused_clip_xor
                logic select_neighbor;
                if((j&(1<<(d-1)))==0)
                    assign select_neighbor=root_lane_mask[d-1] & route_xor[d-1];
                else
                    assign select_neighbor=~root_lane_mask[d-1] | route_xor[d-1];
                assign words[j]=select_neighbor ? generated_route[d-1].words[j^(1<<(d-1))] :
                                                 generated_route[d-1].words[j];
            end
        end
    end
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
    if name==ENGINE:text=once(text,OLD,NEW)
    else:
        child=ENGINE if name==HOST else HOST
        text=once(text,child+' #(',NAMES[child]+' #(')
    return text

def validate_files(root):
    kernel=Path(root)/'rtl/kernel';result={}
    for old,new in NAMES.items():
        actual=(kernel/(new+'.sv')).read_text()
        require(actual==expected(old,(kernel/(old+'.sv')).read_text()),'unreviewed root-fusion delta: '+new)
        result['rtl/kernel/'+new+'.sv']=sha(actual)
    return result

def routes(lanes,stage,op,low_stage,route):
    """Compare literal clip-then-XOR network with fused neighbor network.

    Values are unique source-lane labels, so equality proves arbitrary payload
    routing. This is Python model evidence, not an HDL simulation.
    """
    require(type(lanes) is int and lanes in (1,2,4,8,16,32,64),'lanes')
    require(type(stage) is int and 0<=stage<32,'stage')
    require(type(op) is int and op in range(4),'op')
    require(type(low_stage) is bool,'low_stage')
    require(type(route) is int and 0<=route<2*lanes,'route')
    mask=(1<<stage)-1 if op==0 and low_stage else lanes-1
    old=[j&mask for j in range(lanes)];new=list(range(lanes))
    for d in range(lanes.bit_length()-1):
        bit=1<<d;keep=bool(mask&bit);flip=bool(route&bit)
        old=[old[j^bit] if flip else old[j] for j in range(lanes)]
        new=[new[j^bit] if ((keep and flip) if not j&bit else (not keep or flip))
             else new[j] for j in range(lanes)]
    formula=[(j^(route&(lanes-1)))&mask for j in range(lanes)]
    return old,new,formula
