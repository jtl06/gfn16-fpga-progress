"""Repair integer CLI parameter binding without waiving any width diagnostic."""
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PINS={
 'rtl/kernel/genefer_track_a_trunk_v1.sv':'2908d3babfc01d985e6351303cda5559565f1d4fb210bb0bb25e465e2e0b6ff0',
 'rtl/tb/track_a_trunk_flags_off_probe_v1.sv':'1776385426d96e8de64a93b6419206dff4623361459c40b71c277cc7053a7f18',
 'rtl/tb/track_a_trunk_flags_off_normal_v1.cpp':'117c6938c539c7c498fcdd32d767a7f82bbd25850d068f05e7628cccb5e7e686',
 'rtl/tb/track_a_trunk_flags_off_threaded_v1.cpp':'ae9ba9d82defd4048f847c9102a1cf3b923f0393a2a7df899b04bf1d837ce947',
 'rtl/tb/track_a_trunk_block_v1.cpp':'14b75d5e95a433637b804fc0e8f9de989cf5fa95c00bef464a8bdc8524811dee',
 'rtl/tb/track_a_trunk_merged_v1.cpp':'14b75d5e95a433637b804fc0e8f9de989cf5fa95c00bef464a8bdc8524811dee'}
def expected():
    result={}
    for name,pin in PINS.items():
        raw=(ROOT/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('frozen selector predecessor drift')
        text=raw.decode()
        for old in ('genefer_track_a_trunk_v1','track_a_trunk_flags_off_probe_v1','track_a_trunk_flags_off_normal_v1'):
            text=text.replace(old,old[:-2]+'v2')
        if name.endswith('.sv') and '/kernel/' in name:
            for flag in ('USE_BLOCKCARRY','USE_MERGED_TWIST','USE_ROOT_LOOKAHEAD'):
                text=text.replace('parameter bit '+flag,'parameter int '+flag)
            changes={
              'if(USE_ROOT_LOOKAHEAD)':'if(USE_ROOT_LOOKAHEAD!=0)',
              'if(USE_MERGED_TWIST && !USE_BLOCKCARRY)':'if(USE_MERGED_TWIST!=0 && USE_BLOCKCARRY==0)',
              'if(USE_BLOCKCARRY &&':'if(USE_BLOCKCARRY!=0 &&',
              'assign host_abi=USE_BLOCKCARRY;':'assign host_abi=(USE_BLOCKCARRY!=0);',
              'if(!USE_BLOCKCARRY)':'if(USE_BLOCKCARRY==0)',
              'if(USE_MERGED_TWIST)':'if(USE_MERGED_TWIST!=0)'}
            for old,new in changes.items():
                if text.count(old)!=1:raise ValueError('finite selector expression delta '+old)
                text=text.replace(old,new)
            text=text.replace('    initial begin','    initial begin\n        if((USE_BLOCKCARRY!=0 && USE_BLOCKCARRY!=1) ||\n           (USE_MERGED_TWIST!=0 && USE_MERGED_TWIST!=1) ||\n           (USE_ROOT_LOOKAHEAD!=0 && USE_ROOT_LOOKAHEAD!=1))\n            $fatal(1,"A_TRUNK_BOOLEAN_FLAG_REQUIRED");',1)
        result[name.replace('_v1.','_v2.')]=text
    return result

def verify():
    for name,text in expected().items():
        if (ROOT/name).read_text()!=text:raise ValueError('unexpected selector successor delta '+name)
    return dict(status='PASS_source_delta_only',arithmetic_changes=0,flag_values=[0,1],native_validated=False)
