"""Additive application: synchronized domain resets and endpoint v6.

The literal DIRECT65 component and v1 capture are unchanged. This is still
an actual-application/CDC functional target, NOT execution of vendor HIP IP.
"""
import hashlib
import json
from pathlib import Path
from .stream27_r15_pcie_application_bind_v1 import application as previous,ROOT


def application(bundle):
    b=previous(bundle);old_top=b['top'];top=old_top.removesuffix('_v1')+'_v2'
    text=b['files'].pop(old_top+'.sv')
    replacements={
      'module '+old_top+' #(':'module '+top+' #(',
      'wire common_reset_n,pcie_ready,core_ready,session_exhausted;':
        'wire common_reset_n,pcie_reset_n,core_reset_n,pcie_ready,core_ready,session_exhausted;',
      'genefer_stream27_r15_link_reset_v1 reset_fence(':'genefer_stream27_r15_link_reset_v2 reset_fence(',
      '.common_reset_n,.pcie_ready,.core_ready,.session,.exhausted(session_exhausted));':
        '.common_reset_n,.pcie_reset_n,.core_reset_n,.pcie_ready,.core_ready,.session,.exhausted(session_exhausted));',
      '.clk(pcie_clk),.reset(!common_reset_n),.link_ready(pcie_ready),':
        '.clk(pcie_clk),.reset(!pcie_reset_n),.link_ready(pcie_ready),',
      '.clk(core_clk),.rst_n(common_reset_n),.link_ready(core_ready),.session,':
        '.clk(core_clk),.rst_n(core_reset_n),.link_ready(core_ready),.session,',
      '.clk(core_clk),.rst_n(common_reset_n),.load_we(1\'b0),':
        '.clk(core_clk),.rst_n(core_reset_n),.load_we(1\'b0),',
    }
    original=text
    for before,after in replacements.items():
        if text.count(before)!=1:raise ValueError('R15_APPLICATION_V2_ANCHOR '+before)
        text=text.replace(before,after)
    reversed_text=text
    for before,after in reversed(list(replacements.items())):
        reversed_text=reversed_text.replace(after,before)
    if reversed_text!=original:raise ValueError('R15_APPLICATION_V2_REVERSE')
    b['top']=top;b['files'][top+'.sv']=text
    b['rtl_sources']=[top+'.sv' if p==old_top+'.sv' else p for p in b['rtl_sources']]
    old='genefer_stream27_r15_link_reset_v1.sv';new='genefer_stream27_r15_link_reset_v2.sv'
    b['files'].pop(old);b['files'][new]=(ROOT/'rtl/kernel'/new).read_text()
    b['rtl_sources']=[new if p==old else p for p in b['rtl_sources']]
    role=ROOT/'results/throughput-20260929/trackS-r15-pcie-avmm-native-v6/normal-v6'
    manifest=json.loads((role/'manifest.json').read_bytes())
    for p,h in manifest['sources'].items():
        captured=role/'source/fpga'/p
        if hashlib.sha256(captured.read_bytes()).hexdigest()!=h:
            raise ValueError('R15_APPLICATION_V6_CAPTURE_DRIFT')
        dep=str(captured.relative_to(ROOT));b['source_dependencies'].append(dep);b['source_sha256'][dep]=h
    endpoint='genefer_stream27_r15_pcie_avmm_v1.sv'
    b['files'][endpoint]=(role/'source/fpga/rtl/kernel'/endpoint).read_text()
    for p in ('reference/stream27_r15_pcie_application_bind_v2.py','rtl/kernel/'+new):
        b['source_dependencies'].append(p);b['source_sha256'][p]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
    b['generated_sha256']={k:hashlib.sha256(v.encode()).hexdigest() for k,v in b['files'].items()}
    b['r15_shell_application'].update(domain_reset_release_synchronized=True,
      endpoint_version=6,application_version=2,
      predecessor_application_top=old_top,predecessor_wrapper_exact_reverse=True)
    return b
