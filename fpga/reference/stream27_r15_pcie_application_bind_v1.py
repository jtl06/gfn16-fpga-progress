"""Private real-shell author. Application functional target is not vendor simulation.

The core remains literal DIRECT65, including its component PCIE_SHELL=0. The
enclosing application/shell declares PCIE_SHELL=1 and forwards every other
parameter/epoch. Full physical bind fails closed until its actual vendor/QSF/
SDC closure is captured; emitting an application test target is not that bind.
"""
import copy
import hashlib
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LEAVES=('rtl/kernel/genefer_stream27_r15_core_transport_v1.sv',
        'rtl/kernel/genefer_stream27_r15_async_fifo_v1.sv',
        'rtl/kernel/genefer_stream27_r15_link_reset_v1.sv')
PORTS='''
 input logic pcie_clk,core_clk,board_perst_n,hip_reset_n,pll_locked,
 input logic [11:0] ctrl_address,input logic ctrl_read,ctrl_write,
 input logic [31:0] ctrl_writedata,input logic [3:0] ctrl_byteenable,
 output logic ctrl_waitrequest,output logic [31:0] ctrl_readdata,output logic ctrl_readdatavalid,
 input logic [21:0] cold_address,input logic cold_write,
 input logic [255:0] cold_writedata,input logic [31:0] cold_byteenable,
 input logic [4:0] cold_burstcount,output logic cold_waitrequest,
 input logic [22:0] export_address,input logic export_read,
 input logic [4:0] export_burstcount,output logic export_waitrequest,
 output logic [255:0] export_readdata,output logic export_readdatavalid
'''


def application(bundle):
    """Source-only vendor-free functional target; real core, adapter and CDC."""
    b=copy.deepcopy(bundle);parent=b['top'];text=b['files'][parent+'.sv']
    if b['parameters'].get('DIRECT_COLD')!=1 or b['parameters'].get('PCIE_SHELL')!=0:
        raise ValueError('R15_SHELL_REQUIRES_LITERAL_DIRECT1_PCIE0_COMPONENT')
    begin=text.index('module '+parent+' #(');end=text.index(') (',begin)
    parent_header=text[begin:end+3]
    if parent_header.count('PCIE_SHELL=0')!=1:
        raise ValueError('R15_SHELL_COMPONENT_FLAG_HEADER')
    header=parent_header.replace('PCIE_SHELL=0','PCIE_SHELL=1',1)
    if header.replace('PCIE_SHELL=1','PCIE_SHELL=0',1)!=parent_header:
        raise ValueError('R15_SHELL_HEADER_REVERSE')
    params=re.findall(r'\b([A-Z][A-Z0-9_]*)=\d+',header)
    if len(params)!=len(set(params)) or not {'AW','P','PCIE_SHELL','DIRECT_COLD'}<=set(params):
        raise ValueError('R15_SHELL_PARAMETER_HEADER')
    top=parent+'_application_v1'
    sv=header.replace('module '+parent+' #(','module '+top+' #(',1)+PORTS+');\n'
    sv+='''
 wire common_reset_n,pcie_ready,core_ready,session_exhausted;
 wire [31:0] session;
 wire [511:0] command_push_data,command_pop_data,response_push_data,response_pop_data;
 wire command_push_valid,command_push_ready,command_pop_valid,command_pop_ready;
 wire response_push_valid,response_push_ready,response_pop_valid,response_pop_ready;
 wire protocol_error,transport_error;
 genefer_stream27_r15_link_reset_v1 reset_fence(.pcie_clk,.core_clk,
  .external_reset_n(board_perst_n && hip_reset_n && pll_locked),
  .common_reset_n,.pcie_ready,.core_ready,.session,.exhausted(session_exhausted));
 genefer_stream27_r15_async_fifo_v1 #(.WIDTH(512),.ADDR_W(3)) command_fifo(
  .rst_n(common_reset_n),.wr_clk(pcie_clk),.rd_clk(core_clk),.wr_enable(pcie_ready),.rd_enable(core_ready),
  .wr_valid(command_push_valid),.wr_data(command_push_data),.wr_ready(command_push_ready),
  .rd_valid(command_pop_valid),.rd_data(command_pop_data),.rd_ready(command_pop_ready));
 genefer_stream27_r15_async_fifo_v1 #(.WIDTH(512),.ADDR_W(3)) response_fifo(
  .rst_n(common_reset_n),.wr_clk(core_clk),.rd_clk(pcie_clk),.wr_enable(core_ready),.rd_enable(pcie_ready),
  .wr_valid(response_push_valid),.wr_data(response_push_data),.wr_ready(response_push_ready),
  .rd_valid(response_pop_valid),.rd_data(response_pop_data),.rd_ready(response_pop_ready));
 genefer_stream27_r15_pcie_avmm_v1 #(.N(1<<AW)) pci_application(
  .clk(pcie_clk),.reset(!common_reset_n),.link_ready(pcie_ready),
  .ctrl_address({52'b0,ctrl_address}),.ctrl_read,.ctrl_write,.ctrl_writedata,.ctrl_byteenable,
  .ctrl_waitrequest,.ctrl_readdata,.ctrl_readdatavalid,
  .cold_address({42'b0,cold_address}),.cold_write,.cold_writedata,.cold_byteenable,.cold_burstcount,.cold_waitrequest,
  .export_address({41'b0,export_address}),.export_read,.export_burstcount,.export_waitrequest,.export_readdata,.export_readdatavalid,
  .cmd_valid(command_push_valid),.cmd_data(command_push_data),.cmd_ready(command_push_ready),
  .resp_valid(response_pop_valid),.resp_data(response_pop_data),.resp_ready(response_pop_ready),.protocol_error);
 wire dc_link_drained,dc_begin,dc_cancel,dc_commit,dc_word_valid,dc_context;
 wire [55:0] dc_owner;
 wire [31:0] dc_session,dc_lease,dc_current_session,dc_count,dc_mask;
 wire [2:0] dc_mode;wire [255:0] dc_profile;
 wire [AW+1:0] dc_index;wire [31:0] dc_word;wire dc_transport_empty;
 wire dc_word_ready,dc_active,dc_error;wire [1:0] dc_loaded,dc_idle;
 wire [31:0] dc_next_epoch,dc_next_lease;wire [15:0] dc_job_generation;wire [AW+2:0] dc_applied;
 wire [1:0] start_contexts,busy,canonical_ready;
 wire command_context,command_valid,command_double,command_ready,command_accept;
 wire [31:0] command_index;wire [7:0] command_generation;
 wire host_context,read_en,read_valid,read_context;wire [AW-1:0] host_addr;
 wire [55:0] read_owner;wire [95:0] read_data;wire core_error;
 genefer_stream27_r15_core_transport_v1 #(.AW(AW),.P(P)) core_transport(
  .clk(core_clk),.rst_n(common_reset_n),.link_ready(core_ready),.session,
  .cmd_valid(command_pop_valid),.cmd_data(command_pop_data),.cmd_ready(command_pop_ready),.cmd_empty(!command_pop_valid),
  .resp_valid(response_push_valid),.resp_data(response_push_data),.resp_ready(response_push_ready),.transport_error,.*);
'''
    connections=','.join('.'+p+'('+('0' if p=='PCIE_SHELL' else p)+')' for p in params)
    sv+=f' {parent} #({connections}) compute(\n'
    sv+='''  .clk(core_clk),.rst_n(common_reset_n),.load_we(1'b0),.write_data(32'b0),
  .batch_mode(2'b0),.feed_mode(2'b0),.double_bit(2'b0),.base(64'b0),.warm_count(64'b0),.double_mask(64'b0),
  .initial_c0({2*P*32{1'b0}}),.initial_c1({2*P*32{1'b0}}),
  .operation_accept(),.done(),.warm_done(),.completed_squares(),.operations_started(),
  .accepted_generation(),.feed_level(),.error(core_error),.cycles(),.canonical_cycles(),.image_copy_cycles(),
  .waiting_final(),.final_image_rows(),.*);
 // synthesis translate_off
 initial if(DIRECT_COLD!=1 || PCIE_SHELL!=1)$fatal(1,"R15_APPLICATION_REQUIRES_DIRECT1_SHELL1");
 // synthesis translate_on
endmodule
'''
    b['files'][top+'.sv']=sv;b['rtl_sources'].append(top+'.sv');b['top']=top
    # Frozen v5 fixes real constantBurstBehavior=false, irrelevant read data,
    # current-edge fault masking, and cross-bus forward progress. The original
    # workspace v1 leaf is intentionally not the production endpoint source.
    role=ROOT/'results/throughput-20260929/trackS-r15-pcie-avmm-native-v5/normal-v5'
    manifest=json.loads((role/'manifest.json').read_bytes())
    endpoint='rtl/kernel/genefer_stream27_r15_pcie_avmm_v1.sv'
    for p,h in manifest['sources'].items():
        captured=role/'source/fpga'/p
        if hashlib.sha256(captured.read_bytes()).hexdigest()!=h:
            raise ValueError('R15_APPLICATION_ENDPOINT_CAPTURE_DRIFT')
        dep=str(captured.relative_to(ROOT))
        b['source_dependencies'].append(dep);b['source_sha256'][dep]=h
    b['files'][Path(endpoint).name]=(role/'source/fpga'/endpoint).read_text()
    b['rtl_sources'].append(Path(endpoint).name)
    for p in LEAVES:
        name=Path(p).name
        if name in b['files']:raise ValueError('R15_SHELL_DUPLICATE_LEAF')
        b['files'][name]=(ROOT/p).read_text();b['rtl_sources'].append(name)
        b['source_dependencies'].append(p);b['source_sha256'][p]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
    self='reference/stream27_r15_pcie_application_bind_v1.py'
    b['source_dependencies'].append(self);b['source_sha256'][self]=hashlib.sha256((ROOT/self).read_bytes()).hexdigest()
    b['parameters']['PCIE_SHELL']=1
    b['generated_sha256']={k:hashlib.sha256(v.encode()).hexdigest() for k,v in b['files'].items()}
    b['r15_shell_application']={'status':'SOURCE_ONLY_NATIVE_PENDING','component_top':parent,
      'component_parameters':bundle['parameters'],'top_parameters':b['parameters'],
      'core_source_preserved':True,'host_format':'canonical96-owned-A32',
      'vendor_simulation_ready':False,'vendor_reason':'Only synthesis HIP/IOPLL files generated; no supported vendor simulator/model qualification. Functional target is actual application/core/CDC only, not a HIP blackbox.',
      'physical_shell_ready':False,'no_image_staging':True,'fifo_words':8,'fifo_bits':512}
    b['r15_host_link']['real_pcie_ip_ready']=False
    return b
