"""Native-only cold numeric-fault seam; actual host/three fields/RAM retained."""
import re
from fpga.reference import anext_cold_legality_v1 as s
ROOT=s.ROOT
TOP='genefer_anext_coldleg_fault_probe_v1'
BACK='rtl/tb/genefer_anext_coldleg_fault_backend_v1.sv'
SV='rtl/tb/'+TOP+'.sv'
CPP='rtl/tb/anext_cold_legality_fault_v1.cpp'
CASES=('numeric-first','numeric-final','upper33-final','double-meta','double-image','double-transfer',
       'cancel-on-response','cancel-after-source','cancel-pending')

def expected():
    s.verify();b=(ROOT/s.BACKEND).read_text()
    b=s.once(b,'module genefer_anext_coldleg_backend_v1','module genefer_anext_coldleg_fault_backend_v1')
    b=s.once(b,'    input logic clk,rst_n,begin_square,cancel,double_bit,prefilled,',
      '''    input logic [2:0] sim_fault_mode,
    input logic [AW-1:0] sim_fault_offset,
    input logic [3:0] sim_fault_lane,
    input logic [32:0] sim_fault_word,
    input logic clk,rst_n,begin_square,cancel,double_bit,prefilled,''')
    b=s.once(b,'    genefer_anext_cold_prefill_sourcecheck_v1 #(.AW(AW)) cold_prefill (',
      '''    // Native-only response corruption. No force/release, mock field or physical use.
    wire sim_match=compute_read_valid && compute_read_tag_out==sim_fault_offset;
    logic [527:0] sim_words;
    always_comb begin
        sim_words=compute_read_words;
        if(sim_fault_mode!=0 && sim_match)sim_words[int'(sim_fault_lane)*33+:33]=sim_fault_word;
    end
    genefer_anext_cold_prefill_sourcecheck_v1 #(.AW(AW)) cold_prefill (''')
    b=s.once(b,'.image_read_valid(compute_read_valid),.image_error(compute_memory_error),',
      '.image_read_valid(compute_read_valid),.image_error(compute_memory_error || (sim_fault_mode==3 && sim_match)),')
    b=s.once(b,'.image_read_generation(compute_read_generation),.image_read_words(compute_read_words),',
      '.image_read_generation(compute_read_generation ^ ((sim_fault_mode==2 && sim_match) ? 32\'d1 : 32\'d0)),.image_read_words(sim_words),')
    b=s.once(b,'.field_write_words(prefill_words),.transfer_quiet,.transfer_error',
      '.field_write_words(prefill_words),.transfer_quiet,.transfer_error(transfer_error || (sim_fault_mode==4 && sim_match))')
    c=(ROOT/s.CORE).read_text()
    c=s.once(c,'module genefer_anext_coldleg_core_v1','module '+TOP)
    c=s.once(c,'genefer_anext_coldleg_backend_v1 #','genefer_anext_coldleg_fault_backend_v1 #')
    c=s.once(c,'    input logic clk,rst_n,cmd_valid,rsp_ready,',
      '''    input logic sim_cancel,
    input logic [2:0] sim_fault_mode,
    input logic [AW-1:0] sim_fault_offset,
    input logic [3:0] sim_fault_lane,
    input logic [32:0] sim_fault_word,
    output logic monitor_match,monitor_fault,monitor_prefill_done,monitor_prefill_error,
    output logic monitor_bad_reducer,monitor_bad_field_write,monitor_start,monitor_cache,
    output logic monitor_image_write,monitor_transfer_pending,
    output logic [2:0] monitor_read,monitor_write,
    input logic clk,rst_n,cmd_valid,rsp_ready,''')
    c=s.once(c,'.clk,.rst_n,.begin_square(square_begin),.cancel(square_cancel),',
      '.clk,.rst_n,.sim_fault_mode,.sim_fault_offset,.sim_fault_lane,.sim_fault_word,.begin_square(square_begin),.cancel(square_cancel || sim_cancel),')
    c=s.once(c,'endmodule','''    assign monitor_match=square_backend.sim_match;
    assign monitor_fault=square_backend.cold_prefill.fault;
    assign monitor_prefill_done=square_backend.prefill_done;
    assign monitor_prefill_error=square_backend.prefill_error;
    assign monitor_start=square_backend.start_ntt;
    assign monitor_cache=square_backend.sequencer.profile_cache_valid;
    assign monitor_transfer_pending=|square_backend.transfers.request_write;
    assign monitor_image_write=host.image.write_accept;
    assign monitor_bad_reducer=square_backend.cold_prefill.pipeline_rst_n &&
        square_backend.cold_prefill.capture_valid[1] &&
        square_backend.cold_prefill.destination_tag==sim_fault_offset;
    assign monitor_bad_field_write=(|monitor_write) && square_backend.field_write_offset==sim_fault_offset;
    for(genvar f=0;f<3;f=f+1)begin: native_observer
        wire [127:0] physical_write;
        assign monitor_read[f]=|square_backend.sequencer.field_lane[f].engine.data_re;
        for(genvar bank=0;bank<128;bank=bank+1)begin: RAM_observer
            assign physical_write[bank]=square_backend.sequencer.field_lane[f].engine.memories[bank].ram_write_en;
        end
        assign monitor_write[f]=|physical_write;
    end
endmodule''')
    return {BACK:b,SV:c}

def verify():
    for n,t in expected().items():s.need((ROOT/n).read_text()==t,'COLDLEG_NATIVE_FIXTURE '+n)
    return dict(physical_top_allowed=False,actual_fields=3,force_release=False)

def validate(stdout,stderr,rc,config,assets):
    s.need(set(config)=={'aw','case'} and config['aw'] in (5,8) and not assets,'COLDLEG_NATIVE_CONFIG')
    if config['case']=='negative-edge':
        s.need(rc==1 and stdout=='' and stderr=='COLDLEG_NUMERIC_EDGE_CONTRACT\n','COLDLEG_TYPED_NEGATIVE')
        return dict(status='PASS_expected_contracts',aw=config['aw'],case=config['case'],promotion_allowed=False)
    s.need(config['case'] in CASES,'COLDLEG_NATIVE_CASE')
    m=re.fullmatch(r'COLDLEG_FAULT_PASS aw=([58]) case=([a-z0-9-]+) fields=3 raw_delta=([01]) invalid_reducer=0 invalid_ram=0 quiet=16 reload_words=([0-9]+) recovery_ntt=([0-9]+) ticks=([1-9][0-9]*)\n',stdout)
    s.need(type(rc) is int and rc==0 and stderr=='' and m and int(m[1])==config['aw'] and m[2]==config['case'],'COLDLEG_TYPED_NATIVE')
    aw=config['aw'];delta=int(config['case'] in ('numeric-first','numeric-final','upper33-final','cancel-after-source'))
    groups=max(1,(1<<aw)//128);ntt=2*aw*(groups+10)+((1<<aw)+63)//64+15
    s.need(int(m[3])==delta and int(m[4])==(1<<aw) and int(m[5])==ntt and int(m[6])<1000000,'COLDLEG_EDGE_AND_RECOVERY')
    return dict(status='PASS_expected_contracts',aw=aw,case=m[2],numeric_edge_delta=delta,recovery_words=1<<aw,
      recovery_ntt=ntt,quiet_edges=16,actual_bad_reducer=0,actual_bad_RAM=0,promotion_allowed=False)

def write():
    e=expected()
    for n in e:s.need(not (ROOT/n).exists(),'COLDLEG_NATIVE_FRESH '+n)
    for n,t in e.items():
        with (ROOT/n).open('x') as f:f.write(t)
    return verify()

if __name__=='__main__':
    import json
    print(json.dumps(write(),indent=2))
