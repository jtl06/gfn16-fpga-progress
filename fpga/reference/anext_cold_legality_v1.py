"""Isolated F3 cold numeric-check retiming; no arithmetic/warm-cycle delta.

The source register keeps signed33, then rejects before truncation/reduction.
Raw metadata/image/transfer errors and cancel are not delayed. Numeric failure
is one edge later; an older legal prefix is speculative until whole completion.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PARENT='rtl/kernel/genefer_track_a4_cold_prefill_v1.sv'
BACKEND_PARENT='rtl/kernel/genefer_anext_writeback_square_backend_v1.sv'
CORE_PARENT='rtl/kernel/genefer_anext_writeback_core_v1.sv'
CONTROL='rtl/kernel/genefer_track_a4_control_fsm_v2.sv'
TARGET='rtl/kernel/genefer_anext_cold_prefill_sourcecheck_v1.sv'
BACKEND='rtl/kernel/genefer_anext_coldleg_backend_v1.sv'
CORE='rtl/kernel/genefer_anext_coldleg_core_v1.sv'
PINS={PARENT:'100dd9241023a301df0f161f7039dfdf15b364161b16b085fe841e9507bc1988',
 BACKEND_PARENT:'47cfcc569d8eb152cfeeb74b8346fa78d379aa01f6233bc9510b6f3d897fe9ad',
 CORE_PARENT:'04fe3faa490c83395cec936c40cad15644885ddfd83f008b9f8d7e27da9f8fc9',
 CONTROL:'343d392e1b69f4230e3a59029aafd3355e8139b502589ff56c7b1fbe1bf49d03'}

def sha(raw):return hashlib.sha256(raw).hexdigest()
def need(ok,why):
    if not ok:raise ValueError(why)
def once(t,a,b):
    need(t.count(a)==1,'COLDLEG_SINGLE_SITE '+a[:80]);return t.replace(a,b)
def literal(t,changes):
    before=t
    for a,b in changes:t=once(t,a,b)
    back=t
    for a,b in reversed(changes):back=once(back,b,a)
    need(back==before,'COLDLEG_REVERSIBLE_DELTA');return t
def guard():
    for n,p in PINS.items():need(sha((ROOT/n).read_bytes())==p,'COLDLEG_FROZEN_PARENT '+n)
    control=(ROOT/CONTROL).read_text();backend=(ROOT/BACKEND_PARENT).read_text()
    need('bus.image_valid<=0;bus.prefill_valid<=0;bus.fault_sticky<=1;' in control and
         'setup_valid<=0;loading<=0;canonical<=0;bus.cancel<=1;' in control and
         'else if(!bus.image_valid || !setup_valid || bus.fault_sticky)fail' in control,
         'COLDLEG_PUBLIC_FAILURE_RELOAD_BARRIER')
    need('COLD_WAIT:if(prefill_done)state<=NTT_START;' in backend and
         'wire fault=seq_error || post_error || prefill_error || transfer_error || compute_memory_error' in backend and
         'if(fault || raw_admission_fault)begin ntt_admission<=0;state<=FAILED;' in backend,
         'COLDLEG_NO_NTT_ON_BAD_PREFILL')

def changes():return (
 ('// Canonical image -> ordinary three-field residues. No numeric NTT here.',
  '// Cold-legality successor: full signed33 source capture, then check before destination/reduction.'),
 ('module genefer_track_a4_cold_prefill_v1','module genefer_anext_cold_prefill_sourcecheck_v1'),
 ('    logic [511:0] source_words,destination_words;',
  '    logic [527:0] source_words;\n    logic [511:0] destination_words;'),
 ('if($signed(image_read_words[lane*33+:33]) < -33\'sd1 ||\n               $signed(image_read_words[lane*33+:33]) >= $signed({1\'b0,base_reg}))input_legal=0;',
  'if($signed(source_words[lane*33+:33]) < -33\'sd1 ||\n               $signed(source_words[lane*33+:33]) >= $signed({1\'b0,base_reg}))input_legal=0;'),
 ('(image_read_valid && (!input_legal || image_read_tag_out!=due_tag ||',
  '(image_read_valid && (image_read_tag_out!=due_tag ||'),
 ('            (reduced_valid!=0 && !(&reduced_valid)) ||',
  '            // Numeric failure is local to the captured source token, before truncation.\n'
  '            (capture_valid[0] && !input_legal) ||\n'
  '            (reduced_valid!=0 && !(&reduced_valid)) ||'),
 ('        if(image_read_valid && input_legal)\n            for(int lane=0;lane<16;lane=lane+1)source_words[lane*32+:32]<=image_read_words[lane*33+:32];\n'
  '        if(capture_valid[0])destination_words<=source_words;',
  '        if(image_read_valid)source_words<=image_read_words;\n'
  '        if(capture_valid[0])\n'
  '            for(int lane=0;lane<16;lane=lane+1)destination_words[lane*32+:32]<=source_words[lane*33+:32];'))

def expected():
    guard();cold=literal((ROOT/PARENT).read_text(),changes())
    backend=literal((ROOT/BACKEND_PARENT).read_text(),(
      ('module genefer_anext_writeback_square_backend_v1','module genefer_anext_coldleg_backend_v1'),
      ('genefer_track_a4_cold_prefill_v1 #','genefer_anext_cold_prefill_sourcecheck_v1 #')))
    core=literal((ROOT/CORE_PARENT).read_text(),(
      ('module genefer_anext_writeback_core_v1','module genefer_anext_coldleg_core_v1'),
      ('genefer_anext_writeback_square_backend_v1 #','genefer_anext_coldleg_backend_v1 #')))
    return {TARGET:cold,BACKEND:backend,CORE:core}

def verify():
    e=expected()
    for n,t in e.items():need((ROOT/n).read_text()==t,'COLDLEG_EXACT_SOURCE '+n)
    return {n:sha(t.encode()) for n,t in e.items()}

def legal(word,base):
    need(type(word) is int and -(1<<32)<=word<(1<<32),'COLDLEG_SIGNED33')
    need(type(base) is int and 300<=base<=1000000000,'COLDLEG_BASE')
    return -1<=word<base

def checked_destination(words,base):
    need(len(words)==16,'COLDLEG_WIDTH')
    if not all(legal(w,base) for w in words):return None
    return [w & 0xffffffff for w in words]

def contract():return dict(schema='anext-cold-source-legality-contract-v1',parent='F3',source_bits=16*33,
 destination_bits=16*32,extra_payload_bits=16,normal_cold_cycle_delta=0,warm_cycle_delta=0,
 numeric_fault_edge_delta=1,raw_metadata_image_transfer_cancel_delta=0,
 invalid_numeric_token_enters_destination=False,invalid_numeric_token_enters_reduction=False,
 invalid_numeric_token_enters_field_RAM=False,old_legal_prefix_is_speculative=True,
 possible_additional_older_prefix_commit_rows=1,failed_whole_publication=False,failed_cache_promotion=False,
 retry_requires_complete_reload=True,prior_completed_cache_is_not_a_success_for_failed_operation=True,
 scope='Explicit new numeric-fault ABI, not silent frozen-parent equivalence. No timing gain until measured.')

def write():
    e=expected()
    for n in e:need(not (ROOT/n).exists(),'COLDLEG_FRESH_TARGET '+n)
    for n,t in e.items():
        with (ROOT/n).open('x') as f:f.write(t)
    return verify()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');a=p.parse_args()
    print(json.dumps(write() if a.write else dict(pins=verify(),contract=contract()),indent=2))
