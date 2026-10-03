"""Additive R15 direct-cold/shell integration; frozen compute7bf49 unchanged.

The private direct wrapper must precede six-flag root declaration. Wrapping
an already declared DIRECT_COLD parameter would duplicate that parameter.
Real PCIe is a second, fail-closed private boundary, never a black-box fit.
"""
import copy
import importlib
import re
from . import stream27_r15_all_bind as compute
from . import stream27_r15_direct_cold_bind_v2 as direct

ROOT=compute.ROOT
SELF='reference/stream27_r15_all_io_bind.py'
DIRECT='reference/stream27_r15_direct_cold_bind_v2.py'
DIRECT_PIN='2158f682a0437b6f4697ab70ea312dd1b673b00a75802e27cfecbdd1dfd6f811'
COMPUTE_PIN='7bf49d27c712d9a093b5f92d07f791d946ef0ac7bd526bb72186d4e8fac59099'
sha,need=compute.sha,compute.need


def bind(bundle,*,fixed_schedule=0,lean_build=0,progress_watchdog=0,
         storage_to_ram=0,direct_cold=0,pcie_shell=0):
    values=(fixed_schedule,lean_build,progress_watchdog,storage_to_ram,direct_cold,pcie_shell)
    need(all(type(v) is int and v in (0,1) for v in values),'IO_BOOLEAN_SWITCHES')
    if not any(values):return copy.deepcopy(bundle)
    if not direct_cold and not pcie_shell:
        # The old compute source cohort is not changed or re-qualified by
        # calling its already-frozen orchestrator from this helper.
        return compute.bind(bundle,fixed_schedule=fixed_schedule,lean_build=lean_build,
                            progress_watchdog=progress_watchdog,storage_to_ram=storage_to_ram)
    need(bundle==compute.fixed.capture(bundle['geometry']['n']),'IO_EXACT_FIELD100')
    need(sha((ROOT/compute.SELF).read_bytes())==COMPUTE_PIN,'COMPUTE_FROZEN_SOURCE')
    need(sha((ROOT/DIRECT).read_bytes())==DIRECT_PIN,'DIRECT_CONTAINMENT_SUCCESSOR')
    for path,pin in compute.PINS.items():need(sha((ROOT/path).read_bytes())==pin,'IO_PRIVATE_FROZEN_PIN:'+path)
    out=compute.fixed.bind(bundle,fixed_schedule)
    out=compute.storage.bind(out,storage_to_ram,crt_metadata_mlab=0,
                             crt_r1_mlab=1,crt_d3_mlab=1,crt_x12_mlab=1)
    out=compute.lean.bind(out,lean_build=lean_build,progress_watchdog=progress_watchdog)
    # No REAL PCIe parameter is silently enabled in the raw loader wrapper.
    out=direct.bind(out,direct_cold=direct_cold,pcie_shell=0)
    if direct_cold:
        need(out.get('r15_host_link',{}).get('source_ready') is True,'DIRECT_SOURCE_READY')
    chosen=dict(zip(compute.FLAGS,values))
    top=out['top'];before=out['files'][top+'.sv'];text=before
    need(text.count('CONTEXTS=2,')==1,'IO_ROOT_PARAMETER_SEAM')
    missing={k:v for k,v in chosen.items() if k not in out['parameters']}
    additions=''.join(k+'='+str(v)+',' for k,v in missing.items())
    if missing:text=text.replace('CONTEXTS=2,','CONTEXTS=2,'+additions,1)
    for key,value in chosen.items():
        if key in out['parameters']:need(out['parameters'][key]==value,'IO_FLAG_IDENTITY:'+key)
    newtop=top+'_r15_io_v1'
    text=re.sub(r'\b'+re.escape(top)+r'\b',newtop,text)
    reverse=re.sub(r'\b'+re.escape(newtop)+r'\b',top,text)
    if missing:reverse=reverse.replace('CONTEXTS=2,'+additions,'CONTEXTS=2,',1)
    need(reverse==before,'IO_ROOT_REVERSE')
    out['files'].pop(top+'.sv');out['files'][newtop+'.sv']=text
    out.update(top=newtop,parameters=dict(out['parameters'],**chosen))
    if pcie_shell:
        try:shell=importlib.import_module(__package__+'.stream27_r15_pcie_shell_bind')
        except ModuleNotFoundError as exc:raise ValueError('R15_REAL_PCIE_SOURCE_NOT_READY') from exc
        out=shell.bind(out,pcie_shell=1)
        need(out.get('r15_host_link',{}).get('real_pcie_ip_ready') is True,'REAL_PCIE_IP_IO_CDC_CONSTRAINTS')
        need(all(out['parameters'].get(k)==v for k,v in chosen.items()),'REAL_SHELL_FLAG_FORWARDING')
    deps=list(dict.fromkeys(out['source_dependencies']+[compute.SELF,DIRECT,SELF]))
    out.update(rtl_sources=list(out['files']),generated_sha256={n:sha(t) for n,t in out['files'].items()},
               source_dependencies=deps,source_sha256={p:sha((ROOT/p).read_bytes()) for p in deps})
    out['r15_all_io']=dict(source_ready=True,flags=chosen,parent_top=bundle['top'],
        disabled_literal_FIELD100=True,integration_root_reverse_exact=True,
        fixed_compute_source_not_modified=True,global_loader_error_public_containment=True,
        private_admitted_tails_may_drain=True,field_flush_claim=False,
        original_setup_recomputed_after_start=True,cold_format='raw32-natural-digits-c0-c1-v1',
        initial_export_format='canonical96-full56-v1',raw_export_available=False,
        chip_final_materialization_removed=False,host_cost_excluded_from_compute_projection=True,
        internal_compute_geometry=copy.deepcopy(bundle['geometry']),
        internal_pipeline_latency_delta=0,external_cold_transport_cost_is_not_zero=True,
        real_pcie_shell=bool(pcie_shell),native_qualification_inherited=False,
        source_specific_clock_qualification_inherited=False,promotion_allowed=False)
    return out


def prepare(n=256,*,p=16,contexts=2,**flags):
    need(p==16 and contexts==2,'IO_CLOSED_GEOMETRY')
    return bind(compute.fixed.capture(n),**flags)
