"""Statically closed board wiring for the ACTUALLY generated R15 Qsys system.

This is not a vendor simulation surrogate. Every generated input/output is
classified; unfamiliar ports or widths fail. No new external pins are invented.
"""
import hashlib
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SYSTEM='r15_pcie_system_v1'
TOP='genefer_stream27_r15_pcie_board_v1'
GENERATED='results/throughput-20260929/r15-pcie-system-generation-v1-artifacts/r15_pcie_system_v1/synth/r15_pcie_system_v1.v'
PIN='071e4fe542db8aa0ba9d522a46cfe3b3252683c5940b8aa377b165c6e7aaf059'
RECEIPT='results/throughput-20260929/r15-pcie-system-generation-v1.json'
RECEIPT_PIN='626e5d7a7bd5c7a9cfd149e6101b374e42d9b90a76a5bb9b12a66d0ac856ad8a'


def emit():
    raw=(ROOT/GENERATED).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PIN or hashlib.sha256((ROOT/RECEIPT).read_bytes()).hexdigest()!=RECEIPT_PIN:
        raise ValueError('R15_BOARD_GENERATED_IDENTITY')
    text=raw.decode().split('module '+SYSTEM+' (',1)[1].split('\n\t);',1)[0]
    ports=re.findall(r'\b(input|output)\s+wire\s*(?:\[(\d+):0\])?\s*(\w+)\s*[, ]',text)
    if len(ports)!=text.count('//') or len({p[2] for p in ports})!=len(ports):
        raise ValueError('R15_BOARD_PORT_PARSE')
    fixed={
      'app_board_perst_n':(1,'pcie1_perstn','application common reset authority'),
      'core_pll_refclk':(1,'clk_u59','pinned100MHz board oscillator'),
      'core_pll_rst':(1,'!pcie1_perstn','active-high PLL reset'),
      'pcie_refclk':(1,'clk_pcie1','pinned100MHz PCIe differential reference'),
      'pcie_npor':(1,"1'b1",'pinned community npor tie; PERST separate'),
      'pcie_pin_perst':(1,'pcie1_perstn','pinned board PERST'),
      'pcie_test_in':(32,"32'h00000188",'A10 DMA guide683425 recommended hardware test vector; simulation bit0clear'),
      'pcie_simu_mode_pipe':(1,"1'b0",'real serial PHY, not PIPE simulation'),
      'pcie_sim_pipe_pclk_in':(1,"1'b0",'inactive simulation clock'),
    }
    pipe_in={'phystatus':1,'rxdata':32,'rxdatak':4,'rxelecidle':1,'rxstatus':3,
             'rxvalid':1,'rxdataskip':1,'rxblkst':1,'rxsynchd':2}
    pipe_out={'eidleinfersel':3,'powerdown':2,'rxpolarity':1,'txcompl':1,'txdata':32,
              'txdatak':4,'txdetectrx':1,'txelecidle':1,'txdeemph':1,'txmargin':3,
              'txswing':1,'currentcoeff':18,'currentrxpreset':3,'txsynchd':2,
              'txblkst':1,'txdataskip':1,'rate':2}
    unused_out={'pcie_sim_pipe_rate':2,'pcie_sim_ltssmstate':5,
                'pcie_cra_readdata_o':32,'pcie_cra_waitrequest_o':1}
    cra_in={'pcie_cra_chipselect_i':1,'pcie_cra_address_i':14,'pcie_cra_byteenable_i':4,
            'pcie_cra_read_i':1,'pcie_cra_write_i':1,'pcie_cra_writedata_i':32}
    lines=[];proof={}
    for direction,hi,name in ports:
        width=int(hi)+1 if hi else 1
        if name in fixed:
            wanted,value,reason=fixed[name];want_direction='input'
        elif name in cra_in:
            wanted=cra_in[name];value=f"{wanted}'b0";want_direction='input'
            reason='unused optional CRA slave; no request/chipselect and no external pin'
        elif name in unused_out:
            wanted=unused_out[name];value='';want_direction='output';reason='unused debug/CRA result, no external pin'
        else:
            m=re.fullmatch(r'pcie_(rx_in|tx_out|'+ '|'.join(pipe_in)+'|'+'|'.join(pipe_out)+r')([0-7])',name)
            if not m:raise ValueError('R15_BOARD_UNKNOWN_PORT '+name)
            family,lane=m.groups()
            if family=='rx_in':wanted=1;value=f'pcie1_rx[{lane}]';want_direction='input';reason='actual serial receiver lane'
            elif family=='tx_out':wanted=1;value=f'pcie1_tx[{lane}]';want_direction='output';reason='actual serial transmitter lane'
            elif family in pipe_in:wanted=pipe_in[family];value=f"{wanted}'b0";want_direction='input';reason='inactive PIPE simulation input, simu_mode_pipe=0'
            else:wanted=pipe_out[family];value='';want_direction='output';reason='unused PIPE observation output'
        if width!=wanted or direction!=want_direction:
            raise ValueError('R15_BOARD_PORT_TYPE '+name)
        lines.append(f'  .{name}({value})')
        proof[name]={'direction':direction,'width':width,'connection':value,'reason':reason}
    sv=f'''// Real I/O board wrapper over actual vendor-generated system, not a stub.
// Source-time fixed AW16/P16/C2/allON; effective parameters are captured by
// the Qsys application metadata. No fictitious top-level parameter overrides.
module {TOP}(
 input wire clk_u59,clk_pcie1,pcie1_perstn,
 input wire [7:0] pcie1_rx,output wire [7:0] pcie1_tx
);
 {SYSTEM} system_i(
'''+',\n'.join(lines)+'\n );\nendmodule\n'
    return sv,{'schema':'r15-board-static-wiring-v1','status':'SOURCE_ONLY_NOT_NATIVE_OR_FITTED',
      'top':TOP,'system_top':SYSTEM,'generated_top_path':GENERATED,'generated_top_sha256':PIN,
      'generation_receipt':RECEIPT,'generation_receipt_sha256':RECEIPT_PIN,
      'ports':proof,'source_sha256':hashlib.sha256(sv.encode()).hexdigest(),
      'physical_input_clocks_hz':{'clk_u59':100000000,'clk_pcie1':100000000},
      'physical_epoch_defaults':[0,0],'vendor_simulation_claim':False,'hardware_claim':False,
      'reset_delivery':'PERST/HIP reset/PLL lock only; VFIO/FLR/MMIO soft-reset delivery unqualified',
      'unused_CRA_warning':'Retained generated warning; optional slave tied inactive. No CRA software access claimed.'}
