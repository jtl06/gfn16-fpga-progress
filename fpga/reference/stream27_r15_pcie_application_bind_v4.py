"""Additive explicit-width endpoint repair; application-v3 interfaces unchanged."""
import hashlib
from .stream27_r15_pcie_application_bind_v3 import application as previous,ROOT
from . import stream27_r15_pcie_avmm_v8 as endpoint

SELF='reference/stream27_r15_pcie_application_bind_v4.py'


def application(bundle):
    b=previous(bundle);old=b['top'];top=old.removesuffix('_v3')+'_v4'
    text=b['files'].pop(old+'.sv');before='module '+old+' #('
    if text.count(before)!=1:raise ValueError('R15_APPLICATION_V4_TOP')
    b['files'][top+'.sv']=text.replace(before,'module '+top+' #(')
    b['top']=top;b['rtl_sources']=[top+'.sv' if p==old+'.sv' else p for p in b['rtl_sources']]
    b['files']['genefer_stream27_r15_pcie_avmm_v1.sv']=endpoint.source().decode()
    for p in (SELF,'reference/stream27_r15_pcie_avmm_v8.py'):
        b['source_dependencies'].append(p)
        b['source_sha256'][p]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
    b['generated_sha256']={p:hashlib.sha256(s.encode()).hexdigest() for p,s in b['files'].items()}
    b['r15_shell_application'].update(application_version=4,endpoint_version=8,
        predecessor_application_top=old,explicit_unsigned_export_span_width=32)
    return b
