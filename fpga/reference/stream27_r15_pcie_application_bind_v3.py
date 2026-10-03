"""Private additive application ingress for a pre-router aperture fault.

No new arithmetic or CDC. The external PCIe-domain fault enters the endpoint's
existing ordered one-ABORT path; already-admitted commands are not flushed.
"""
import hashlib
from .stream27_r15_pcie_application_bind_v2 import application as previous, ROOT

SELF='reference/stream27_r15_pcie_application_bind_v3.py'


def application(bundle):
    from . import stream27_r15_pcie_avmm_v7 as endpoint
    b=previous(bundle)
    old=b['top'];top=old.removesuffix('_v2')+'_v3'
    text=b['files'].pop(old+'.sv');original=text
    pairs=[('module '+old+' #(', 'module '+top+' #('),
      (' input logic pcie_clk,core_clk,board_perst_n,hip_reset_n,pll_locked,',
       ' input logic pcie_clk,core_clk,board_perst_n,hip_reset_n,pll_locked,\n'
       ' input logic external_fault_valid,output logic external_fault_ready,'),
      ('.clk(pcie_clk),.reset(!pcie_reset_n),.link_ready(pcie_ready),',
       '.clk(pcie_clk),.reset(!pcie_reset_n),.link_ready(pcie_ready),\n'
       '  .external_fault_valid,.external_fault_ready,')]
    for before,after in pairs:
        if text.count(before)!=1:raise ValueError('R15_APP_V3_ANCHOR '+before)
        text=text.replace(before,after)
    reverse=text
    for before,after in reversed(pairs):reverse=reverse.replace(after,before)
    if reverse!=original:raise ValueError('R15_APP_V3_REVERSE')
    b['files'][top+'.sv']=text;b['top']=top
    b['rtl_sources']=[top+'.sv' if p==old+'.sv' else p for p in b['rtl_sources']]
    b['files']['genefer_stream27_r15_pcie_avmm_v1.sv']=endpoint.source().decode()
    deps=[SELF,'rtl/kernel/genefer_stream27_r15_pcie_avmm_v1.sv']
    deps += [f'reference/stream27_r15_pcie_avmm_v{v}.py' for v in range(2,8)]
    for p in deps:
        b['source_dependencies'].append(p)
        b['source_sha256'][p]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
    b['generated_sha256']={p:hashlib.sha256(s.encode()).hexdigest() for p,s in b['files'].items()}
    b['r15_shell_application'].update(application_version=3,endpoint_version=7,
        predecessor_application_top=old,predecessor_wrapper_exact_reverse=True,
        external_fault_domain='pcie_clk',external_fault_delivery='ordered existing ABORT, no pipeline flush',
        aperture_guard_external=True)
    return b
