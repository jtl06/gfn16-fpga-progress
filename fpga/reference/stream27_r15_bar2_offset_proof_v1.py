"""Source-bound BAR2 offset projection, distinct from internal DMA addresses.

BAR2 commands are already classified by the vendor PCIe BAR decoder. Their
upper address is the host-assigned BAR base, NOT a software DMA aperture index.
This proof trusts the instantiated hard-IP BAR semantics, not a HIP simulation.
"""
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/r15-pcie-system-generation-v1-artifacts'
IP='ip/r15_pcie_system_v1/r15_pcie_system_v1_pcie/'
SYN=IP+'altera_pcie_a10_hip_2023/synth/'


def proof(base=None,system='r15_pcie_system_v1'):
    if system not in ('r15_pcie_system_v1','r15_pcie_system_v2'):
        raise ValueError('R15_BAR2_SYSTEM')
    base=BASE if base is None else Path(base).resolve()
    ip='ip/'+system+'/'+system+'_pcie/'
    syn=ip+'altera_pcie_a10_hip_2023/synth/'
    checks={
      ip+'synth/'+system+'_pcie.v':[
        '.bar2_address_width_mux_hwtcl                         (12)',
        '.bar2_type                                            ("bar2_32bit_non_prefetch_mem")'],
      syn+'altpcieav_dma_rxm.sv':[
        'assign  bar_decode    = RxFifoDataq_i[265:260];',
        'bar_decode_reg     <= (rx_sop) ? bar_decode : bar_decode_reg;',
        'assign RxmWrite_2_o = rxm_wr_ena & bar_decode_reg[2];',
        'assign RxmRead_2_o  = rxm_rd_ena & bar_decode_reg[2];',
        'assign RxmAddress_2_o = rx_addr_sel[BAR2_TYPE-1:0];'],
      syn+'altpcieav_256_app.sv':['.BAR2_SIZE_MASK        (BAR2_SIZE_MASK)',
                                '.RxmAddress_2_o         (AvRxmAddress_2_o'],
    }
    pins={}
    for p,anchors in checks.items():
        raw=(base/p).read_bytes();text=raw.decode()
        if not all(a in text for a in anchors):raise ValueError('R15_BAR2_SOURCE_ANCHOR '+p)
        pins[p]=hashlib.sha256(raw).hexdigest()
    for base in (0,0x80000000,0xfffff000):
        for offset in (0,4,0x40,0xffc):
            assert (base+offset)&0xfff==offset
    return {'schema':'r15-bar2-offset-source-proof-v1',
      'status':'SOURCE_BOUND_VENDOR_BAR_DECODE_ASSUMPTION',
      'sources':pins,'bar':2,'aperture_bytes':4096,'prefetchable':False,
      'address_semantics':'full host TLP address; low12 is offset only after vendor BAR2 hit',
      'trusted_authority':'actual hard-IP BAR2 decoder configured32-bit nonprefetchable12-bit aperture',
      'not_assumed':'upper64 address bits zero; rejecting nonzero BAR base would reject legitimate MMIO',
      'boundary_note':'ordinary RXM accepts one DWORD accesses; endpoint further validates alignment/BE/CSR offsets',
      'native_HIP_execution_claim':False,'hardware_validation_claim':False,
      'primary_reference':'https://www.intel.com/programmable/technical-pdfs/683425.pdf'}
