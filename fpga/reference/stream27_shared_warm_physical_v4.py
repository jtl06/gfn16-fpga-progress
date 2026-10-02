"""Shared parameterized P-choice warm sizing, component exemption only.

P16 historical native-qualified sizing projects remain frozen. P8 uses the
same additive shared compiler, not a probe fork or whole-core substitution.
No numeric/clock qualification is inferred from this source-only preparation.
"""
import hashlib
import json
from pathlib import Path
import tarfile
from .stream27_shared_field_v1 import ROOT,prepare as compile_field
from .stream27_field_physical_probe_v1 import DEVICE
from fpga.cloud.plain_fit_v2 import FULL_TCL
from fpga.cloud.aws_fit_v6 import verify_project


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(destination,*,p=8,field=0):
    destination=Path(destination).resolve()
    if destination.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('S4_WARM_PCHOICE_FRESH_PAUSE')
    if p not in (8,16) or field not in (0,1,2):raise ValueError('S4_WARM_PCHOICE_PARAMETERS')
    b=compile_field(65536,p,field,mode='warm',contexts=1,allow_full_constants=True)
    project=destination/'project';(project/'rtl').mkdir(parents=True)
    qsf=['set_global_assignment -name FAMILY "Arria 10"','set_global_assignment -name DEVICE '+DEVICE,
        'set_global_assignment -name TOP_LEVEL_ENTITY '+b['top'],
        'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
        'set_global_assignment -name NUM_PARALLEL_PROCESSORS 4','set_global_assignment -name SEED 1',
        'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON','set_global_assignment -name SDC_FILE probe.sdc']
    for name,text in b['files'].items():
        (project/'rtl'/name).write_text(text)
        if name.endswith('.sv'):qsf.append('set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name)
    qsf+=['set_parameter -name AW 16',f'set_parameter -name P {p}','set_parameter -name CONTEXTS 1']
    ports=['rst_n','in_slot_valid','frame_start','context_enabled','generation_in[*]','live_generation[*]','base_in[*]',
        'epoch_in[*]','correction_epoch[*]','correction_valid','correction_generation[*]','data_in[*]','c0_in[*]','c1_in[*]',
        'out_slot_valid','out_frame_start','out_eligible','out_error','fault_pending','generation_out[*]','data_out[*]',
        'out_epoch[*]','commit_valid','commit_frame_start','commit_generation[*]','commit_epoch[*]','commit_data[*]',
        'owner_count[*]','frame_accept','correction_accept','output_row[*]','cycle_count[*]','frame_count[*]']
    qsf+=['set_instance_assignment -name VIRTUAL_PIN ON -to {'+port+'}' for port in ports]
    controls={'probe.qsf':'\n'.join(qsf)+'\n','probe.qpf':'PROJECT_REVISION = "probe"\n',
        'probe.sdc':'create_clock -name kernel_clk -period 10.000 [get_ports {clk}]\nderive_clock_uncertainty\n# Component sizing only; reset release excluded.\nset_false_path -from [get_ports {rst_n}]\n',
        'run.tcl':FULL_TCL}
    for name,text in controls.items():(project/name).write_text(text)
    path='reference/stream27_shared_warm_physical_v4.py'
    m=dict(status='prepared_pchoice_component_sizing_source_only_not_fit',top=b['top'],edition='pro',device=DEVICE,
        compile_processors=4,seed=1,clock_period_ns=10,address_width=16,bitstream_generation=False,
        allowed_stages=['syn','fit','sta'],core_parameters=dict(AW=16,P=p,CONTEXTS=1),raw_multiplier_parameters=None,
        field_parameters=None,source_sha256={name:hashlib.sha256(text.encode()).hexdigest() for name,text in b['files'].items()},
        control_sha256={name:hashlib.sha256(text.encode()).hexdigest() for name,text in controls.items()},
        preparation_source_sha256={**b['source_sha256'],path:sha(ROOT/path),'cloud/plain_fit_v2.py':sha(ROOT/'cloud/plain_fit_v2.py')},
        geometry=b['geometry'],provisional_physical_probe=True,
        sizing_exemption='B20261001S4 onefield virtual-I/O sizing; full native numeric pre-fit gate exempt, not passed/inherited.',
        purpose='Measure real shared warm field for P-choice after measured P16 warm area NO-GO; no smaller-core completion claim.',
        omitted=['three-field join','CRT','block carry','shared reciprocal/bound setup','feedback/image RAM','hardware canonicalization/host controller','CONTEXTS2 interleave'],
        full_N_numeric_NTT_performed_on_Mac=False,physical_fit_qualified=False,promotion_allowed=False)
    (project/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');context=verify_project(project)
    if context['source_sha256']!=m['source_sha256']:raise ValueError('S4_WARM_PCHOICE_RTL_DRIFT')
    result=dict(status='source_verified_component_sizing_not_dispatched',project=context,
        project_manifest_sha256=sha(project/'manifest.json'),source_files=len(b['rtl_sources']),p=p,field=field,n=65536,
        period_ns=10,seed=1,compile_processors=4,sizing_exemption=m['sizing_exemption'],
        no_claims='No native numeric PASS, fitted result, whole-core clock, P8 whole support or P16 GO.',promotion_allowed=False)
    (destination/'preparation.json').write_text(json.dumps(result,indent=2)+'\n')
    with tarfile.open(destination/'source.tar.gz','x:gz') as archive:
        for path in sorted(project.rglob('*')):
            if path.is_file():archive.add(path,arcname='project/'+str(path.relative_to(project)),recursive=False)
        archive.add(destination/'preparation.json',arcname='preparation.json',recursive=False)
    result['archive_sha256']=sha(destination/'source.tar.gz');return result


if __name__=='__main__':
    import sys
    if len(sys.argv)!=2:raise ValueError('S4_WARM_PCHOICE_USAGE')
    r=prepare(sys.argv[1]);print(json.dumps({k:r[k] for k in ('status','project_manifest_sha256','archive_sha256','source_files','sizing_exemption')},indent=2))
