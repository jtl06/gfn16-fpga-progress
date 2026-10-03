"""R15 switch integration. FIELD100 is immutable and all-OFF is literal.

Each enabled mode is a new source cohort: previous source/native/clock
qualification is not attached to it. The cold/PCIe owner is imported only
when requested; absent or incomplete real IP is a preparation failure.
"""
import copy
import hashlib
import importlib
import re
from pathlib import Path
from . import stream27_r15_fixed_schedule_bind as fixed
from . import stream27_r15_storage_ram_bind as storage
from . import stream27_r15_lean_watchdog_bind as lean

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_all_bind.py'
FLAGS=('FIXED_SCHEDULE','LEAN_BUILD','PROGRESS_WATCHDOG','STORAGE_TO_RAM','DIRECT_COLD','PCIE_SHELL')
PINS={fixed.SELF:'0b86fe6368e4f07172cf6049bfe5cf668424bde7d3e1981796c90d7baa296ae7',
      lean.SELF:'3dfe66d187d492e5e3c161fae98b14c1d4908cf08cf49fca3d08e4f7eb2d6d3b',
      storage.SELF:'adf35093f686365ddee0c7a46bf41803af28ea4ba4ae9c466bec6cc151591e06'}


def sha(raw):
    return hashlib.sha256(raw.encode() if isinstance(raw,str) else raw).hexdigest()


def need(ok,why):
    if not ok:raise ValueError('R15_ALL_'+why)


def bind(bundle,*,fixed_schedule=0,lean_build=0,progress_watchdog=0,
         storage_to_ram=0,direct_cold=0,pcie_shell=0):
    values=(fixed_schedule,lean_build,progress_watchdog,storage_to_ram,direct_cold,pcie_shell)
    need(all(type(v) is int and v in (0,1) for v in values),'BOOLEAN_SWITCHES')
    if not any(values):return copy.deepcopy(bundle)
    need(bundle==fixed.capture(bundle['geometry']['n']),'EXACT_FIELD100_PARENT')
    for path,pin in PINS.items():need(sha((ROOT/path).read_bytes())==pin,'PRIVATE_FROZEN_PIN:'+path)
    # The private numeric delays preserve E16 and all validity/owner/reset
    # authorities. Metadata conversion is deliberately OFF: parent Quartus
    # already inferred that shift as RAM, so it supplies no presumed saving.
    out=fixed.bind(bundle,fixed_schedule)
    out=storage.bind(out,storage_to_ram,crt_metadata_mlab=0,
                     crt_r1_mlab=1,crt_d3_mlab=1,crt_x12_mlab=1)
    out=lean.bind(out,lean_build=lean_build,progress_watchdog=progress_watchdog)
    if direct_cold or pcie_shell:
        try:io=importlib.import_module(__package__+'.stream27_r15_direct_cold_bind')
        except ModuleNotFoundError as exc:
            raise ValueError('R15_ALL_IO_SOURCE_NOT_READY') from exc
        out=io.bind(out,direct_cold=direct_cold,pcie_shell=pcie_shell)
        need(out.get('r15_host_link',{}).get('source_ready') is True,'IO_SOURCE_CONTRACT')
        if pcie_shell:
            need(out['r15_host_link'].get('real_pcie_ip_ready') is True,'REAL_PCIE_IP_CONSTRAINTS_NOT_READY')
    chosen=dict(zip(FLAGS,values))
    top=out['top'];host=out['files'][top+'.sv'];before=host
    need(host.count('CONTEXTS=2,')==1,'TOP_CLOSED_PARAMETER_SEAM')
    missing={k:v for k,v in chosen.items() if k not in out['parameters']}
    if missing:
        host=host.replace('CONTEXTS=2,','CONTEXTS=2,'+''.join(k+'='+str(v)+',' for k,v in missing.items()),1)
    for key,value in chosen.items():
        if key in out['parameters']:need(out['parameters'][key]==value,'PRIVATE_FLAG_IDENTITY:'+key)
    newtop=top+'_r15_all_v1'
    host=re.sub(r'\b'+re.escape(top)+r'\b',newtop,host)
    reverse=re.sub(r'\b'+re.escape(newtop)+r'\b',top,host)
    if missing:reverse=reverse.replace('CONTEXTS=2,'+''.join(k+'='+str(v)+',' for k,v in missing.items()),'CONTEXTS=2,',1)
    need(reverse==before,'INTEGRATION_ROOT_REVERSE')
    out['files'].pop(top+'.sv');out['files'][newtop+'.sv']=host
    deps=list(dict.fromkeys(out['source_dependencies']+[SELF]))
    out.update(top=newtop,parameters=dict(out['parameters'],**chosen),rtl_sources=list(out['files']),
               generated_sha256={n:sha(t) for n,t in out['files'].items()},source_dependencies=deps,
               source_sha256={p:sha((ROOT/p).read_bytes()) for p in deps})
    out['r15_all']=dict(source_ready=True,flags=chosen,disabled_literal_FIELD100=True,
        parent_top=bundle['top'],parent_generated_sha256=bundle['generated_sha256'],
        composition_order=['fixed_internal_calendar','numeric_storage','lean_watchdog','direct_cold_pcie'],
        integration_root_reverse_exact=True,internal_compute_geometry=copy.deepcopy(bundle['geometry']),
        healthy_internal_latency_delta=0,
        external_DMA_CDC_backpressure_retained=True,active_pipeline_stall_allowed=False,
        descriptor_underflow_typed_fault_retained=True,
        host_GL_implementation_qualification_inherited=False,
        mapped_area_saving_assumed=False,native_qualification_inherited=False,
        source_specific_clock_qualification_inherited=False,promotion_allowed=False)
    return out


def prepare(n=256,*,p=16,contexts=2,**flags):
    need(p==16 and contexts==2,'CLOSED_GEOMETRY')
    return bind(fixed.capture(n),**flags)
