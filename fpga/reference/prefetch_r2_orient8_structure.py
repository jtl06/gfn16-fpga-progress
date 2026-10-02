"""Isolated orientation-driver replication: source/control-model evidence only.

No HDL compile/simulation, whole-core qualification, or physical benefit is
claimed. One old orientation_d register is replaced by ceil(LANES/8) drivers
with the same predecessor, edge, asynchronous reset and unconditional update.
All arithmetic/masks/counters and orientation_pipe writeback tags are unchanged.
Logical register delta is ceil(LANES/8)-1 per field (+21 for three L64 fields).
No RTL LUT mux, DSP or RAM is added or removed; placed resources need measurement.
"""
import hashlib
from pathlib import Path

ANCESTORS={
    'genefer_ntt_banked27_prefetch_r2_engine':'552d273972af97c3363b77df0798e08a962d283869bcc95159f378a0f0070b17',
    'genefer_ntt_banked27_prefetch_r2_host_broadcast_engine':'0960922332ea919a72a1ee591a70006bba76af7f26bc5308b68f50e327583e29',
    'genefer_square_core27_stream_prefetch_r2_host_broadcast':'ea2b518880cb1c3191c71d35a232d2483aee82046ecd4d930d7ac7ffa07a80e1',
}
NAMES={
    'genefer_ntt_banked27_prefetch_r2_engine':'genefer_ntt_banked27_prefetch_r2_orient8_engine',
    'genefer_ntt_banked27_prefetch_r2_host_broadcast_engine':'genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_engine',
    'genefer_square_core27_stream_prefetch_r2_host_broadcast':'genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8',
}
CANDIDATE_PINS={
    'genefer_ntt_banked27_prefetch_r2_orient8_engine':'e6d524b36eb26f791617bbafdd440f18fe2ef0abe08aba3a26c9aa896b0ea138',
    'genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_engine':'03a3c3183bace1ec37e6f9c81462ca4debe90625b093e054f71af55b050fd68d',
    'genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8':'5e02a3d2795c3b554990092ce98e651b7b236ec07a59b2ffbb8e51f67c7215cd',
}
PATTERN_NAME='genefer_ntt_banked27_tiled_engine'
PATTERN_SHA='d3dbaa6fe626e7e926b589f92b84959381b6c7aff74cb21a2d9f1d8d25353af0'
ENGINE='genefer_ntt_banked27_prefetch_r2_engine'
HOST='genefer_ntt_banked27_prefetch_r2_host_broadcast_engine'
TILE_BLOCK='''    // Same-edge replicas: eight arithmetic lanes per driver, no new latency.
    localparam int ORIENT_TILE_LANES=8,ORIENT_TILES=(LANES+ORIENT_TILE_LANES-1)/ORIENT_TILE_LANES;
    for(genvar tile=0;tile<ORIENT_TILES;tile=tile+1) begin : orientation_tiles
        (* preserve, dont_merge *) logic orientation_q;
        always_ff @(posedge clk or negedge rst_n) begin
            if(!rst_n) orientation_q<=0;
            else orientation_q<=orientation;
        end
    end
'''


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(text):return hashlib.sha256(text.encode()).hexdigest()


def once(text,old,new):
    require(text.count(old)==1,'ambiguous source anchor: '+old)
    return text.replace(old,new)


def expected(name,original):
    require(name in ANCESTORS and sha(original)==ANCESTORS[name],'frozen ancestor identity')
    text=once(original,'module '+name+' #(','module '+NAMES[name]+' #(')
    if name==ENGINE:
        text=once(text,'logic orientation,orientation_d,point_half,point_half_d,low_stage_d;',
                       'logic orientation,point_half,point_half_d,low_stage_d;')
        anchor='    for(genvar lane=0;lane<LANES;lane=lane+1) begin : arithmetic'
        text=once(text,anchor,TILE_BLOCK+anchor)
        for word in ('u','v'):
            text=once(text,'assign '+word+'=orientation_d ?',
                'assign '+word+'=orientation_tiles[lane/ORIENT_TILE_LANES].orientation_q ?')
        text=once(text,'orientation_d<=0;point_half_d<=0;','point_half_d<=0;')
        text=once(text,'orientation_d<=orientation;point_half_d<=point_half;','point_half_d<=point_half;')
    else:
        child=ENGINE if name==HOST else HOST
        text=once(text,child+' #(',NAMES[child]+' #(')
    return text


def validate_files(root):
    kernel=Path(root)/'rtl/kernel'
    pattern=(kernel/(PATTERN_NAME+'.sv')).read_text()
    require(sha(pattern)==PATTERN_SHA and '(* preserve, dont_merge *) logic orientation_e;' in pattern,
            'existing preserved/nonmerged pattern identity')
    result={}
    for old,new in NAMES.items():
        actual=(kernel/(new+'.sv')).read_text()
        require(actual==expected(old,(kernel/(old+'.sv')).read_text()),'unreviewed orientation delta: '+new)
        require(sha(actual)==CANDIDATE_PINS[new],'candidate identity')
        result['rtl/kernel/'+new+'.sv']=sha(actual)
    return result


def control_trace(actions,lanes,wrong_one_cycle=False):
    """Abstract FF transition model, not elaboration or RTL simulation.

    edge0/edge1 sample the predecessor; assert/release model asynchronous reset.
    Returns the original selector and each physical-tile selector after events.
    The deliberately wrong alternative samples the previous registered value.
    """
    require(type(lanes) is int and lanes in (1,2,4,8,16,32,64),'supported geometry')
    count=(lanes+7)//8
    reset=False;original=0;copies=[0]*count;trace=[]
    for action in actions:
        require(action in ('edge0','edge1','assert','release'),'control event')
        if action=='assert':reset=True;original=0;copies=[0]*count
        elif action=='release':reset=False
        else:
            source=int(action[-1]);before=original
            original=0 if reset else source
            copies=[0 if reset else before if wrong_one_cycle else source]*count
        trace.append((original,tuple(copies)))
    return trace
