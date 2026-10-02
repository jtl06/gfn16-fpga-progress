"""Source-bound shape checks, not HDL elaboration or RAM inference proof."""
import hashlib
from pathlib import Path

RTL='rtl/kernel/genefer_stream27_mdc_commutator_sync.sv'
SHA='72e6d497280f8d5eeba28c0af30b79a116e20b338d50a9894355a28d3aa4d218'


def validate(root):
    raw=(Path(root)/RTL).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SHA:raise ValueError('commutator RTL pin')
    text=raw.decode()
    for token in ('if (DEPTH == 1) begin : register_cell',
                  'prefetched <= memory[next_pointer];','memory[pointer] <= write_word;',
                  "assign next_pointer = pointer + PTR_W'(1);",
                  "assign head = (filled == FILL_W'(DEPTH)) ? prefetched : '0;",
                  'advance = rst_n && !out_error && !malformed && !owner_bad;',
                  'phase = in_valid && !frame_start && offset[SHIFT];',
                  'head_upper.generation == expected_generation'):
        if token not in text:raise ValueError('commutator source shape '+token)
    actual=[line.strip() for line in text.splitlines() if 'memory[' in line]
    if actual!=['prefetched <= memory[next_pointer];','memory[pointer] <= write_word;']:
        raise ValueError('unreviewed RAM access')
    return dict(RTL_sha256=SHA,RAM_read='registered lookahead',RAM_payload_reset=False,
                latency='shuffle output k+DEPTH, next consumer k+DEPTH+1',
                qualified_by_native=False)
