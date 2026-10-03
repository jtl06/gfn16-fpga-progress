"""Default-off FIELD100 storage-only delta; no authority or latency changes.

The first cut is the shared CRT metadata D16 shift, not an additional P2
commutator saving.  The copied root retains its name and external ABI.
"""
import copy
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_r15_storage_ram_bind.py'
P2 = 'genefer_stream27_delay_mlab_v1.sv'
P2_PIN = 'fbcdb5da28c9ae64a68189d0b5a6b60182edcc2c80d98728ca9673555591b36e'
MODULE = 'genefer_stream27_r15_crt_metadata_mlab_v1'
LEAF = MODULE + '.sv'
NUMERIC_MODULE = 'genefer_stream27_r15_numeric_delay_mlab_v1'
NUMERIC_LEAF = NUMERIC_MODULE + '.sv'
CRT = 'genefer_crt3_27_mont_pipe.sv'
NUMERIC_DECL = '    logic [26:0] r1_pipe[0:6],d3_pipe[0:4];'
READY_MARKER = "    assign ready=1'b1;"
DECL = ' logic [TAG_W-1:0] crt_tag[0:15];logic crt_double[0:15];'
SHIFT = '''  if(joined)begin crt_tag[0]<={field_context[0],field_epoch[0],field_generation[0],field_row[0]};crt_double[0]<=bank_double[bank];end
  for(int d=1;d<16;d=d+1)begin crt_tag[d]<=crt_tag[d-1];crt_double[d]<=crt_double[d-1];end'''
NEW_DECL = f''' wire [TAG_W-1:0] crt_tag_tail;wire crt_double_tail;
 {MODULE} #(.WORD_W(TAG_W+1)) crt_metadata_delay (
  .clk,.rst_n,.joined,
  .write_word({{bank_double[bank],field_context[0],field_epoch[0],field_generation[0],field_row[0]}}),
  .head({{crt_double_tail,crt_tag_tail}}));'''
NEW_SHIFT = '  // R15 D16 storage-only cut; unchanged preedge CRT metadata consumption.'


def sha(data):
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def need(ok, why):
    if not ok:
        raise ValueError('R15_STORAGE_RAM_' + why)


def leaf():
    return f'''module {MODULE} #(parameter int unsigned WORD_W=38)(
 input logic clk,rst_n,joined,input logic [WORD_W-1:0] write_word,
 output wire [WORD_W-1:0] head);
 // Stage zero originally held on !joined, even while reset/quarantined.
 // Payload remains unreset; the existing CRT valid pipeline owns eligibility.
 logic [WORD_W-1:0] held;
 always_ff @(posedge clk)if(joined)held<=write_word;
 genefer_stream27_delay_mlab_v1 #(.WORD_W(WORD_W),.DEPTH(16)) delay (
  .clk,.rst_n,.advance(1'b1),.write_word(joined ? write_word : held),.head);
endmodule
'''


def bind_arithmetic(text, storage_to_ram=0):
    need(storage_to_ram in (0, 1), 'BINARY_SWITCH')
    if not storage_to_ram:
        return text
    need(text.count(DECL) == text.count(SHIFT) == 1, 'EXACT_CRT_METADATA_SEAM')
    need(text.count('crt_tag[15]') == 3 and text.count('crt_double[15]') == 1,
         'ALL_CONSUMERS')
    result = text.replace(DECL, NEW_DECL).replace(SHIFT, NEW_SHIFT)
    result = result.replace('crt_tag[15]', 'crt_tag_tail').replace('crt_double[15]', 'crt_double_tail')
    need('crt_tag[' not in result and 'crt_double[' not in result, 'HIDDEN_CONSUMER')
    need(unbind_arithmetic(result) == text, 'LITERAL_REVERSE')
    return result


def unbind_arithmetic(text):
    need(text.count(NEW_DECL) == text.count(NEW_SHIFT) == 1, 'REVERSE_SEAM')
    return (text.replace(NEW_DECL, DECL).replace(NEW_SHIFT, SHIFT)
            .replace('crt_tag_tail', 'crt_tag[15]').replace('crt_double_tail', 'crt_double[15]'))


def numeric_leaf():
    return f'''module {NUMERIC_MODULE} #(
 parameter int unsigned WORD_W=27,DELAY=6)(
 input logic clk,rst_n,input logic [WORD_W-1:0] write_word,
 output wire [WORD_W-1:0] head);
 // Eight physical slots, DELAY5/6 logical edges. Read offset4/3 is
 // unconditionally distinct from write pointer, including reset/bad inputs.
 localparam logic [2:0] READ_OFFSET=3'(9-DELAY);
 logic [2:0] pointer,filled;
 wire [2:0] read_pointer=pointer+READ_OFFSET;
 (* ramstyle="MLAB, no_rw_check" *) logic [WORD_W-1:0] memory[0:7];
 logic [WORD_W-1:0] prefetched;
 assign head=filled==3'(DELAY) ? prefetched : '0;
 always_ff @(posedge clk)begin
  prefetched<=memory[read_pointer];memory[pointer]<=write_word;
 end
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin pointer<=0;filled<=0;end
  else begin pointer<=pointer+3'd1;if(filled!=3'(DELAY))filled<=filled+3'd1;end
 end
 // synthesis translate_off
 initial if(WORD_W<1 || (DELAY!=5 && DELAY!=6))$fatal(1,"R15_NUMERIC_DELAY_PARAMETERS");
 // synthesis translate_on
endmodule
'''


def numeric_changes(r1, d3, x12):
    decl = '    ' + ('logic [26:0] r1_stage0;wire [26:0] r1_tail;' if r1 else 'logic [26:0] r1_pipe[0:6];')
    decl += ('wire [26:0] d3_tail;' if d3 else 'logic [26:0] d3_pipe[0:4];')
    changes = []
    declarations = [(NUMERIC_DECL, decl)]
    instances = ''
    if r1:
        changes += [('        for(int i=1;i<=6;i=i+1)r1_pipe[i]<=r1_pipe[i-1];',
                     '        // R15 continuous D6 r1 tail in MLAB; stage0 reduction remains literal.'),
                    ('r1_pipe[0]', 'r1_stage0'), ('r1_pipe[6]', 'r1_tail')]
        instances += f'''    {NUMERIC_MODULE} #(.WORD_W(27),.DELAY(6)) r15_r1_history (
        .clk,.rst_n,.write_word(r1_stage0),.head(r1_tail));
'''
    if d3:
        changes += [('d3_pipe[0]<=delta3_work[26:0];', ''),
                    ('        for(int i=1;i<=4;i=i+1)d3_pipe[i]<=d3_pipe[i-1];',
                     '        // R15 continuous D5 delta3 payload in MLAB.'),
                    ('d3_pipe[4]', 'd3_tail')]
        instances += f'''    {NUMERIC_MODULE} #(.WORD_W(27),.DELAY(5)) r15_d3_history (
        .clk,.rst_n,.write_word(delta3_work[26:0]),.head(d3_tail));
'''
    if x12:
        declarations += [('    logic [52:0] x12_pipe[0:5];', '    wire [52:0] x12_tail;')]
        changes += [('        x12_pipe[0]<=x12_work[52:0];',
                     '        // R15 continuous D6 reconstructed x12 payload in MLAB.'),
                    ('        for(int i=1;i<=5;i=i+1)x12_pipe[i]<=x12_pipe[i-1];', ''),
                    ('x12_pipe[5]', 'x12_tail')]
        instances += f'''    {NUMERIC_MODULE} #(.WORD_W(53),.DELAY(6)) r15_x12_history (
        .clk,.rst_n,.write_word(x12_work[52:0]),.head(x12_tail));
'''
    changes += declarations
    if instances:
        changes += [(READY_MARKER, instances + READY_MARKER)]
    return changes


def bind_crt(text, *, r1=0, d3=0, x12=0):
    need(all(v in (0, 1) for v in (r1,d3,x12)), 'NUMERIC_BINARY_SWITCHES')
    if not (r1 or d3 or x12):
        return text
    result = text
    for old, new in numeric_changes(r1,d3,x12):
        need(old in result, 'NUMERIC_EXACT_SEAM:'+old[:40])
        result = result.replace(old,new)
    need(unbind_crt(result,r1=r1,d3=d3,x12=x12) == text, 'NUMERIC_LITERAL_REVERSE')
    for enabled, name in ((r1,'r1_pipe['),(d3,'d3_pipe['),(x12,'x12_pipe[')):
        need(not enabled or name not in result, 'NUMERIC_HIDDEN_CONSUMER:'+name)
    return result


def unbind_crt(text, *, r1, d3, x12):
    # Empty replacements require anchored restoration, never global insertion.
    result = text
    for old,new in reversed(numeric_changes(r1,d3,x12)):
        if old == 'd3_pipe[0]<=delta3_work[26:0];':
            anchor = 'delta2<=delta2_work[26:0];'
            need(result.count(anchor) == 1, 'REVERSE_D3_ANCHOR')
            result = result.replace(anchor,anchor+old)
        elif old == '        for(int i=1;i<=5;i=i+1)x12_pipe[i]<=x12_pipe[i-1];':
            anchor = '        // R15 continuous D6 reconstructed x12 payload in MLAB.\n'
            need(result.count(anchor) == 1, 'REVERSE_X12_ANCHOR')
            result = result.replace(anchor,anchor+old)
        else:
            need(new in result, 'NUMERIC_REVERSE_SEAM')
            result = result.replace(new,old)
    return result


def bind(bundle, storage_to_ram=0, *, crt_metadata_mlab=0,
         crt_r1_mlab=1, crt_d3_mlab=1, crt_x12_mlab=1):
    """Copy-only binding; zero returns a deep, byte-exact bundle copy."""
    need(storage_to_ram in (0, 1), 'BINARY_SWITCH')
    out = copy.deepcopy(bundle)
    if not storage_to_ram:
        return out
    flags = dict(crt_metadata_mlab=crt_metadata_mlab,crt_r1_mlab=crt_r1_mlab,
                 crt_d3_mlab=crt_d3_mlab,crt_x12_mlab=crt_x12_mlab)
    need(all(v in (0,1) for v in flags.values()), 'CUT_BINARY_SWITCHES')
    need(any(flags.values()), 'NO_ENABLED_CUT')
    need(bundle['geometry']['p'] == 16 and bundle['geometry']['contexts'] == 2,
         'QUALIFIED_GEOMETRY')
    need(sha(bundle['files'][P2]) == P2_PIN, 'EXACT_EXISTING_P2')
    need(LEAF not in bundle['files'] and NUMERIC_LEAF not in bundle['files'], 'ALREADY_BOUND')
    names = [n for n, text in bundle['files'].items() if DECL in text]
    need(len(names) == 1, 'ONE_SHARED_ARITHMETIC')
    name = names[0]
    members = []
    if crt_metadata_mlab:
        out['files'][name] = bind_arithmetic(bundle['files'][name], 1)
        out['files'][LEAF] = leaf()
        out['rtl_sources'].append(LEAF)
        members += [name,LEAF]
    if crt_r1_mlab or crt_d3_mlab or crt_x12_mlab:
        out['files'][CRT] = bind_crt(bundle['files'][CRT],r1=crt_r1_mlab,d3=crt_d3_mlab,x12=crt_x12_mlab)
        out['files'][NUMERIC_LEAF] = numeric_leaf()
        out['rtl_sources'].append(NUMERIC_LEAF)
        members += [CRT,NUMERIC_LEAF]
    out['generated_sha256'] = {n: sha(t) for n, t in out['files'].items()}
    changed = {n: {'before': bundle['generated_sha256'].get(n), 'after': out['generated_sha256'][n]}
               for n in members}
    out['source_dependencies'] = list(dict.fromkeys(bundle['source_dependencies'] + [SELF]))
    out['source_sha256'][SELF] = sha((ROOT / SELF).read_bytes())
    width = 25 + (bundle['geometry']['aw'] - 4) + 1
    out['r15_storage_ram'] = dict(
        switch='storage_to_ram', enabled=1, cut_flags=flags,
        cuts=[k for k,v in flags.items() if v],
        changed_members=changed, original_arithmetic=name, leaf=LEAF,
        word_width=width, depth=16, continuous_advance=True,
        stage_zero_hold=True, payload_reset=False, reset_fresh_edges=16,
        read_address='(write_pointer+1) mod 16', write_address='write_pointer',
        collision_possible=False, original_eligible_preedge_head=True,
        eligibility_authority='unchanged CRT valid / error barrier',
        latency_delta=0, schedule_unchanged=True, ownership_fault_logic_unchanged=True,
        interface_unchanged=True, term_payload_cut_enabled=False,
        previous_P2_savings_counted_again=False,
        declared_ff_upper_bound_only=16*width-(2*width+4+5),
        metadata_parent_already_mapped_to_M20K=True,
        numeric_ring_depth=8, numeric_delays={'r1':6,'d3':5,'x12':6},
        numeric_widths={'r1':27,'d3':27,'x12':53},
        numeric_declared_ff_upper_bound_only=16*sum((w*d-w-6) for w,d,on in
            ((27,6,crt_r1_mlab),(27,5,crt_d3_mlab),(53,6,crt_x12_mlab)) if on),
        native_qualified=False, mapped_saving_measured=False, promotion_allowed=False)
    if crt_metadata_mlab:
        need(unbind_arithmetic(out['files'][name]) == bundle['files'][name], 'BUNDLE_REVERSE')
    need(out['parameters'] == bundle['parameters'] and out['geometry'] == bundle['geometry'] and
         out['top'] == bundle['top'], 'PUBLIC_ABI_CALENDAR')
    return out
