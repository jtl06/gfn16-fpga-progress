"""Simulation-only three-field profile/completion fault seam bindings."""
import hashlib
from pathlib import Path
from fpga.reference.anext_core_source_v1 import verify as direct_verify
ROOT=Path(__file__).resolve().parents[1]
SEQ='rtl/tb/genefer_anext_control_seq_probe_v1.sv'
BACK='rtl/tb/genefer_anext_control_backend_probe_v1.sv'
CORE='rtl/tb/genefer_anext_control_fault_probe_v1.sv'
def once(t,a,b):
    if t.count(a)!=1:raise ValueError('unique integration seam '+a)
    return t.replace(a,b)

def sources():
    direct_verify()
    seq=(ROOT/'rtl/kernel/genefer_anext_ntt_sequencer_v1.sv').read_text().replace('genefer_anext_ntt_sequencer_v1','genefer_anext_control_seq_probe_v1')
    seq=once(seq,'    input logic clk,rst_n,cancel,start_ntt,','    input logic sim_header_corrupt,sim_drop_done,sim_child_error,\n    input logic clk,rst_n,cancel,start_ntt,')
    seq=once(seq,'logic [31:0] rom_data[0:2],expected_header[0:2];','logic [31:0] rom_data[0:2],expected_header[0:2],raw_rom_data[0:2];')
    seq=once(seq,'logic [2:0] ntt_busy,ntt_done,ntt_error,ntt_host_error,block_errors;',
      '''logic [2:0] ntt_busy,ntt_done,ntt_error,ntt_host_error,block_errors;
    logic [2:0] raw_ntt_done,raw_ntt_error;
    assign ntt_done=raw_ntt_done & (sim_drop_done ? 3'b110 : 3'b111);
    assign ntt_error=raw_ntt_error | (sim_child_error ? 3'b001 : 3'b000);''')
    seq=once(seq,'    for(genvar f=0;f<3;f=f+1)begin: field_lane','    for(genvar f=0;f<3;f=f+1)begin: field_lane\n        assign rom_data[f]=raw_rom_data[f] ^ ((f==0 && sim_header_corrupt) ? 32\'d1 : 32\'d0);')
    seq=once(seq,'.word_addr(rom_addr[f]),.word_data(rom_data[f])','.word_addr(rom_addr[f]),.word_data(raw_rom_data[f])')
    seq=once(seq,'.done(ntt_done[f]),.error(ntt_error[f]),','.done(raw_ntt_done[f]),.error(raw_ntt_error[f]),')
    backend=(ROOT/'rtl/kernel/genefer_anext_square_backend_v1.sv').read_text().replace('genefer_anext_square_backend_v1','genefer_anext_control_backend_probe_v1').replace('genefer_anext_ntt_sequencer_v1','genefer_anext_control_seq_probe_v1')
    backend=once(backend,'    input logic clk,rst_n,begin_square,cancel,double_bit,prefilled,','    input logic sim_header_corrupt,sim_drop_done,sim_child_error,\n    input logic clk,rst_n,begin_square,cancel,double_bit,prefilled,')
    backend=once(backend,'.clk,.rst_n,.cancel(child_cancel),.start_ntt,','.clk,.rst_n,.sim_header_corrupt,.sim_drop_done,.sim_child_error,.cancel(child_cancel),.start_ntt,')
    core=(ROOT/'rtl/kernel/genefer_anext_core_v1.sv').read_text().replace('genefer_anext_core_v1','genefer_anext_control_fault_probe_v1').replace('genefer_anext_square_backend_v1','genefer_anext_control_backend_probe_v1')
    core=once(core,'    input logic clk,rst_n,cmd_valid,rsp_ready,','''    input logic sim_header_corrupt,sim_drop_done,sim_child_error,
    output logic [3:0] monitor_state,
    output logic [2:0] monitor_step,monitor_child_done,monitor_ram_read,monitor_ram_write,
    output logic monitor_word_valid,monitor_cache,monitor_seq_error,
    output logic [15:0] monitor_word,
    input logic clk,rst_n,cmd_valid,rsp_ready,''')
    core=once(core,'.clk,.rst_n,.begin_square(square_begin),.cancel(square_cancel),','.clk,.rst_n,.sim_header_corrupt,.sim_drop_done,.sim_child_error,.begin_square(square_begin),.cancel(square_cancel),')
    core=once(core,'endmodule','''    assign monitor_state=4'(square_backend.sequencer.state);
    assign monitor_step=square_backend.sequencer.step;
    assign monitor_child_done=square_backend.sequencer.raw_ntt_done;
    assign monitor_word_valid=&square_backend.sequencer.rom_valid;
    assign monitor_word=square_backend.sequencer.profile_words_loaded;
    assign monitor_cache=square_backend.sequencer.profile_cache_valid;
    assign monitor_seq_error=square_backend.seq_error;
    for(genvar f=0;f<3;f=f+1)begin: physical_RAM_observer
        assign monitor_ram_read[f]=|square_backend.sequencer.field_lane[f].engine.data_re;
        assign monitor_ram_write[f]=|square_backend.sequencer.field_lane[f].engine.data_we;
    end
endmodule''')
    return {SEQ:seq,BACK:backend,CORE:core}

def verify():
    for name,text in sources().items():
        if (ROOT/name).read_text()!=text:raise ValueError('unexpected integration fault probe delta')
    return dict(source_only=True,physical_top_allowed=False,arithmetic_changes=0)
