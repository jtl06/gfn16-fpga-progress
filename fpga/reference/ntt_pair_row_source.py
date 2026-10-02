"""Reviewed exact source delta for the isolated row-only RTL candidate."""
BASELINE_SHA256 = 'f056b8dc9cdc971ea5360560228354d88060d4d042b8d2f829c2e8644dfb73d0'
BENCH_SHA256 = '02e05022ade3591924f94909ae61039bd97672903fb74f980bfaa72f168ed336'


def row_source(source):
    edits = [
        ('// Checked variant: expected-token validity detects loss of all fallback/point outputs.',
         '// Row-only variant: setup-decoded data rows; root routing and timing unchanged.'),
        ('module genefer_ntt_banked27_pair_checked_engine #(', 'module genefer_ntt_banked27_pair_row_engine #('),
        ('    logic [AW-1:0] fixed_mask;',
         '    logic [AW-1:0] fixed_mask;\n    logic [RW-1:0] row_masks[0:1],transform_row[0:BANKS-1];\n    logic [PW-1:0] row_coordinates[0:1];'),
        ('    function automatic logic [31:0] bank_address(input logic [KW-1:0] b);',
         '    // synthesis translate_off\n    function automatic logic [31:0] bank_address(input logic [KW-1:0] b);'),
        ('    assign setup_pair=LANES>1', '    // synthesis translate_on\n    assign setup_pair=LANES>1'),
        ('        logic [31:0] bf_address,root_address;',
         '        logic [31:0] root_address;\n        logic [KW-1:0] row_variable;'),
        ("        assign bf_address=bank_address(KW'(bank));",
         "        assign row_variable=KW'(bank)^base_bank;\n"
         "        assign transform_row[bank]=RW'(base_addr>>KW) |\n"
         "            (row_variable[row_coordinates[0]] ? row_masks[0] : RW'(0)) |\n"
         "            (row_variable[row_coordinates[1]] ? row_masks[1] : RW'(0));\n"
         "        // synthesis translate_off\n"
         "        logic [31:0] bf_address;\n"
         "        assign bf_address=bank_address(KW'(bank));\n"
         "        always_ff @(posedge clk) if(rst_n && transform_read && 32'(bank)<n)\n"
         "            if(transform_row[bank]!=RW'(bank_address(KW'(bank))>>KW))\n"
         "                $fatal(1,\"row-only decode identity mismatch\");\n"
         "        // synthesis translate_on"),
        ("data_ra[bank]=RW'(bf_address>>KW);", 'data_ra[bank]=transform_row[bank];'),
        ("transform_read ? RW'(bank_address(KW'(b))>>KW) : data_ra[b]", 'transform_read ? transform_row[b] : data_ra[b]'),
        ('layer_shift[i]<=0;layer_mask[i]<=0;end', 'layer_shift[i]<=0;layer_mask[i]<=0;row_masks[i]<=0;row_coordinates[i]<=0;end'),
        ("                        layer_shift[layer]<=5'(shift);",
         "                        layer_shift[layer]<=5'(shift);\n"
         "                        row_coordinates[layer]<=PW'(s%KW);\n"
         "                        row_masks[layer]<=((layer==0 || setup_pair) && s>=KW) ? (RW'(1)<<(s-KW)) : RW'(0);")
    ]
    for old, new in edits:
        if source.count(old) != 1:
            raise ValueError('ambiguous row-only source delta: ' + old)
        source = source.replace(old, new)
    # Normalize final blank lines only; this is part of the recorded delta.
    return source.rstrip() + '\n'
