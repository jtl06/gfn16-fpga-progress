"""Private shared CRT metadata delay; no arithmetic/authority/calendar edits.

The copied arithmetic root is the sole permitted consumer seam. The qualified
P2 D16 leaf reads pointer+1 while writing pointer, so RDW is never requested.
"""
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
P2 = 'rtl/kernel/genefer_stream27_delay_mlab_v1.sv'
P2_SHA = 'fbcdb5da28c9ae64a68189d0b5a6b60182edcc2c80d98728ca9673555591b36e'
MODULE = 'genefer_stream27_crt_tag_delay_mlab_v1'
DECL = ' logic [TAG_W-1:0] crt_tag[0:15];logic crt_double[0:15];'
SHIFT = '''  if(joined)begin crt_tag[0]<={field_context[0],field_epoch[0],field_generation[0],field_row[0]};crt_double[0]<=bank_double[bank];end
  for(int d=1;d<16;d=d+1)begin crt_tag[d]<=crt_tag[d-1];crt_double[d]<=crt_double[d-1];end'''
NEW_DECL = ''' wire [TAG_W-1:0] crt_tag_tail;wire crt_double_tail;
 genefer_stream27_crt_tag_delay_mlab_v1 #(.WORD_W(TAG_W+1)) crt_metadata_delay (
  .clk,.rst_n,.joined,
  .write_word({bank_double[bank],field_context[0],field_epoch[0],field_generation[0],field_row[0]}),
  .head({crt_double_tail,crt_tag_tail}));'''
NEW_SHIFT = '  // Private D16 metadata RAM retains the original preedge CRT consume edge.'


def need(ok, reason):
    if not ok:
        raise ValueError('CRT_TAG_DELAY_' + reason)


def bind_leaf(enabled=1):
    """Return one isolated generic transport leaf, old semantics at enabled0."""
    need(enabled in (0, 1), 'BINARY_FLAG')
    data = (ROOT / P2).read_bytes()
    need(hashlib.sha256(data).hexdigest() == P2_SHA, 'QUALIFIED_P2_PIN')
    body = ''' logic [WORD_W-1:0] held;
 always_ff @(posedge clk)if(joined)held<=write_word;
 genefer_stream27_delay_mlab_v1 #(.WORD_W(WORD_W),.DEPTH(16)) delay (
  .clk,.rst_n,.advance(1'b1),.write_word(joined ? write_word : held),.head);
''' if enabled else ''' logic [WORD_W-1:0] stages[0:15];
 always_ff @(posedge clk)begin
  if(joined)stages[0]<=write_word;
  for(int d=1;d<16;d=d+1)stages[d]<=stages[d-1];
 end
 assign head=stages[15];
'''
    return f'''module {MODULE} #(parameter int unsigned WORD_W=38)(
 input logic clk,rst_n,joined,input logic [WORD_W-1:0] write_word,
 output wire [WORD_W-1:0] head);
{body}endmodule
'''


def bind_arithmetic(text, enabled=1):
    """Only shared payload transport changes; disabled returns exact input bytes."""
    need(enabled in (0, 1), 'BINARY_FLAG')
    if not enabled:
        return text
    need(text.count(DECL) == text.count(SHIFT) == 1, 'EXACT_COPIED_ROOT_SEAM')
    need(text.count('crt_double[15]') == 1 and text.count('crt_tag[15]') == 3,
         'ALL_TAIL_CONSUMERS_ACCOUNTED')
    result = text.replace(DECL, NEW_DECL).replace(SHIFT, NEW_SHIFT)
    result = result.replace('crt_double[15]', 'crt_double_tail').replace('crt_tag[15]', 'crt_tag_tail')
    need('crt_tag[' not in result and 'crt_double[' not in result, 'NO_HIDDEN_ARRAY_CONSUMERS')
    need(unbind_arithmetic(result) == text, 'LITERAL_REVERSE')
    return result


def unbind_arithmetic(text):
    need(text.count(NEW_DECL) == text.count(NEW_SHIFT) == 1, 'REVERSE_SEAM')
    return (text.replace(NEW_DECL, DECL).replace(NEW_SHIFT, SHIFT)
            .replace('crt_double_tail', 'crt_double[15]').replace('crt_tag_tail', 'crt_tag[15]'))
