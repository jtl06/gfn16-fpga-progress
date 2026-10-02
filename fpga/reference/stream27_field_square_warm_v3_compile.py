"""Additive runnable N32 warm/late-correction integration shell.

Preserves the frozen coherent-image v2 compiler/bundles. Adds independent epoch
correction admission and a continuously checked two-owner production protocol.
N32 arithmetic uses four seeds; full-N recurrence/scaling is still separate.
"""
from pathlib import Path
import hashlib

from .stream27_field_square_compile import prepare as coherent_bundle
from .stream27_epoch_protocol_v3 import geometry,Protocol
from .stream27_field_square_compile import PRIME,PSI,R
from .stream_ntt_schedule import transform
from .stream_ntt_model import bit_reverse


def replace_once(source,old,new):
    if source.count(old)!=1:raise ValueError('WARM_SOURCE_ANCHOR: '+old)
    return source.replace(old,new)


def prepare():
    parent=coherent_bundle();files=dict(parent['files'])
    old_top=parent['top'];new_top='genefer_stream27_field_square_aw5_warm_v3'
    source=files.pop(old_top+'.sv')
    source=replace_once(source,'module '+old_top+' (','module '+new_top+' (')
    source=replace_once(source,'  input logic [31:0] base_in,', '''  input logic [31:0] base_in,
  input logic [15:0] epoch_in,correction_epoch,
  input logic correction_valid,
  input logic [7:0] correction_generation,''')
    source=replace_once(source,'  output logic [215:0] commit_data);', '''  output logic [215:0] commit_data,
  output logic [15:0] out_epoch,commit_epoch,
  output logic [1:0] owner_count,
  output logic frame_accept,correction_accept);''')
    source=replace_once(source,'  logic busy,quarantine,controller_error;', '''  logic busy,quarantine,controller_error;
  logic [15:0] active_epoch,protocol_pw_epoch,protocol_sink_epoch;
  logic [23:0] high_owner,seed_owner,small_first_owner;
  logic [31:0] high_base;
  logic [2:0] correction_gap;
  logic [15:0] table_epoch[0:1];
  logic [7:0] table_generation[0:1];
  logic epoch_error,epoch_pending,epoch_correction_accept,protocol_pw_accept,protocol_commit;
  logic [31:0] epoch_correction_base;
  logic [1:0] protocol_pw_row,protocol_sink_row;
  wire raw_frame_begin=in_slot_valid && frame_start && !stop && !digit_admission_bad;
  wire accepted_correction=correction_valid && epoch_correction_accept && !stop && !admission_bad;''')
    source=replace_once(source,'  wire accepted=in_slot_valid && !stop && !admission_bad;',
                        '  wire accepted=in_slot_valid && !stop && !admission_bad && !epoch_pending;')
    source=replace_once(source,'  wire boundary_slot=(accepted_start || c1_pending) && !stop && !admission_bad;',
                        '  wire boundary_slot=(accepted_correction || c1_pending) && !stop && !admission_bad;')
    source=replace_once(source,'  wire [31:0] boundary_base=accepted_start ? base_in : active_base;',
                        '  wire [31:0] boundary_base=accepted_correction ? epoch_correction_base : active_base;')
    source=replace_once(source,'  wire [7:0] boundary_generation=accepted_start ? generation_in : active_generation;',
                        '  wire [7:0] boundary_generation=accepted_correction ? correction_generation : active_generation;')
    source=replace_once(source,'  logic admission_bad,join_bad;',
                        '  logic admission_bad,join_bad,digit_admission_bad;')
    source=replace_once(source,'(frame_start && (!in_slot_valid || busy))',
                        '(frame_start && (!in_slot_valid || remaining_input!=0))')
    source=replace_once(source,'''    // Base/correction pins after row0 are deliberately ignored.
    if(in_slot_valid && frame_start)
      for(int block=0;block<8;block=block+1)
        if(!correction_ok(c0_in[block*32+:32],base_in-32'd1) ||
           !correction_ok(c1_in[block*32+:32],32'd256))admission_bad=1;''', '''    // Corrections are a separate same-image epoch-tagged admission.
    digit_admission_bad=admission_bad;
    if(correction_valid && correction_gap<3)admission_bad=1;
    if(correction_valid)
      for(int block=0;block<8;block=block+1)
        if(!correction_ok(c0_in[block*32+:32],epoch_correction_base-32'd1) ||
           !correction_ok(c1_in[block*32+:32],32'd256))admission_bad=1;''')
    source=replace_once(source,'  assign out_error=controller_error || (|child_error);',
                        '  assign out_error=controller_error || (|child_error) || epoch_error;')
    # Separate prospective digit admission from correction validation. A
    # correction lookup may use the base of a same-edge new descriptor; that
    # lookup must not feed back into its own prospective frame_begin.
    source=replace_once(source,'    digit_admission_bad=admission_bad;\n','')
    admission_start=source.index('  always_comb begin\n    admission_bad=')
    correction_start=source.index('    // Corrections are a separate same-image epoch-tagged admission.')
    digit_block=source[admission_start:correction_start].replace('admission_bad','digit_admission_bad')
    source=source[:admission_start]+digit_block+'  end\n  always_comb begin\n    admission_bad=digit_admission_bad;\n'+source[correction_start:]
    source=replace_once(source,'  assign fault_pending=out_error || (|child_pending) || (!stop && (admission_bad || join_bad));',
                        '  assign fault_pending=out_error || (|child_pending) || epoch_pending || (!stop && (admission_bad || join_bad));')
    source=replace_once(source,'  assign generation_out=final_generation;', '''  assign generation_out=final_generation;
  assign out_epoch=protocol_sink_epoch;
  assign frame_accept=accepted_start;
  assign correction_accept=accepted_correction;
  genefer_stream27_epoch_protocol_v3 #(.ROWS(4),.POINTWISE_FIRST(43),.SINK_FIRST(88),.EPOCH_W(16)) epoch_protocol (
    .clk,.rst_n,.quarantine(stop),
    .external_fault_pending(admission_bad || join_bad || (|child_pending)),
    .frame_begin(raw_frame_begin),.frame_epoch(epoch_in),.frame_generation(generation_in),.frame_base(base_in),
    .correction_valid,.correction_epoch,.correction_generation,
    .cache_ready(term_slot && seed_capture==3),.cache_epoch(active_epoch),.cache_generation(term_generation),
    .pointwise_slot(fwd_slot),.pointwise_frame_start(fwd_start),.pointwise_generation(fwd_generation),
    .sink_slot(out_slot_valid),.sink_frame_start(out_frame_start),.sink_generation(generation_out),
    .context_enabled,.live_generation,.correction_accept(epoch_correction_accept),.correction_base(epoch_correction_base),
    .pointwise_accept(protocol_pw_accept),.commit_enable(protocol_commit),
    .pointwise_epoch(protocol_pw_epoch),.sink_epoch(protocol_sink_epoch),
    .pointwise_row(protocol_pw_row),.sink_row(protocol_sink_row),.owner_count,
    .out_error(epoch_error),.fault_pending(epoch_pending));''')
    source=replace_once(source,'        c1_pending<=accepted_start;',
                        '        c1_pending<=accepted_correction;')
    source=replace_once(source,'busy<=1;active_base<=base_in;active_generation<=generation_in;high_correction<=c1_in;',
                        'busy<=1;active_base<=base_in;active_generation<=generation_in;active_epoch<=epoch_in;')
    source=replace_once(source,'        if(small_slot)begin',
                        '        if(accepted_correction)high_correction<=c1_in;\n        if(small_slot)begin')
    source=replace_once(source,'          if(context_enabled && generation_out==live_generation)begin',
                        '          if(protocol_commit && context_enabled && generation_out==live_generation)begin')
    source=replace_once(source,'            commit_generation<=generation_out;commit_data<=data_out;',
                        '            commit_generation<=generation_out;commit_epoch<=protocol_sink_epoch;commit_data<=data_out;')
    # Main delay RAM still carries generation8. Only the P-point correction
    # transform and seed producer use compound(epoch16,generation8) tags.
    row_parent=(Path(__file__).resolve().parents[1]/'rtl/kernel/genefer_stream27_row_arithmetic_v2.sv').read_text()
    row_v3=row_parent.replace('genefer_stream27_mul8_v2','genefer_stream27_mul8_v3').replace(
        'genefer_stream27_add8_v2','genefer_stream27_add8_v3')
    row_v3=replace_once(row_v3,"parameter logic [31:0] Q=32'd4190109697",
                        "parameter logic [31:0] Q=32'd4190109697,\n    parameter int unsigned GEN_W=8")
    row_v3=replace_once(row_v3,"parameter logic [31:0] P=32'd104857601\n) (",
                        "parameter logic [31:0] P=32'd104857601,\n    parameter int unsigned GEN_W=8\n) (")
    row_v3=row_v3.replace('logic [7:0] generation_in','logic [GEN_W-1:0] generation_in').replace(
        'logic [7:0] generation_out','logic [GEN_W-1:0] generation_out').replace(
        'logic [7:0] generation_pipe','logic [GEN_W-1:0] generation_pipe')
    files['genefer_stream27_row_arithmetic_v3.sv']=row_v3
    source=replace_once(source,'logic [26:0] A_table[0:7],B_table[0:7],term_table[0:3][0:7];',
                        'logic [26:0] A_table[0:1][0:7],B_table[0:1][0:7],term_table[0:1][0:3][0:7];')
    source=replace_once(source,'logic small_capture,seed_running,tables_ready;',
                        'logic small_capture,seed_running; logic [1:0] tables_ready;')
    source=replace_once(source,'wire [31:0] boundary_base=accepted_correction ? epoch_correction_base : active_base;',
                        'wire [31:0] boundary_base=accepted_correction ? epoch_correction_base : high_base;')
    source=replace_once(source,'wire [7:0] boundary_generation=accepted_correction ? correction_generation : active_generation;',
                        'wire [23:0] boundary_owner=accepted_correction ? {correction_epoch,correction_generation} : high_owner;')
    source=replace_once(source,'logic [7:0] boundary_tag[0:7];','logic [23:0] boundary_tag[0:7];')
    if source.count('.BLOCKS(8),.PAYLOAD_W(8)')!=8:raise ValueError('signedowner tag anchors')
    source=source.replace('.BLOCKS(8),.PAYLOAD_W(8)','.BLOCKS(8),.PAYLOAD_W(24)').replace(
        '.payload_in(boundary_generation)','.payload_in(boundary_owner)')
    source=replace_once(source,'logic [7:0] twist_generation,small_twist_generation,term_generation,square_generation;',
                        'logic [7:0] twist_generation,square_generation; logic [23:0] small_twist_generation,term_generation;')
    source=replace_once(source,'logic [7:0] fwd_generation,inv_generation,small_generation;',
                        'logic [7:0] fwd_generation,inv_generation; logic [23:0] small_generation;')
    source=replace_once(source,'genefer_stream27_mul8_v2 small_twist (',
                        'genefer_stream27_mul8_v3 #(.GEN_W(24)) small_twist (')
    source=replace_once(source,'genefer_stream27_mul8_v2 term_seed (',
                        'genefer_stream27_mul8_v3 #(.GEN_W(24)) term_seed (')
    source=replace_once(source,'genefer_stream27_dif_aw3_p8_f0 correction_transform (',
                        'genefer_stream27_dif_aw3_p8_f0 #(.GEN_W(24)) correction_transform (')
    source=replace_once(source,'.generation_in(small_twist_generation),.live_generation,.data_in(small_twisted)',
                        '.generation_in(small_twist_generation),.live_generation({16\'b0,live_generation}),.data_in(small_twisted)')
    source=replace_once(source,'.generation_in(active_generation),.lhs(term_lhs)',
                        '.generation_in(seed_owner),.lhs(term_lhs)')
    source=replace_once(source,'.cache_epoch(active_epoch),.cache_generation(term_generation)',
                        '.cache_epoch(term_generation[23:8]),.cache_generation(term_generation[7:0])')
    source=replace_once(source,'''    join_bad=(fwd_slot && (!tables_ready || fwd_generation!=active_generation)) ||
      (small_slot && small_generation!=active_generation) ||
      (term_slot && term_generation!=active_generation) ||
      (out_slot_valid && generation_out!=active_generation);''', '''    join_bad=(fwd_slot && (!tables_ready[protocol_pw_epoch[0]] ||
        table_epoch[protocol_pw_epoch[0]]!=protocol_pw_epoch ||
        table_generation[protocol_pw_epoch[0]]!=fwd_generation)) ||
      (small_slot && small_capture && small_generation!=small_first_owner) ||
      (term_slot && (table_epoch[term_generation[8]]!=term_generation[23:8] ||
                    table_generation[term_generation[8]]!=term_generation[7:0]));''')
    source=replace_once(source,'logic [1:0] addA_row;',
                        'logic [1:0] addA_row; logic addA_bank; wire [1:0] correction_row=fwd_start ? 2\'d0 : x_row;')
    source=replace_once(source,'else if(fwd_slot && !stop && !join_bad)addA_row<=x_row;',
                        'else if(fwd_slot && !stop && !join_bad)begin addA_row<=correction_row;addA_bank<=protocol_pw_epoch[0];end')
    for lane in range(8):
        source=replace_once(source,f"assign term_lhs[{27*lane}+:27]=B_table[{{1'b{(lane>>2)&1},seed_issue[0],seed_issue[1]}}]",
                            f"assign term_lhs[{27*lane}+:27]=B_table[seed_owner[8]][{{1'b{(lane>>2)&1},seed_issue[0],seed_issue[1]}}]")
        source=replace_once(source,f"assign addA_rhs[{27*lane}+:27]=A_table[{{1'b{(lane>>2)&1},x_row[0],x_row[1]}}]",
                            f"assign addA_rhs[{27*lane}+:27]=A_table[protocol_pw_epoch[0]][{{1'b{(lane>>2)&1},correction_row[0],correction_row[1]}}]")
        source=replace_once(source,f'term_table[addA_row][{lane}]',f'term_table[addA_bank][addA_row][{lane}]')
    source=source.replace('A_table[j]<=small_data','A_table[small_generation[8]][j]<=small_data').replace(
        'B_table[j]<=small_data','B_table[small_generation[8]][j]<=small_data')
    source=replace_once(source,'remaining_input<=3;input_row<=1;x_row<=0;sink_row<=0;',
                        'remaining_input<=3;input_row<=1;')
    source=replace_once(source,'small_capture<=0;tables_ready<=0;seed_issue<=0;seed_capture<=0;',
                        'tables_ready[epoch_in[0]]<=0;')
    source=replace_once(source,'if(accepted_correction)high_correction<=c1_in;', '''if(accepted_correction)begin
          high_correction<=c1_in;high_base<=epoch_correction_base;
          high_owner<={correction_epoch,correction_generation};correction_gap<=0;
        end''')
    seed_progress='''        if(seed_running)begin
          seed_issue<=seed_issue+2'd1;
          if(seed_issue==3)seed_running<=0;
        end
'''
    source=replace_once(source,seed_progress,'')
    source=replace_once(source,'        if(small_slot)begin',seed_progress+'''        if(small_slot)begin''')
    source=replace_once(source,'if(small_capture)begin seed_running<=1;seed_issue<=0;seed_capture<=0;end', '''if(small_capture)begin
            seed_running<=1;seed_issue<=0;seed_owner<=small_generation;
            table_epoch[small_generation[8]]<=small_generation[23:8];
            table_generation[small_generation[8]]<=small_generation[7:0];
          end else small_first_owner<=small_generation;''')
    source=replace_once(source,'term_table[seed_capture][lane]<=term_result',
                        'term_table[term_generation[8]][seed_capture][lane]<=term_result')
    source=replace_once(source,'if(seed_capture==3)tables_ready<=1;',
                        'if(seed_capture==3)tables_ready[term_generation[8]]<=1;')
    source=replace_once(source,'if(fwd_slot)x_row<=x_row+2\'d1;',
                        "if(fwd_slot)x_row<=correction_row+2'd1;")
    source=replace_once(source,'small_capture<=0;seed_running<=0;tables_ready<=0;',
                        'small_capture<=0;seed_running<=0;tables_ready<=0;correction_gap<=3;')
    source=replace_once(source,'      if(!stop && !fault_pending)begin',
                        "      if(!stop && !fault_pending)begin\n        if(correction_gap<3)correction_gap<=correction_gap+3'd1;")
    files[new_top+'.sv']=source
    dependencies=list(parent['source_dependencies'])+[
        'reference/stream27_field_square_warm_v3_compile.py',
        'reference/stream27_epoch_protocol_v3.py',
        'rtl/kernel/genefer_stream27_epoch_protocol_v3.sv']
    root=Path(__file__).resolve().parents[1]
    rtl_sources=[p for p in parent['rtl_sources'] if p!=old_top+'.sv']
    rtl_sources+=['rtl/kernel/genefer_stream27_epoch_protocol_v3.sv',
                  'genefer_stream27_row_arithmetic_v3.sv',new_top+'.sv']
    return dict(files=files,source_dependencies=dependencies,rtl_sources=rtl_sources,top=new_top,
                source_sha256={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in dependencies},
                generated_sha256={p:hashlib.sha256(s.encode()).hexdigest() for p,s in files.items()},
                geometry=geometry(32),first_physical_output=87,first_commit=88,
                warm_interval=130,next_raw_boundary=134,next_correction_accept=135,
                next_cache_capture=171,next_forward_output=172,next_pointwise_accept=173,
                arithmetic_scope='N32/field0;lateepochcorrections;two-owner-two-cache;fourtermseeds',
                minimum_correction_push_spacing=4,
                full_N_arithmetic_ready=False,epoch_RAM_bits_added=0,native_run_performed=False)


def replay_small_overlap(images,starts,correction_edges,*,first_epoch=0):
    """Actual two-cache event/data replay, independently judged by schoolbook.

    Numeric arithmetic stays N32. Full-N protocol tests remain geometry only.
    This replays cache writes/seed products and pointwise reads at exact edges;
    it does not execute HDL or claim physical packing.
    """
    if not(len(images)==len(starts)==len(correction_edges)):
        raise ValueError('WARM_IMAGE_EVENT_WIDTH')
    if any(image.n!=32 for image in images):raise ValueError('WARM_LOCAL_N32_ONLY')
    if any(b-a<4 for a,b in zip(correction_edges,correction_edges[1:])):
        raise ValueError('WARM_CORRECTION_SEED_CAPACITY')
    p=Protocol(32);mont=lambda a,b:a*b*pow(R,-1,PRIME)%PRIME
    bundle=prepare();files=bundle['files'];events={};pw={};sink={};spectra={};answers={}
    caches=[dict(A=None,B=None,terms=[None]*4,tag=None) for _ in range(2)]
    def event(tick,kind,value):events.setdefault(tick,[]).append((kind,value))
    tags=[]
    for f,(image,start,corr) in enumerate(zip(images,starts,correction_edges)):
        image.validate();tag=((first_epoch+f)&65535,image.generation);tags.append(tag)
        event(start,'begin',tag);event(corr,'correction',tag)
        twisted=[image.digits[i]*pow(PSI,i,PRIME)%PRIME for i in range(32)]
        spectra[tag]=transform(32,8,values=twisted)['output_values']
        tables=[]
        for coefficients in (image.c0,image.c1):
            values=[coefficients[k]*pow(PSI,k*4,PRIME)%PRIME for k in range(8)]
            raw=transform(8,8,values=values)['output_values']
            tables.append(tuple(raw[bit_reverse(k,3)] for k in range(8)))
        event(corr+27,'A',(tag,tables[0]));event(corr+28,'B',(tag,tables[1]))
        for row in range(4):
            # Seed issue is after B capture. Old/young B values remain in
            # separate bank registers even when seed batches are back-to-back.
            event(corr+29+row,'seed',(tag,row))
            event(corr+33+row,'capture',(tag,row))
            pw[start+43+row]=(*tag,row);sink[start+88+row]=(*tag,row)
        event(corr+36,'ready',tag)
        answers[tag]=[None]*32
    finish=max(starts)+92
    pending_products={};seed_capture=0;cache_reads=0
    for tick in range(finish):
        inputs=dict((kind,value) for kind,value in events.get(tick,[]) if kind in ('begin','correction','ready'))
        p.edge(tick,begin=inputs.get('begin'),correction=inputs.get('correction'),ready=inputs.get('ready'),
               pw=pw.get(tick),sink=sink.get(tick),live_generation=images[-1].generation)
        if p.error:raise AssertionError(p.error)
        # A PW read sees registers from before this edge. Cache-capture events
        # below become visible only to a later sampled edge.
        row=pw.get(tick)
        if row:
            epoch,gen,m=row;tag=(epoch,gen);cache=caches[epoch&1]
            if cache['tag']!=tag or cache['terms'][m] is None:
                raise AssertionError('WARM_CACHE_OWNER')
            for lane in range(8):
                slot=m*8+lane;k=bit_reverse(slot,5)%8
                corrected=(spectra[tag][slot]+cache['A'][k]+cache['terms'][m][lane])%PRIME
                answers[tag][slot]=mont(corrected,corrected)
            cache_reads+=1
        for kind,value in events.get(tick,[]):
            if kind in ('A','B'):
                tag,values=value;cache=caches[tag[0]&1]
                cache[kind]=values
                if kind=='B':cache['tag']=tag;cache['terms']=[None]*4
            elif kind=='seed':
                tag,m=value;cache=caches[tag[0]&1]
                if cache['tag']!=tag:raise AssertionError('WARM_SEED_OWNER')
                weights=[int(word,16) for word in files['field-aw5-term-lane0.hex'].splitlines()]
                product=[]
                for lane in range(8):
                    weight=int(files[f'field-aw5-term-lane{lane}.hex'].splitlines()[m],16)
                    k=bit_reverse(m*8+lane,5)%8
                    product.append(mont(cache['B'][k],weight))
                pending_products[(tag,m)]=tuple(product)
            elif kind=='capture':
                tag,m=value
                if seed_capture!=m:raise AssertionError('WARM_SEED_CAPTURE_ORDER')
                caches[tag[0]&1]['terms'][m]=pending_products.pop((tag,m))
                seed_capture=(seed_capture+1)&3
    output=[]
    for image,tag in zip(images,tags):
        raw=transform(32,8,inverse=True,values=answers[tag])['output_values']
        rows=[]
        for m in range(4):
            rows.append(tuple(mont(raw[bit_reverse(lane,3)*4+m]*32%PRIME,
                         int(files[f'field-aw5-untwist-lane{lane}.hex'].splitlines()[m],16))
                              for lane in range(8)))
        output.append(tuple(rows))
    return dict(output=tuple(output),peak_owners=p.peak_owners,pointwise_cache_reads=cache_reads,
                sink_rows=p.sink_count,producer_products_remaining=len(pending_products),
                full_N_numeric_NTT_performed=False)
