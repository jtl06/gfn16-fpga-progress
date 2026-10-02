"""Native-qualified warm-field sizing project, not a whole-core fit claim."""
import hashlib
import json
from pathlib import Path
import tarfile

from .stream27_shared_field_v1 import ROOT,prepare as compile_field
from .stream27_field_physical_probe_v1 import DEVICE,RUN_TCL


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(destination,*,p=16,field=0):
    destination=Path(destination).resolve()
    if destination.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('S4_WARM_PHYSICAL_FRESH_PAUSE')
    if p!=16 or field!=0:raise ValueError('S4_WARM_PHYSICAL_NATIVE_QUALIFIED_P16_F0_ONLY')
    q=json.loads((ROOT/'queue/done/s4-aw16-shared-q1-v1.json').read_text())
    if q['dependency_gate']['status']!='PASS_expected_contracts':raise ValueError('S4_WARM_PHYSICAL_NATIVE_GATE')
    gate=Path(q['dependency_gate']['path'])
    if sha(gate)!=q['dependency_gate']['sha256']:raise ValueError('S4_WARM_PHYSICAL_GATE_DRIFT')
    native=Path(q['result']['evidence'])/'output/native/report.json';r=json.loads(native.read_text())
    b=compile_field(65536,p,field,allow_full_constants=True)
    for name,text in b['files'].items():
        if r['sources']['rtl/'+name]!=hashlib.sha256(text.encode()).hexdigest():raise ValueError('S4_WARM_PHYSICAL_RTL_DRIFT:'+name)
    project=destination/'project';(project/'rtl').mkdir(parents=True)
    qsf=['set_global_assignment -name FAMILY "Arria 10"','set_global_assignment -name DEVICE '+DEVICE,
        'set_global_assignment -name TOP_LEVEL_ENTITY '+b['top'],
        'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
        'set_global_assignment -name NUM_PARALLEL_PROCESSORS 4','set_global_assignment -name SEED 1',
        'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON','set_global_assignment -name SDC_FILE warm.sdc']
    for name,text in b['files'].items():
        (project/'rtl'/name).write_text(text)
        if name.endswith('.sv'):qsf.append('set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+name)
    qsf+=['set_parameter -name AW 16',f'set_parameter -name P {p}','set_parameter -name CONTEXTS 1']
    ports=['in_slot_valid','frame_start','context_enabled','generation_in[*]','live_generation[*]','base_in[*]',
        'epoch_in[*]','correction_epoch[*]','correction_valid','correction_generation[*]','data_in[*]','c0_in[*]','c1_in[*]',
        'out_slot_valid','out_frame_start','out_eligible','out_error','fault_pending','generation_out[*]','data_out[*]',
        'out_epoch[*]','commit_valid','commit_frame_start','commit_generation[*]','commit_epoch[*]','commit_data[*]',
        'owner_count[*]','frame_accept','correction_accept','output_row[*]','cycle_count[*]','frame_count[*]']
    qsf+=['set_instance_assignment -name VIRTUAL_PIN ON -to {'+port+'}' for port in ports]
    controls={'warm.qsf':'\n'.join(qsf)+'\n','warm.qpf':'PROJECT_REVISION = "warm"\n',
        'warm.sdc':'create_clock -name kernel_clk -period 10.000 [get_ports {clk}]\nderive_clock_uncertainty\n',
        'run.tcl':RUN_TCL}
    for name,text in controls.items():(project/name).write_text(text)
    m=dict(status='prepared_sizing_source_only_not_fit',top=b['top'],edition='pro',device=DEVICE,
        compile_processors=4,seed=1,clock_period_ns=10,address_width=16,bitstream_generation=False,
        allowed_stages=['syn','fit','sta'],core_parameters=dict(AW=16,P=p,CONTEXTS=1),raw_multiplier_parameters=None,
        field_parameters=None,source_sha256={name:hashlib.sha256(text.encode()).hexdigest() for name,text in b['files'].items()},
        control_sha256={name:hashlib.sha256(text.encode()).hexdigest() for name,text in controls.items()},
        preparation_source_sha256={**b['source_sha256'],'reference/stream27_shared_warm_physical_v1.py':sha(ROOT/'reference/stream27_shared_warm_physical_v1.py')},
        native_report_sha256=sha(native),native_gate_sha256=sha(gate),native_gate_scope='real P16/f0 warm field,9frames/589824physicalwords; no three-field/carry/host or clock claim',
        geometry=b['geometry'],provisional_physical_probe=True,
        missing_overhead_quantification='Includes real small correction DIF, signed/unsigned reducers, correction twist, segmented term, modular adds, two caches and frame ownership/cycle controller.',
        purpose='Measure warm field overhead relative to frozen plain P16-c field source; no one-field-to-whole-core timing inference',
        omitted=['three-field join','CRT','block carry','shared reciprocal/bound setup','feedback/image RAM','hardware canonicalization/host controller','CONTEXTS2 interleave'],
        full_N_numeric_NTT_performed_on_Mac=False,physical_fit_qualified=False,promotion_allowed=False)
    (project/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    inputs={str(path.relative_to(project)):sha(path) for path in sorted(project.rglob('*')) if path.is_file()}
    result=dict(status='prepared_not_dispatched',project_manifest_sha256=sha(project/'manifest.json'),project_input_sha256=inputs,
        native_report_sha256=sha(native),native_gate_sha256=sha(gate),source_files=len(b['rtl_sources']),
        p=p,field=field,n=65536,period_ns=10,seed=1,compile_processors=4,
        requested_scope='One-field virtual-I/O sizing exemption under B20261001S4; fit owner still enforces source/tools/resources/budget and native DA/timing evidence.',
        no_claims='No new spend, launch, mapped/fitted result, whole-core clock or P16 GO.')
    (destination/'preparation.json').write_text(json.dumps(result,indent=2)+'\n')
    with tarfile.open(destination/'source.tar.gz','x:gz') as archive:
        for name in sorted(inputs):archive.add(project/name,arcname='project/'+name,recursive=False)
        archive.add(destination/'preparation.json',arcname='preparation.json',recursive=False)
    result['archive_sha256']=sha(destination/'source.tar.gz');return result


if __name__=='__main__':
    import sys
    if len(sys.argv)!=2:raise ValueError('S4_WARM_PHYSICAL_USAGE')
    r=prepare(sys.argv[1]);print(json.dumps({k:r[k] for k in ('status','project_manifest_sha256','archive_sha256','source_files','requested_scope')},indent=2))
