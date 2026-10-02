"""Exact additive T5b source derivation; no simulation or clock claim."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENT = 'genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill'
CORE = PARENT + '_pipe_v1'
PARENT_SHA = 'fc8f381d0db17d3c1bff9ee4b89a99878102099b2c6a404d60157ce2c6b5d6af'


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('T5b unique delta anchor: ' + old[:100])
    return text.replace(old, new, 1)


def generate(root=ROOT):
    raw = (Path(root)/'rtl/kernel'/(PARENT+'.sv')).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError('frozen T5 parent changed')
    s = raw.decode().replace('module '+PARENT+' #', 'module '+CORE+' #', 1)
    s = s.replace('// SOURCE-ONLY T5 candidate: not native/physical qualified.',
        '// SOURCE-ONLY T5b: source row FF + two field-local launch FFs.\n'
        '// Invalidated images are quarantined until reset/reload; already-admitted\n'
        '// rows may write on a fault-detection edge, never after the flush edge.\n'
        '// No clock claim; source registers are not a demonstrated M20K packing result.')
    s = once(s, '    // A descriptor accompanies the committed carry digits through the four\n'
        '    // reducer registers and the existing registered RAM boundary. Accepted\n'
        '    // commit E0 -> reducer output E3 -> boundary E4 -> NTT RAM E5 -> check E6.',
        '    // Source capture E0 -> reducer E1..E4 -> boundary E5 -> field launch\n'
        '    // E6/E7 -> RAM E8 -> registered host-error check E9. II remains one.\n'
        '    // All launch payload and descriptors travel through the SAME registers.')
    s = once(s, '    logic prefill_window,fast_eligible,prefill_complete;', '''    logic prefill_window,fast_eligible,prefill_complete;
    logic source_valid,source_prefill,source_capture;
    logic [AW-1:0] source_addr;
    logic [IO_WIDTH-1:0] source_mask;
    logic [IO_WIDTH*96-1:0] source_words;
    logic [AW:0] conversion_sent,prefill_launched;
    logic boundary_admit;
    (* preserve, dont_merge *) logic [1:0] field_launch_valid[0:2];
    (* preserve, dont_merge *) logic [AW-1:0] field_launch_addr[0:2][0:1];
    (* preserve, dont_merge *) logic [IO_WIDTH-1:0] field_launch_mask[0:2][0:1];
    (* preserve, dont_merge *) logic [IO_WIDTH*32-1:0] field_launch_words[0:2][0:1];
    logic [2:0] field_write_valid;
    logic launch_empty;
    assign launch_empty=(field_launch_valid[0]==0 && field_launch_valid[1]==0 && field_launch_valid[2]==0);
    assign source_capture=(state==CONVERT && (VECTOR_IO ? carry_vector_valid : carry_valid)) ||
        (prefill_window && emit_commit_valid && !prefill_fault && !core_fault);
    // A RAM-output/source register cuts the previous RAM -> bad_digit -> ena cone.
    // Payload is deliberately not reset. A fault flush wins over capture.
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin source_valid<=0;source_prefill<=0;end
        else begin
            source_valid<=source_capture;source_prefill<=prefill_window;
            if(state==FAILED || error || (busy && (core_fault || prefill_fault)) ||
               (state==IDLE && start))source_valid<=0;
        end
    end
    always_ff @(posedge clk)if(rst_n && source_capture)begin
        source_addr<=emit_commit_addr;
        source_mask<=prefill_window ? emit_commit_mask : (VECTOR_IO ? carry_vector_mask : IO_MASK);
        for(int h=0;h<IO_WIDTH;h=h+1)
            source_words[h*96+:96]<=prefill_window ? emit_commit_data[h*96+:96] :
                (VECTOR_IO ? carry_vector_output[h*96+:96] : carry_output);
    end''')
    s = once(s, '        !prefill_boundary_valid && conversion_valid==0 &&',
        '        !source_valid && !prefill_boundary_valid && conversion_valid==0 && launch_empty &&')
    s = once(s, '            if(emit_commit_valid && (bad_digit || emit_commit_mask!=IO_MASK ||',
        '            if(source_valid && source_prefill && bad_digit)prefill_fault=1;\n'
        '            if(emit_commit_valid && (emit_commit_mask!=IO_MASK ||')
    s = once(s, '               prefill_boundary_addr!=AW\'(prefill_written) ||\n'
        '               int\'(prefill_written)>=N))prefill_fault=1;',
        '               prefill_boundary_addr!=AW\'(prefill_launched) ||\n'
        '               int\'(prefill_launched)>=N))prefill_fault=1;')
    s = once(s, '            if(carry_success && prefill_pipe_valid==0 && !prefill_boundary_valid &&\n'
        '               conversion_valid==0 && int\'(prefill_written)!=N)prefill_fault=1;',
        '            if(carry_success && !source_valid && prefill_pipe_valid==0 && !prefill_boundary_valid &&\n'
        '               conversion_valid==0 && launch_empty && int\'(prefill_written)!=N)prefill_fault=1;')
    s = once(s, '    assign prefill_accept=prefill_window && emit_commit_valid && !prefill_fault && !core_fault;\n'
        '    assign prefill_commit=prefill_window && prefill_boundary_valid &&\n'
        '        (&conversion_valid) && !prefill_fault && !core_fault;',
        '    assign prefill_accept=prefill_window && source_valid && source_prefill && !prefill_fault && !core_fault;\n'
        '    assign boundary_admit=((state==CONVERT && (&conversion_valid) && !bad_digit) ||\n'
        '        (prefill_window && prefill_boundary_valid && (&conversion_valid))) && !prefill_fault && !core_fault;\n'
        '    // Do not reconnect combinational global fault to the physical RAM write enable.\n'
        '    assign prefill_commit=prefill_window && (&field_write_valid);')
    s = once(s, '            prefill_issued<=0;prefill_written<=0;prefill_pipe_valid<=0;prefill_boundary_valid<=0;',
        '            prefill_issued<=0;prefill_written<=0;prefill_pipe_valid<=0;prefill_boundary_valid<=0;\n'
        '            conversion_sent<=0;prefill_launched<=0;')
    s = once(s, '                prefill_pipe_addr[0]<=emit_commit_addr;\n'
        '                prefill_pipe_mask[0]<=emit_commit_mask;\n'
        '                prefill_issued<=prefill_issued+(AW+1)\'(IO_STEP);',
        '                prefill_pipe_addr[0]<=source_addr;\n'
        '                prefill_pipe_mask[0]<=source_mask;')
    s = once(s, '            if(prefill_commit)prefill_written<=prefill_written+(AW+1)\'(IO_STEP);',
        '            if(prefill_window && source_capture)prefill_issued<=prefill_issued+(AW+1)\'(IO_STEP);\n'
        '            if(boundary_admit && prefill_window)prefill_launched<=prefill_launched+(AW+1)\'(IO_STEP);\n'
        '            if(boundary_admit && state==CONVERT)conversion_sent<=conversion_sent+(AW+1)\'(IO_STEP);\n'
        '            if(prefill_commit)prefill_written<=prefill_written+(AW+1)\'(IO_STEP);')
    s = once(s, '                prefill_issued<=0;prefill_written<=0;carry_success<=0;',
        '                prefill_issued<=0;prefill_written<=0;carry_success<=0;\n'
        '                conversion_sent<=0;prefill_launched<=0;')
    s = once(s, '    assign convert_input_valid=prefill_window ? emit_commit_valid : (VECTOR_IO ? carry_vector_valid : carry_valid);\n'
        '    assign convert_mask=prefill_window ? emit_commit_mask : (VECTOR_IO ? carry_vector_mask : IO_MASK);',
        '    assign convert_input_valid=source_valid;\n    assign convert_mask=source_mask;')
    s = once(s, '        assign carry_words[h]=prefill_window ? $signed(emit_commit_data[h*96+:96]) :\n'
        '            (VECTOR_IO ? $signed(carry_vector_output[h*96+:96]) : carry_output);',
        '        assign carry_words[h]=$signed(source_words[h*96+:96]);')
    s = once(s, 'carry_start=(state==CONVERT && (&conversion_valid)',
        'carry_start=(state==CONVERT && (&field_write_valid)')
    s = once(s, '        assign conversion_valid[f]=convert_valid_words[f][0];', '''        assign conversion_valid[f]=convert_valid_words[f][0];
        assign field_write_valid[f]=field_launch_valid[f][1];
        // Field-local admission and physical launch registers: control and data
        // share both edges. Clearing valid never fabricates replacement payload.
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)field_launch_valid[f]<=0;
            else begin
                field_launch_valid[f]<={field_launch_valid[f][0],boundary_admit};
                if(state==FAILED || error || (busy && (core_fault || prefill_fault)) ||
                   (state==CONVERT && bad_digit) || (state==IDLE && start))
                    field_launch_valid[f]<=0;
            end
        end
        always_ff @(posedge clk)if(rst_n)begin
            if(boundary_admit)begin
                field_launch_addr[f][0]<=prefill_window ? prefill_boundary_addr : AW'(conversion_sent);
                field_launch_mask[f][0]<=prefill_window ? prefill_boundary_mask : IO_MASK;
                field_launch_words[f][0]<=convert_words[f];
            end
            if(field_launch_valid[f][0])begin
                field_launch_addr[f][1]<=field_launch_addr[f][0];
                field_launch_mask[f][1]<=field_launch_mask[f][0];
                field_launch_words[f][1]<=field_launch_words[f][0];
            end
        end''')
    s = once(s, '        assign ntt_load=(state==CONVERT && conversion_valid[f]) || prefill_commit;',
        '        assign ntt_load=(state==CONVERT || prefill_window) && field_write_valid[f];')
    s = once(s, '        assign addr=prefill_window ? prefill_boundary_addr :\n'
        '            (state==CONVERT ? AW\'(write_count) : AW\'(issue_count));',
        '        assign addr=(prefill_window || state==CONVERT) ? field_launch_addr[f][1] : AW\'(issue_count);')
    s = once(s, '        assign data=conversion_data[f];', '        assign data=field_launch_words[f][1][31:0];')
    s = once(s, '.vector_lane_mask(prefill_window ? prefill_boundary_mask : IO_MASK),.vector_write_data(convert_words[f]),',
        '.vector_lane_mask((prefill_window || state==CONVERT) ? field_launch_mask[f][1] : IO_MASK),.vector_write_data(field_launch_words[f][1]),')
    s = once(s, '                    if(&conversion_valid) begin', '                    if(&field_write_valid) begin')
    return s


def validate(root=ROOT):
    root = Path(root)
    path = root/'rtl/kernel'/(CORE+'.sv')
    if path.read_text() != generate(root):
        raise ValueError('T5b exact source delta mismatch')
    return dict(status='source_only_not_native_qualified', parent_sha256=PARENT_SHA,
                core_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                source_to_ram_edges=8, parent_source_to_ram_edges=5,
                cold_conversion_delta=3, prefill_drain_delta=3,
                steady_state_row_ii=1, estimated_added_payload_bits=1536+3072,
                quarantined_fault_edge_write_allowed=True)


if __name__ == '__main__':
    import argparse, json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emit-patch', action='store_true')
    args = parser.parse_args()
    if args.emit_patch:
        path = ROOT/'rtl/kernel'/(CORE+'.sv')
        if path.exists(): raise ValueError('fresh additive source required')
        print('*** Begin Patch\n*** Add File: '+str(path))
        for line in generate().splitlines(): print('+'+line)
        print('*** End Patch')
    else: print(json.dumps(validate(), indent=2))
