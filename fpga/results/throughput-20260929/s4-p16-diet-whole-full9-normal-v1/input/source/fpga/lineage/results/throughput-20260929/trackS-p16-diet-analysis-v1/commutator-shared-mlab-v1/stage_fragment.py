"""Drop-in temporal-stage emission for the sole shared-field generator owner.

Call only at its existing `if depth:` site. This fragment does not alter roots,
butterflies, spatial-stage controls, row calendars, or source-parent selection.
"""
def emit_shared_temporal(stage,depth,swaps):
    swaps=list(swaps);pairs=len(swaps);lanes=[v for pair in swaps for v in pair]
    if pairs<1 or sorted(lanes)!=list(range(2*pairs)) or depth<1 or depth&(depth-1):
        raise ValueError('SHARED_COMM_STAGE_GEOMETRY')
    out=[f'  wire [{pairs*28-1}:0] shared_upper_in,shared_lower_in,shared_upper_out,shared_lower_out;',
         '  wire shared_shuffle_error,shared_shuffle_pending;',
         '  assign shuffle_pending=shared_shuffle_error || shared_shuffle_pending;']
    for k,(lo,hi) in enumerate(swaps):
        out += [f'  assign shared_upper_in[{k*28}+:28]=data[{stage}][{lo*28}+:28];',
                f'  assign shared_lower_in[{k*28}+:28]=data[{stage}][{hi*28}+:28];',
                f'  assign row_data[{lo*28}+:28]=shared_upper_out[{k*28}+:28];',
                f'  assign row_data[{hi*28}+:28]=shared_lower_out[{k*28}+:28];']
    out += [f'  genefer_stream27_mdc_commutator_shared_mlab_v1 #(.PAIRS({pairs}),.DATA_W(28),.PAYLOAD_W(1),',
            f'   .GEN_W(GEN_W),.DEPTH({depth}),.FRAME_T(FRAME_T),.CONTEXTS(1)) shared_shuffle (',
            f'   .clk,.rst_n,.in_slot_valid(slot[{stage}]),.frame_start(start[{stage}]),.quarantine(stop),',
            '   .upper_in(shared_upper_in),.lower_in(shared_lower_in),',
            f"   .upper_payload({pairs}'b0),.lower_payload({pairs}'b0),.context_in(1'b0),",
            f'   .generation_in(generation[{stage}]),.context_enabled,.live_generations(live_generation),',
            '   .out_slot_valid(row_slot),.out_frame_start(row_start),.out_eligible(),',
            '   .out_error(shared_shuffle_error),.fault_pending(shared_shuffle_pending),',
            '   .upper_out(shared_upper_out),.lower_out(shared_lower_out),',
            '   .upper_payload_out(),.lower_payload_out(),.context_out(),.generation_out(row_generation));']
    return out

if __name__=='__main__':
    for p in (8,16):
        for pos in range(p.bit_length()-1):
            swaps=[(i,i^(1<<pos)) for i in range(p) if not i&(1<<pos)]
            lines=emit_shared_temporal(4,32,swaps)
            assert len([x for x in lines if 'assign row_data[' in x])==p
    print('PASS pure wiring fragment: P8/P16 all lane positions, one driver per lane')
