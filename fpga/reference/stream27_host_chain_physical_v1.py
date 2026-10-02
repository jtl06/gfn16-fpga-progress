"""Whole P8 AW16 source project, never a field sizing exemption.

One shared parameterized compiler emits exactly the standalone candidate that
the full-N T5b-paired native gate wraps. Source preparation alone is NOT fit
admission: exact native prerequisites and declared structural inventory are
required by the fit owner, with normal whole-job horizons and budget guards.
"""
import hashlib
import json
from pathlib import Path
import re
import tarfile
from . import stream27_host_chain_param_v2 as core
from .stream27_field_physical_probe_v1 import DEVICE
from fpga.cloud.plain_fit_v2 import FULL_TCL

ROOT=core.ROOT
PINS={'reference/stream27_host_chain_param_v2.py':'bd909f42310a194220c5c20f0a4e3decb3e97bcf142b3ffd5a1b300d0ffc9773',
      'cloud/plain_fit_v2.py':'6ae141be72ccfdc77b2035d9b7347e5f555b37e94b4d7a7476ccfb3530d9883e'}
ROOT_PIN='ee65a33fdaac06de83c7122f7e95704c835f4c1ee55171f846ac7e553ed30d21'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def host_ports(text):
    header=text.split(') (',1)[1].split(');',1)[0];result=[];direction=None;width=None
    pattern=r'(?:(input|output)\s+logic(?:\s+signed)?(?:\s+\[([^\]]+)\])?\s+)?([a-zA-Z]\w*)'
    for item in header.split(','):
        match=re.fullmatch(pattern,item.strip())
        if not match:raise ValueError('S4_WHOLE_LITERAL_HOST_PORT:'+item)
        if match[1]:direction,width=match[1],match[2]
        if direction is None:raise ValueError('S4_WHOLE_HOST_PORT_DIRECTION')
        if match[3] not in ('clk','rst_n'):result.append(match[3]+('[*]' if width else ''))
    if len(result)!=len(set(result)):raise ValueError('S4_WHOLE_UNIQUE_PORTS')
    return result


def prepare(destination,*,workers=6):
    destination=Path(destination).resolve()
    if destination.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('S4_WHOLE_FRESH_PAUSE')
    if workers not in (4,6):raise ValueError('S4_WHOLE_APPROVED_WORKERS')
    for path,pin in PINS.items():
        if sha(ROOT/path)!=pin:raise ValueError('S4_WHOLE_SOURCE_DRIFT:'+path)
    b=core.prepare(65536,8,paired=False,contexts=1,allow_full_constants=True)
    root_source=b['files'][b['top']+'.sv']
    if hashlib.sha256(root_source.encode()).hexdigest()!=ROOT_PIN:raise ValueError('S4_WHOLE_NATIVE_CANDIDATE_ROOT_DRIFT')
    project=destination/'project';(project/'rtl').mkdir(parents=True)
    qsf=['set_global_assignment -name FAMILY "Arria 10"','set_global_assignment -name DEVICE '+DEVICE,
         'set_global_assignment -name TOP_LEVEL_ENTITY '+b['top'],
         'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
         f'set_global_assignment -name NUM_PARALLEL_PROCESSORS {workers}',
         'set_global_assignment -name SEED 1','set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON',
         'set_global_assignment -name SDC_FILE probe.sdc']
    for name,text in b['files'].items():
        (project/'rtl'/name).write_text(text)
        if name.endswith('.sv'):qsf.append('set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name)
    parameters=dict(AW=16,P=8,CONTEXTS=1,EPOCH_SEED=65534)
    qsf += ['set_parameter -name '+name+' '+str(value) for name,value in parameters.items()]
    qsf += ['set_instance_assignment -name VIRTUAL_PIN ON -to {'+port+'}' for port in host_ports(root_source)]
    controls={'probe.qsf':'\n'.join(qsf)+'\n','probe.qpf':'PROJECT_REVISION = "probe"\n',
              'probe.sdc':'create_clock -name kernel_clk -period 10.000 [get_ports {clk}]\nderive_clock_uncertainty\n',
              'run.tcl':FULL_TCL}
    for name,text in controls.items():(project/name).write_text(text)
    m=dict(status='whole_source_prepared_not_fit_admitted',scope='whole_core',top=b['top'],edition='pro',device=DEVICE,
           compile_processors=workers,seed=1,clock_period_ns=10,address_width=16,bitstream_generation=False,
           allowed_stages=['syn','fit','sta'],core_parameters=parameters,raw_multiplier_parameters=None,field_parameters=None,
           source_sha256=b['generated_sha256'],control_sha256={name:sha(project/name) for name in controls},
           preparation_source_sha256={**b['source_sha256'],'reference/stream27_host_chain_physical_v1.py':sha(ROOT/'reference/stream27_host_chain_physical_v1.py')},
           intermediate_snapshots=True,geometry=b['geometry'],sizing_exemption=None,physical_fit_qualified=False,promotion_allowed=False,
           native_prerequisite='s4-aw16-p8-full-host-q1-v1 actual PASS source/config closure; pending, not inherited from field or small PRP',
           structural_prerequisite='Declared whole-core source inventory must pass exact94945704 source_inventory; not prepared by this source-only phase',
           host_contract=b['host_contract'],cycle_contract=b['cycle_contract'],
           notes=['Same49 standalone RTL subset of fullN paired60 RTL; no T5b oracle in physical core',
                  'AW16/P8/CONTEXTS1/EPOCH_SEED65534 explicit, normal whole21780s horizon; no field2h substitution',
                  'Virtual external host I/O and asynchronous reset release are not board-qualified; no false paths added here',
                  'No onefield-to-whole area/LAB/clock inference; actual whole packing/STA required'])
    (project/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    context=dict(manifest_sha256=sha(project/'manifest.json'),source_sha256=m['source_sha256'],
                 control_sha256={**m['control_sha256'],'manifest.json':sha(project/'manifest.json')},qsf_parameters=parameters)
    (destination/'project-context.json').write_text(json.dumps(context,indent=2)+'\n')
    result=dict(status='whole_source_prepared_NOT_fit_admitted',manifest_sha256=context['manifest_sha256'],context_sha256=sha(destination/'project-context.json'),
                source_files=len(b['rtl_sources']),candidate_root_sha256=ROOT_PIN,top=b['top'],parameters=parameters,
                compile_processors=workers,clock_period_ns=10,seed=1,fit_allowed=False,field_sizing_exemption=False,
                pending=['actualfullNnative source/config receipt','whole structural source inventory','ordinary fit-owner money/resources/horizon checks'],
                full_N_numeric_NTT_performed_on_Mac=False,vendor_executed=False,promotion_allowed=False)
    (destination/'preparation.json').write_text(json.dumps(result,indent=2)+'\n')
    with tarfile.open(destination/'source.tar.gz','x:gz') as archive:
        for path in sorted(project.rglob('*')):
            if path.is_file():archive.add(path,arcname='project/'+str(path.relative_to(project)),recursive=False)
        archive.add(destination/'preparation.json',arcname='preparation.json',recursive=False)
        archive.add(destination/'project-context.json',arcname='project-context.json',recursive=False)
    result['archive_sha256']=sha(destination/'source.tar.gz');return result


if __name__=='__main__':
    import sys
    print(json.dumps(prepare(sys.argv[1],workers=int(sys.argv[2]) if len(sys.argv)==3 else 6),indent=2))
