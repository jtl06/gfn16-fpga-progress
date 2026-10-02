"""ONE additive frozen point+RAM27 whole area experiment, not promotion.

Namespace substitutions plus ONE RAM leaf; frozen full32 hardware block
admission and all arithmetic/control interfaces remain exact. No launcher.
"""
import hashlib
from pathlib import Path
from fpga.reference import anext_point_source_v1 as point
from fpga.reference import radix22_aa_pointdata27_v1 as field
from fpga.reference import anext_point_representative_v1 as representative
from fpga.reference import anext_a10_block_probe_prepare_v1 as probe

ROOT=field.ROOT
SELF='reference/radix22_aa_whole_source_v1.py'
TEST='tests/test_radix22_aa_whole_source_v1.py'
NAMES={old:old.replace('anext_point_','anext_pointdata27_') for old in point.NAMES.values()}
CORE=NAMES['genefer_anext_point_core_v1']
BLOCK='rtl/kernel/'+NAMES['genefer_anext_point_block_engine_v1']+'.sv'
CPP='rtl/tb/track_anext_pointdata27_core_v1.cpp'
FULL_CPP='rtl/tb/track_anext_pointdata27_representative_v1.cpp'
OUTPUT='reference/radix22_aa_whole_output_v1.py'
FULL_OUTPUT='reference/radix22_aa_whole_representative_output_v1.py'
PROBE_TOP='genefer_anext_pointdata27_block_probe_v1'
PROBE_SV='rtl/tb/'+PROBE_TOP+'.sv'
PROBE_CPP='rtl/tb/radix22_aa_whole_block_probe_v1.cpp'
FIELDS=(104857601,69206017,67239937)


def need(ok,why):
    if not ok:raise ValueError(why)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rename(text):
    for old,new in NAMES.items():text=text.replace(old,new)
    return text


def reverse(text):
    for old,new in NAMES.items():text=text.replace(new,old)
    return text


def expected():
    need(sha(ROOT/'reference/anext_point_source_v1.py')=='0969fc65c0b472e8304aa8dc78bb0a3a615efbbacea141f5722947ce70e13376'
         and sha(ROOT/'reference/anext_point_representative_v1.py')=='b4b944cc31cc86b7a581ffce1d18a77c67d2d1a753f8028ca18c93c26eb6c527','frozen source APIs')
    originals=point.expected();point.verify();result={}
    for name,text in originals.items():
        if name.endswith('genefer_anext_point_block_engine_v1.sv'):
            need(text.count(field.OLD)==1 and field.NEW not in text,'ONE block data-RAM substitution')
            changed=text.replace(field.OLD,field.NEW)
            need(changed.replace(field.NEW,field.OLD)==text,'no other block control/math/ABI delta')
        else:changed=text
        new_name=rename(name)
        if name=='rtl/tb/track_anext_point_core_v1.cpp':new_name=CPP
        if name=='reference/anext_point_output_v1.py':
            new_name=OUTPUT;changed=changed.replace("candidate='A-next-point-v1'","candidate='A-next-pointdata27-v1'")
        changed=rename(changed)
        restored=reverse(changed).replace(field.NEW,field.OLD).replace("candidate='A-next-pointdata27-v1'","candidate='A-next-point-v1'")
        need(restored==text,'exact reversible source/bench/validator alias delta '+name)
        result[new_name]=changed
    for name,text in representative.expected().items():
        need((ROOT/name).read_text()==text,'frozen representative source')
        new_name=FULL_CPP if name.endswith('.cpp') else FULL_OUTPUT
        changed=rename(text).replace("candidate='A-next-point-v1'","candidate='A-next-pointdata27-v1'")
        need(reverse(changed).replace("candidate='A-next-pointdata27-v1'","candidate='A-next-point-v1'")==text,'representative math unchanged')
        result[new_name]=changed
    probe.source_guard()
    result[PROBE_SV]=(ROOT/probe.SV).read_text().replace(probe.TOP,PROBE_TOP).replace('genefer_anext_a10_block_engine_v1',NAMES['genefer_anext_point_block_engine_v1'])
    cpp=(ROOT/probe.CPP).read_text();anchor='    words[0]=0xffffffffu;event(false,true,0,1,0,0xfffe,words);check();\n'
    extra='''    // Synthesized full32 block admission, not a translate_off RAM assertion.
    for(uint32_t bad : {0x08000001u,0x80000001u,0xffffffffu})
        for(unsigned lane=0;lane<16;++lane){
            words.fill(7);words[lane]=bad;
            event(true,true,0,1,65535,65535,words);check();
        }
'''
    need(cpp.count(anchor)==1,'exact extra48 high-word block transactions')
    result[PROBE_CPP]=cpp.replace(anchor,extra+anchor).replace(probe.TOP,PROBE_TOP).replace('A10_BLOCK_PASS','AA_POINTDATA27_BLOCK_PASS').replace('forward=direct-small\\n','forward=direct-small highword_cases=48\\n')
    return result


def full32_block_admission(words,mask,*,enabled=True,rst_n=True):
    """Range part of actual hardware gate; descriptor/state gates can reject more.

    Does not simulate timing, prove whole rollback, or admit raw scalar/vector.
    """
    need(type(mask) is int and 0<=mask<65536 and len(words)==16
         and all(type(x) is int and 0<=x<(1<<32) for x in words),'exact full32 block domain')
    return [bool(enabled and rst_n and not any((mask>>j)&1 and words[j]>=prime for j in range(16))) for prime in FIELDS]


def range_contract(overrides=None):
    point.verify();block=(ROOT/'rtl/kernel/genefer_anext_point_block_engine_v1.sv').read_text()
    seq=(ROOT/'rtl/kernel/genefer_anext_point_ntt_sequencer_v1.sv').read_text()
    backend=(ROOT/'rtl/kernel/genefer_anext_point_square_backend_v1.sv').read_text()
    def text(name):return (ROOT/'rtl/kernel'/name).read_text()
    route=text('genefer_track_a4_blockroute_v2.sv');cold=text('genefer_track_a4_cold_prefill_v1.sv')
    post=text('genefer_track_a4_post_ntt_v1.sv');transfer=text('genefer_track_a4_field_transfer_v2.sv')
    control=text('genefer_track_a4_control_fsm_v2.sv');digit=text('genefer_digit_reduce27_pipe.sv')
    if overrides:
        need(set(overrides)<= {'block','seq','route','cold','post','transfer','control','digit','backend'},'known pure mutation fixture')
        block=overrides.get('block',block);seq=overrides.get('seq',seq);route=overrides.get('route',route)
        cold=overrides.get('cold',cold);post=overrides.get('post',post);transfer=overrides.get('transfer',transfer)
        control=overrides.get('control',control);digit=overrides.get('digit',digit);backend=overrides.get('backend',backend)
    need(all(p<(1<<27) and 16*p>999999999 for p in FIELDS),'same three supported fields/reducer range')
    gate='if(block_write_en && block_write_mask[lane] && block_write_words[lane*32+:32]>=P)'
    need(block.count(gate)==1 and block.index(gate)<block.index('// synthesis translate_off')
         and '&& !block_bad_word;' in block and '.enable(block_enable)' in block,'synthesized full32 masked admission BEFORE RAM write enable')
    need(".load_we(1'b0),.read_en(1'b0)" in seq and ".vector_load_we(1'b0),.vector_read_en(1'b0)" in seq
         and '.block_write_words(block_write_words[f*512+:512])' in seq,'all actual whole callers use checked block port; legacy writes unreachable')
    need('wire write_accept=rst_n && write_en && legal;' in route and 'assign ram_we[bank]=write_accept' in route
         and '.write_en(data_we[bank])' in block,'RAM commit includes actual reset and block legality gate')
    need('wire allow_transfer=rst_n && !cancel && !error && !protocol_fault;' in transfer
         and 'assign field_write_en=request_write[1] && allow_transfer;' in transfer,'reset/cancel/error flush outward tokens')
    need('prefill_write ? prefill_words : post_write_words' in backend and 'wire admitted_write=(prefill_write || post_write) && !raw_admission_fault;' in backend,'exhaustive external producers are cold and post, admitted ownership retained')
    need('int\'(issued)!=T || int\'(received)!=T || int\'(written)!=T ||' in cold and "assign field_write_mask=16'hffff;" in cold
         and 'state==DRAIN && transfer_quiet && !fault' in cold,'cold initialized full image and registered error tail')
    need("int'(normal_written)!=T" in post and "patch_words_written!=6'd32" in post
         and 'if(transfer_quiet && !(|image_write_valid) && !(|image_boundary_valid))state<=CHECK;' in backend,'warm full normal write +32 patch words and bridge/image tail')
    need('bus.image_valid<=0;bus.prefill_valid<=0' in control and 'prefilled_snapshot<=bus.prefill_valid;bus.prefill_valid<=0;bus.image_valid<=0;' in control
         and 'generation<=generation+1\'b1;bus.prefill_valid<=0;bus.image_valid<=0;' in control,'reset/reload/mutation invalidate warm eligibility')
    need('digit<=32\'d999999999 || digit==32\'hffffffff' in digit and "residue<={5'b0,27'" in digit,'full-word reducer domain/signedminusone canonical output before block gate')
    names=['genefer_track_a4_blockroute_v2.sv','genefer_track_a4_cold_prefill_v1.sv','genefer_track_a4_post_ntt_v1.sv',
           'genefer_track_a4_field_transfer_v2.sv','genefer_track_a4_control_fsm_v2.sv','genefer_digit_reduce27_pipe.sv',
           'genefer_stream27_signed_boundary_reduce27_pipe.sv','genefer_a10_canonical_butterfly_v1.sv','genefer_montgomery_mul27_sparse_pipe.sv']
    return dict(status='PASS_source_range_admission_trace_exploration_ONLY',fields=FIELDS,
        caller_source_pins={name:sha(ROOT/'rtl/kernel'/name) for name in names},
        external_write_classes=['cold reducer output','post normal digit residues','post canonical signed patch sum'],
        internal_write_classes=['canonical CT/GS butterfly output','canonical Montgomery point-square output'],
        unreachable_in_this_whole_binding=['raw scalar load','raw contiguous vector load'],
        block_compare_full32_synthesized=True,mask_bad_word_rejects_whole16_lane_action=True,
        all_three_fields_rollback_atomicity_NOT_claimed=True,posterror_partial_field_image_requires_reload=True,
        cold_initialization='T offset rows ×16 lanes per field, counted/tagged/reduced, waits transfer quiet and error tail',
        warm_initialization='full normal T writes then32 canonical patch words; commit after whole child/transfer/image tail',
        reset_reload_mutation='eligibility invalidates; actual reset/cancel gates drop write tokens; payload memory retained; cold reload before use',
        BF_Montgomery_invariant='unchanged canonical arithmetic and fixed packed roots/normalization; valid outputs<P under initialized canonical inputs; not new arithmetic proof',
        field_only2054_scope_not_inherited_as_whole_qualification=True,new_arithmetic_profile=False,
        raw_arbitrary32_equivalence_claim=False,signed_CRT96_digit32_header_interfaces_unchanged=True,
        native_hardware_admission_probe_required=True,whole_native_and_physical_promotion=False)


def verify():
    expected_files=expected()
    for name,text in expected_files.items():need((ROOT/name).read_text()==text,'additive source drift '+name)
    range_contract();return {name:sha(ROOT/name) for name in expected_files}
