"""Source-only complete N32/P8 field square: no native/HDL dispatch.

The tiny term path uses four explicit seed products, one per physical row.
It does not claim a full-N recurrence implementation. Frozen transform bundles
are untouched; this emits new source and exact ROM collateral in memory.
"""
from pathlib import Path
import hashlib

from .stream27_field_compile import compile_transform
from .stream_ntt_model import bit_reverse
from .stream_ntt_schedule import transform


PRIME = 104857601
PSI = pow(3, (PRIME - 1) // 64, PRIME)
R = (1 << 32) % PRIME


BODY = r'''// Complete source-only tiny one-field square. No RTL/clock claim.
// Digits: ordinary unsigned d<b. c0/c1: signed32, natural block order.
// Main words remain ordinary; square adds R^-1; final roots use R^2/N.
module genefer_stream27_field_square_aw5_probe (
  input logic clk,rst_n,in_slot_valid,frame_start,context_enabled,
  input logic [7:0] generation_in,live_generation,
  input logic [31:0] base_in,
  input logic [255:0] data_in,c0_in,c1_in,
  output logic out_slot_valid,out_frame_start,out_eligible,out_error,fault_pending,
  output logic [7:0] generation_out,
  output logic [215:0] data_out,
  output logic commit_valid,commit_frame_start,
  output logic [7:0] commit_generation,
  output logic [215:0] commit_data);
  logic busy,quarantine,controller_error;
  logic [31:0] active_base;
  logic [7:0] active_generation;
  logic [255:0] high_correction;
  logic c1_pending;
  logic [2:0] remaining_input;
  logic [1:0] input_row,x_row,seed_issue,seed_capture,sink_row;
  logic small_capture,seed_running,tables_ready;
  logic [26:0] A_table[0:7],B_table[0:7],term_table[0:3][0:7];
  logic [11:0] child_error,child_pending;
  wire stop=quarantine || out_error;
  logic admission_bad,join_bad;
  wire accepted=in_slot_valid && !stop && !admission_bad;
  wire accepted_start=accepted && frame_start;
  wire [31:0] digit_base=frame_start ? base_in : active_base;
  wire [1:0] digit_row=frame_start ? 2'd0 : input_row;
  wire boundary_slot=(accepted_start || c1_pending) && !stop && !admission_bad;
  wire [31:0] boundary_base=accepted_start ? base_in : active_base;
  wire [7:0] boundary_generation=accepted_start ? generation_in : active_generation;
  function automatic logic correction_ok(input logic [31:0] word,input logic [31:0] limit);
    logic signed [32:0] wide_value;
    logic [32:0] magnitude;
    begin
      wide_value=$signed({word[31],word});
      magnitude=word[31] ? 33'(-wide_value) : 33'(wide_value);
      correction_ok=magnitude<={1'b0,limit};
    end
  endfunction
  always_comb begin
    admission_bad=(frame_start && (!in_slot_valid || busy)) ||
      (in_slot_valid && !frame_start && remaining_input==0) ||
      (!in_slot_valid && remaining_input!=0) ||
      (in_slot_valid && !frame_start && remaining_input!=0 && generation_in!=active_generation);
    if(in_slot_valid) begin
      if(digit_base<32'd172 || digit_base>32'd1000000000)admission_bad=1;
      for(int lane=0;lane<8;lane=lane+1)
        if(data_in[lane*32+:32]>=digit_base)admission_bad=1;
    end
    // Base/correction pins after row0 are deliberately ignored.
    if(in_slot_valid && frame_start)
      for(int block=0;block<8;block=block+1)
        if(!correction_ok(c0_in[block*32+:32],base_in-32'd1) ||
           !correction_ok(c1_in[block*32+:32],32'd256))admission_bad=1;
  end
  assign out_error=controller_error || (|child_error);
  assign fault_pending=out_error || (|child_pending) || (!stop && (admission_bad || join_bad));

  logic [7:0] digit_valid,digit_error,boundary_valid,boundary_error;
  logic [10:0] digit_tag[0:7];
  logic [7:0] boundary_tag[0:7];
  logic [215:0] digit_data,boundary_data,twist_rhs,small_rhs,term_lhs,term_rhs,untwist_rhs;
  wire digit_slot=&digit_valid;
  wire boundary_out_slot=&boundary_valid;
  assign child_error[10]=|digit_error;
  assign child_error[11]=|boundary_error;
  always_comb begin
    child_pending[10]=child_error[10] || (!stop && ((|digit_valid) && !(&digit_valid)));
    child_pending[11]=child_error[11] || (!stop && ((|boundary_valid) && !(&boundary_valid)));
    for(int lane=1;lane<8;lane=lane+1)begin
      if(!stop && digit_slot && digit_tag[lane]!=digit_tag[0])child_pending[10]=1;
      if(!stop && boundary_out_slot && boundary_tag[lane]!=boundary_tag[0])child_pending[11]=1;
    end
  end
  logic twist_slot,twist_start,small_twist_slot,small_twist_start;
  logic term_slot,term_start,square_slot,square_start;
  logic [7:0] twist_generation,small_twist_generation,term_generation,square_generation;
  logic [215:0] twisted,small_twisted,term_result,squared;
  logic fwd_slot,fwd_start,inv_slot,inv_start,small_slot,small_start;
  logic [7:0] fwd_generation,inv_generation,small_generation;
  logic [215:0] fwd_data,inv_data,small_data;
  logic addA_slot,addA_start,addB_slot,addB_start;
  logic [7:0] addA_generation,addB_generation;
  logic [215:0] addA_data,addB_data,addA_rhs,addB_rhs;
  logic final_slot,final_start;
  logic [7:0] final_generation;
  logic [215:0] final_data;
%REDUCERS_ROOTS%

  genefer_stream27_mul8_v2 twist (
    .clk,.rst_n,.in_slot_valid(digit_slot),.frame_start(digit_tag[0][2]),.quarantine(stop),
    .generation_in(digit_tag[0][10:3]),.lhs(digit_data),.rhs(twist_rhs),
    .out_slot_valid(twist_slot),.out_frame_start(twist_start),.out_error(child_error[0]),
    .fault_pending(child_pending[0]),.generation_out(twist_generation),.result(twisted));
  genefer_stream27_mul8_v2 small_twist (
    .clk,.rst_n,.in_slot_valid(boundary_out_slot),.frame_start(1'b1),.quarantine(stop),
    .generation_in(boundary_tag[0]),.lhs(boundary_data),.rhs(small_rhs),
    .out_slot_valid(small_twist_slot),.out_frame_start(small_twist_start),.out_error(child_error[1]),
    .fault_pending(child_pending[1]),.generation_out(small_twist_generation),.result(small_twisted));
  genefer_stream27_dif_aw3_p8_f0 correction_transform (
    .clk,.rst_n,.in_slot_valid(small_twist_slot),.frame_start(small_twist_start),.quarantine(stop),
    .context_enabled,.generation_in(small_twist_generation),.live_generation,.data_in(small_twisted),
    .out_slot_valid(small_slot),.out_frame_start(small_start),.out_eligible(),
    .out_error(child_error[7]),.fault_pending(child_pending[7]),.generation_out(small_generation),.data_out(small_data));
  genefer_stream27_dif_aw5_p8_f0 forward_transform (
    .clk,.rst_n,.in_slot_valid(twist_slot),.frame_start(twist_start),.quarantine(stop),
    .context_enabled,.generation_in(twist_generation),.live_generation,.data_in(twisted),
    .out_slot_valid(fwd_slot),.out_frame_start(fwd_start),.out_eligible(),
    .out_error(child_error[5]),.fault_pending(child_pending[5]),.generation_out(fwd_generation),.data_out(fwd_data));
  genefer_stream27_mul8_v2 term_seed (
    .clk,.rst_n,.in_slot_valid(seed_running),.frame_start(seed_issue==0),.quarantine(stop),
    .generation_in(active_generation),.lhs(term_lhs),.rhs(term_rhs),
    .out_slot_valid(term_slot),.out_frame_start(term_start),.out_error(child_error[2]),
    .fault_pending(child_pending[2]),.generation_out(term_generation),.result(term_result));
%CORRECTION_SELECTION%
  genefer_stream27_add8_v2 add_A (
    .clk,.rst_n,.in_slot_valid(fwd_slot && !join_bad),.frame_start(fwd_start),.quarantine(stop),
    .generation_in(fwd_generation),.lhs(fwd_data),.rhs(addA_rhs),
    .out_slot_valid(addA_slot),.out_frame_start(addA_start),.out_error(child_error[8]),
    .fault_pending(child_pending[8]),.generation_out(addA_generation),.result(addA_data));
  genefer_stream27_add8_v2 add_B (
    .clk,.rst_n,.in_slot_valid(addA_slot),.frame_start(addA_start),.quarantine(stop),
    .generation_in(addA_generation),.lhs(addA_data),.rhs(addB_rhs),
    .out_slot_valid(addB_slot),.out_frame_start(addB_start),.out_error(child_error[9]),
    .fault_pending(child_pending[9]),.generation_out(addB_generation),.result(addB_data));
  genefer_stream27_mul8_v2 square (
    .clk,.rst_n,.in_slot_valid(addB_slot),.frame_start(addB_start),.quarantine(stop),
    .generation_in(addB_generation),.lhs(addB_data),.rhs(addB_data),
    .out_slot_valid(square_slot),.out_frame_start(square_start),.out_error(child_error[3]),
    .fault_pending(child_pending[3]),.generation_out(square_generation),.result(squared));
  genefer_stream27_dit_aw5_p8_f0 inverse_transform (
    .clk,.rst_n,.in_slot_valid(square_slot),.frame_start(square_start),.quarantine(stop),
    .context_enabled,.generation_in(square_generation),.live_generation,.data_in(squared),
    .out_slot_valid(inv_slot),.out_frame_start(inv_start),.out_eligible(),
    .out_error(child_error[6]),.fault_pending(child_pending[6]),.generation_out(inv_generation),.data_out(inv_data));
  genefer_stream27_mul8_v2 final_normalize (
    .clk,.rst_n,.in_slot_valid(inv_slot),.frame_start(inv_start),.quarantine(stop),
    .generation_in(inv_generation),.lhs(inv_data),.rhs(untwist_rhs),
    .out_slot_valid(final_slot),.out_frame_start(final_start),.out_error(child_error[4]),
    .fault_pending(child_pending[4]),.generation_out(final_generation),.result(final_data));
  assign out_slot_valid=final_slot && !stop;
  assign out_frame_start=final_start && out_slot_valid;
  assign generation_out=final_generation;
  assign data_out=final_data;
  assign out_eligible=out_slot_valid && context_enabled && generation_out==live_generation;
  always_comb begin
    join_bad=(fwd_slot && (!tables_ready || fwd_generation!=active_generation)) ||
      (small_slot && small_generation!=active_generation) ||
      (term_slot && term_generation!=active_generation) ||
      (out_slot_valid && generation_out!=active_generation);
  end
  always_ff @(posedge clk or negedge rst_n)begin
    if(!rst_n)begin
      busy<=0;quarantine<=0;controller_error<=0;c1_pending<=0;remaining_input<=0;
      input_row<=0;x_row<=0;seed_issue<=0;seed_capture<=0;sink_row<=0;
      small_capture<=0;seed_running<=0;tables_ready<=0;
      commit_valid<=0;commit_frame_start<=0;
    end else begin
      commit_valid<=0;commit_frame_start<=0;
      if(out_error)quarantine<=1;
      if(!stop && (admission_bad || join_bad || (|child_pending)))controller_error<=1;
      if(!stop && !fault_pending)begin
        c1_pending<=accepted_start;
        if(accepted_start)begin
          busy<=1;active_base<=base_in;active_generation<=generation_in;high_correction<=c1_in;
          remaining_input<=3;input_row<=1;x_row<=0;sink_row<=0;
          small_capture<=0;tables_ready<=0;seed_issue<=0;seed_capture<=0;
        end else if(accepted)begin remaining_input<=remaining_input-3'd1;input_row<=input_row+2'd1;end
        if(small_slot)begin
          for(int j=0;j<8;j=j+1)begin
%CAPTURE_TABLES%
          end
          if(small_capture)begin seed_running<=1;seed_issue<=0;seed_capture<=0;end
          small_capture<=!small_capture;
        end
        if(seed_running)begin
          seed_issue<=seed_issue+2'd1;
          if(seed_issue==3)seed_running<=0;
        end
        if(term_slot)begin
          for(int lane=0;lane<8;lane=lane+1)term_table[seed_capture][lane]<=term_result[lane*27+:27];
          seed_capture<=seed_capture+2'd1;
          if(seed_capture==3)tables_ready<=1;
        end
        if(fwd_slot)x_row<=x_row+2'd1;
        if(out_slot_valid)begin
          sink_row<=sink_row+2'd1;
          if(sink_row==3)busy<=0;
          if(context_enabled && generation_out==live_generation)begin
            commit_valid<=1;commit_frame_start<=out_frame_start;
            commit_generation<=generation_out;commit_data<=data_out;
          end
        end
      end
    end
  end
endmodule
'''


def prepare():
    files = {}
    for n, inverse in ((32, False), (32, True), (8, False)):
        compiled = compile_transform(n, inverse=inverse)
        files[compiled['module'] + '.sv'] = compiled['source']
        files.update(compiled['rom_files'])
    reducers = []
    selections = []
    captures = []
    for lane in range(8):
        block = bit_reverse(lane, 3)
        reducers += [f'''  genefer_digit_reduce27_pipe #(.PAYLOAD_W(11)) digit_lane{lane} (
    .clk,.rst_n,.in_valid(accepted),.digit(data_in[{32*lane}+:32]),
    .payload_in({{generation_in,frame_start,digit_row}}),.out_valid(digit_valid[{lane}]),
    .out_error(digit_error[{lane}]),.residue(),.payload_out(digit_tag[{lane}]));''']
        # A separate explicit full residue wire avoids implicit width extension.
        reducers[-1] = reducers[-1].replace('.residue()', f'.residue(digit_residue{lane})')
        reducers.insert(len(reducers)-1, f'  wire [31:0] digit_residue{lane},boundary_residue{lane};')
        reducers += [f'  assign digit_data[{27*lane}+:27]=digit_residue{lane}[26:0];',
                     f'''  genefer_stream27_signed_boundary_reduce27_pipe #(.AW(5),.BLOCKS(8),.PAYLOAD_W(8)) boundary_lane{lane} (
    .clk,.rst_n,.in_valid(boundary_slot),.boundary_high(c1_pending),
    .correction($signed(c1_pending ? high_correction[{32*block}+:32] : c0_in[{32*block}+:32])),
    .base(boundary_base),.payload_in(boundary_generation),.out_valid(boundary_valid[{lane}]),
    .out_error(boundary_error[{lane}]),.residue(boundary_residue{lane}),.payload_out(boundary_tag[{lane}]));''',
                     f'  assign boundary_data[{27*lane}+:27]=boundary_residue{lane}[26:0];',
                     f"  assign small_rhs[{27*lane}+:27]=27'd{pow(PSI,block*4,PRIME)*R%PRIME};"]
        weights = {
            'twist': [pow(PSI, block * 4 + row, PRIME) * R % PRIME for row in range(4)],
            'untwist': [pow(PSI, -(block * 4 + row), PRIME) * pow(32, -1, PRIME) * R * R % PRIME for row in range(4)],
            'term': [PSI * pow(PSI * PSI % PRIME, bit_reverse(row * 8 + lane, 5), PRIME) * R % PRIME for row in range(4)],
        }
        for kind, words in weights.items():
            filename = f'field-aw5-{kind}-lane{lane}.hex'
            files[filename] = ''.join(f'{word:07x}\n' for word in words)
            slot, start = {'twist': ('digit_slot', 'digit_tag[0][2]'),
                           'untwist': ('inv_slot', 'inv_start'),
                           'term': ('seed_running', 'seed_issue==0')}[kind]
            rhs = {'twist': 'twist_rhs', 'untwist': 'untwist_rhs', 'term': 'term_rhs'}[kind]
            reducers += [f'''  genefer_stream27_root_rom_prefetch #(.PERIOD(4),.FIRST_ROOT(27'd{words[0]}),
    .HEX_FILE("{filename}")) {kind}_root{lane} (
    .clk,.rst_n,.in_slot_valid({slot} && !stop),.frame_start({start}),.root({rhs}[{27*lane}+:27]));''']
        selections += [f'''  assign term_lhs[{27*lane}+:27]=B_table[{{1'b{(lane>>2)&1},seed_issue[0],seed_issue[1]}}];
  assign addA_rhs[{27*lane}+:27]=A_table[{{1'b{(lane>>2)&1},x_row[0],x_row[1]}}];
  assign addB_rhs[{27*lane}+:27]=term_table[addA_row][{lane}];''']
        # j varies in the source loop, so constant generated cases are explicit.
        captures += [f'''            if(j=={lane})begin
              if(!small_capture)A_table[j]<=small_data[{27*bit_reverse(lane,3)}+:27];
              else B_table[j]<=small_data[{27*bit_reverse(lane,3)}+:27];
            end''']
    # The second add consumes row r one edge after the first: retain r through
    # that register boundary, including canceled occupied rows.
    selections.insert(0, '''  logic [1:0] addA_row;
  always_ff @(posedge clk or negedge rst_n)
    if(!rst_n)addA_row<=0;
    else if(fwd_slot && !stop && !join_bad)addA_row<=x_row;''')
    source = BODY.replace('%REDUCERS_ROOTS%', '\n'.join(reducers))
    source = source.replace('%CORRECTION_SELECTION%', '\n'.join(selections))
    source = source.replace('%CAPTURE_TABLES%', '\n'.join(captures))
    files['genefer_stream27_field_square_aw5_probe.sv'] = source
    dependencies = ['reference/stream27_field_square_compile.py', 'reference/stream27_field_compile.py',
                    'reference/stream27_field_plan.py', 'reference/stream_ntt_model.py',
                    'reference/stream_ntt_schedule.py', 'reference/stream_ntt_blockcarry_schedule.py',
                    'rtl/kernel/genefer_stream27_row_arithmetic_v2.sv',
                    'rtl/kernel/genefer_stream27_root_rom_prefetch.sv',
                    'rtl/kernel/genefer_stream27_mdc_commutator_slots_v2.sv',
                    'rtl/kernel/genefer_stream27_mdc_commutator_sync.sv',
                    'rtl/kernel/genefer_digit_reduce27_pipe.sv',
                    'rtl/kernel/genefer_stream27_signed_boundary_reduce27_pipe.sv',
                    'rtl/kernel/genefer_ntt_banked27_engine.sv',
                    'rtl/kernel/genefer_montgomery_mul27_sparse_pipe.sv']
    root = Path(__file__).resolve().parents[1]
    mutations = {}
    final_file = 'field-aw5-untwist-lane0.hex'
    final_words = files[final_file].splitlines()
    final_words[1] = f'{int(final_words[1],16)*pow(R,-1,PRIME)%PRIME:07x}'
    mutations['wrong_final_domain'] = dict(files={final_file: '\n'.join(final_words)+'\n'},
        expected_kind='FIELD_PHYSICAL_DATA_MISMATCH',
        description='One final row1/lane0 root uses R/N instead of R^2/N; row0 bypass is matched control.')
    top_file = 'genefer_stream27_field_square_aw5_probe.sv'
    for kind, label in (('missing_c0','addA_rhs'),('missing_c1','addB_rhs')):
        changed = files[top_file]
        anchors = []
        for lane in range(8):
            if label == 'addA_rhs':
                anchor = f"assign addA_rhs[{27*lane}+:27]=A_table[{{1'b{(lane>>2)&1},x_row[0],x_row[1]}}];"
            else:
                anchor = f'assign addB_rhs[{27*lane}+:27]=term_table[addA_row][{lane}];'
            if changed.count(anchor)!=1:
                raise ValueError('FIELD_MUTATION_ANCHOR: '+anchor)
            replacement = f"assign {label}[{27*lane}+:27]=27'd0;"
            changed = changed.replace(anchor,replacement)
            anchors.append(dict(before=anchor,after=replacement))
        mutations[kind] = dict(files={top_file:changed},expected_kind='FIELD_PHYSICAL_DATA_MISMATCH',
                              description=kind,anchors=anchors)
    rtl_sources = [path for path in dependencies if path.endswith('.sv')]
    rtl_sources += [path for path in files if path.endswith('.sv')]
    return dict(files=files, source_dependencies=dependencies, rtl_sources=rtl_sources,
                mutations=mutations, top='genefer_stream27_field_square_aw5_probe',
                source_sha256={path: hashlib.sha256((root/path).read_bytes()).hexdigest() for path in dependencies},
                generated_sha256={path: hashlib.sha256(text.encode()).hexdigest() for path,text in files.items()},
                first_physical_output=87, first_terminal_commit=88,
                tiny_complete_field_source=True, full_N_ready=False, native_run_performed=False)


def evaluate_small_image(image, mutation=None):
    """Replay the emitted tiny roots/domain contract, never full-N arithmetic.

    The qualification oracle is separately owned schoolbook convolution. This
    replay checks the implementer's whole algebra before HDL preparation.
    """
    image.validate()
    if image.n != 32:
        raise ValueError('FIELD_SQUARE_TINY_ONLY')
    bundle = prepare()
    files = dict(bundle['files'])
    if mutation:
        files.update(bundle['mutations'][mutation]['files'])
    r_inverse = pow(R, -1, PRIME)
    mont = lambda a,b: a*b*r_inverse % PRIME
    def roots(kind,lane):
        return tuple(int(word,16) for word in files[f'field-aw5-{kind}-lane{lane}.hex'].splitlines())
    twisted = [0]*32
    for lane in range(8):
        block = bit_reverse(lane,3)
        for row,weight in enumerate(roots('twist',lane)):
            i=block*4+row
            twisted[i]=mont(image.digits[i] % PRIME,weight)
    forward=transform(32,8,values=twisted)['output_values']
    tables=[]
    for coefficients in (image.c0,image.c1):
        values=[mont(coefficients[k]%PRIME,pow(PSI,k*4,PRIME)*R%PRIME) for k in range(8)]
        raw=transform(8,8,values=values)['output_values']
        tables.append(tuple(raw[bit_reverse(k,3)] for k in range(8)))
    spectrum=[]
    for row in range(4):
        for lane in range(8):
            slot=row*8+lane;k=bit_reverse(slot,5)%8
            A=0 if mutation=='missing_c0' else tables[0][k]
            term=0 if mutation=='missing_c1' else mont(tables[1][k],roots('term',lane)[row])
            corrected=(forward[slot]+A+term)%PRIME
            spectrum.append(mont(corrected,corrected))
    inverse=transform(32,8,inverse=True,values=spectrum)['output_values']
    result=[]
    for row in range(4):
        result.append(tuple(mont(inverse[bit_reverse(lane,3)*4+row]*32%PRIME,
                                roots('untwist',lane)[row]) for lane in range(8)))
    return tuple(result)
