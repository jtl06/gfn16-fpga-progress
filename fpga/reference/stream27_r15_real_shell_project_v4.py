"""Emit ONE private source-locked real-I/O project; no fit dispatch.

Generated QIP/SDC sources are copied unchanged. Generation-only dni/qdb state
is explicitly excluded from the source projection, not deleted from evidence.
"""
import copy
import hashlib
import json
from pathlib import Path
from .stream27_r15_all_io_bind import prepare as direct
from .stream27_r15_pcie_shell_bind_v2 import bind,ROOT,BASE as VENDOR

BASE=ROOT/'results/throughput-20260929/trackS-r15-real-pcie-shell-v2'
SELF='reference/stream27_r15_real_shell_project_v4.py'


def sha(raw):return hashlib.sha256(raw).hexdigest()
def json_bytes(value):return (json.dumps(value,indent=2)+'\n').encode()


def prepare(output):
    output=Path(output).resolve()
    if not output.is_relative_to(BASE) or output.exists():raise ValueError('R15_REAL_PROJECT_FRESH_PRIVATE_OUTPUT')
    b=bind(direct(65536,p=16,contexts=2,fixed_schedule=1,lean_build=1,
      progress_watchdog=1,storage_to_ram=1,direct_cold=1,pcie_shell=0),pcie_shell=1)
    desc=copy.deepcopy(b['r15_real_shell']);sources={p:sha(t.encode()) for p,t in b['files'].items()}
    vendor_all=desc['vendor_sources']
    omitted={p:h for p,h in vendor_all.items() if p.split('/')[0] in ('dni','qdb')}
    if len(omitted)!=10:raise ValueError('R15_GENERATION_STATE_PROJECTION')
    vendor={p:h for p,h in vendor_all.items() if p not in omitted}
    if len(vendor)!=335:raise ValueError('R15_VENDOR_SOURCE_PROJECTION')
    desc.update(vendor_root='rtl/vendor',vendor_sources=vendor,
       vendor_generation_sources=vendor_all,omitted_generation_state=omitted,
       original_vendor_root=str(VENDOR))
    desc['clock_control_paths']={'base':'probe.sdc','cdc':'rtl/proofs/application_cdc.sdc',
      'registers':'rtl/proofs/application_registers.qsf'}
    desc['compatibility_caveats']=[
      'Registered downstream response credit only: minimum one response edge; zero-latency response is rejected.',
      'Whole32-byte beat spans are checked independently of byte enables; some partial edge transfers can be refused.',
      'Previously offered downstream reads can remain stalled until common reset; no fabricated completion.',
      'Automatic link-down/retrain/FLR delivery and hardware identity are unqualified; common reset and both-domain drain are required.',
      'Retained vendor PHY warnings/E3 Gen3 timing require physical and hardware evidence; no speed-grade change or warning waiver.']
    controls={}
    controls['probe.qpf']=b'PROJECT_REVISION = "probe"\n'
    controls['probe.sdc']=desc['base_sdc'].encode()
    controls['rtl/proofs/application_cdc.sdc']=desc['cdc_sdc'].encode()
    controls['rtl/proofs/application_registers.qsf']=desc['cdc_qsf'].encode()
    lines=['set_global_assignment -name FAMILY "Arria 10"',
      'set_global_assignment -name DEVICE 10AX115N4F40E3SG',
      'set_global_assignment -name TOP_LEVEL_ENTITY '+b['top'],
      'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
      'set_global_assignment -name NUM_PARALLEL_PROCESSORS 8',
      'set_global_assignment -name SEED 1',
      'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON',
      'set_global_assignment -name SDC_FILE probe.sdc',
      'set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+b['top']+'.sv']
    lines += ['set_global_assignment -name QIP_FILE rtl/vendor/'+q for q in desc['qip_roots']]
    lines += ['set_global_assignment -name SDC_FILE rtl/proofs/application_cdc.sdc',
              'source rtl/proofs/application_registers.qsf',desc['pin_qsf'].rstrip()]
    controls['probe.qsf']=('\n'.join(lines)+'\n').encode()
    controls['run.tcl']=b'''# Real-I/O fixed-clock syn/fit/STA only. No assembler or period retarget.
load_package project
load_package flow
cd [file dirname [file normalize [info script]]]
project_open probe
if {[catch {
 execute_module -tool syn
 execute_module -tool fit
 execute_module -tool sta
} failure]} {
 catch {project_close}
 error $failure
}
catch {project_close}
'''
    proofs={'source-bundle.json':b,'real-shell.json':desc,
      'board-static-wiring.json':desc['board_static_proof'],
      'clock-source-proof.json':desc['clock_proof'],
      'bar2-source-proof.json':desc['bar2_proof'],
      'aperture-wiring-proof.json':desc['aperture_wiring'],
      'generation-diagnostics.json':desc['generation_diagnostics']}
    for name,value in proofs.items():controls['rtl/proofs/'+name]=json_bytes(value)
    for key,name in [('generation_receipt','generation-receipt.json'),('generation_input','generation-input.json')]:
        ref=desc[key];raw=(ROOT/ref['path']).read_bytes()
        if sha(raw)!=ref['sha256']:raise ValueError('R15_REAL_PROJECT_EVIDENCE_DRIFT')
        controls['rtl/proofs/'+name]=raw
        desc[key]=dict(path='rtl/proofs/'+name,sha256=ref['sha256'])
    controls['rtl/proofs/generation-full-collection.json']=(VENDOR/'full-collection.json').read_bytes()
    desc['source_bundle']=dict(path='rtl/proofs/source-bundle.json',sha256=sha(controls['rtl/proofs/source-bundle.json']))
    controls['rtl/proofs/real-shell.json']=json_bytes(desc)
    manifest=dict(schema='r15-real-io-shell-project-v1',physical_mode='r15_real_shell_v1',status='SOURCE_PREPARED_NATIVE_GATES_PENDING',
      top=b['top'],edition='pro',device='10AX115N4F40E3SG',compile_processors=8,seed=1,
      clock_period_ns=12,bitstream_generation=False,allowed_stages=['syn','fit','sta'],
      core_parameters={},raw_multiplier_parameters=None,field_parameters=None,
      source_sha256=sources,control_sha256={p:sha(raw) for p,raw in controls.items()},
      preparation_source_sha256={SELF:sha((ROOT/SELF).read_bytes())},r15_real_shell=desc,
      native_required_ids=['s4-p16-c2-r15-shell-application-full-normal-q1-v7','s4-r15-dma-aperture-normal-q1-v2'],
      scope='Real-pin/source-locked guarded Gen3x8 shell candidate. No vendor simulation, physical clock, board, automatic reconnect, raw-B, host-GL or promotion inheritance.',promotion_allowed=False)
    output.mkdir(parents=True)
    for name,text in b['files'].items():
        p=output/'rtl'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(text.encode())
    for name,pin in vendor.items():
        raw=(VENDOR/name).read_bytes()
        if sha(raw)!=pin:raise ValueError('R15_REAL_PROJECT_VENDOR_DRIFT')
        p=output/'rtl/vendor'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    for name,raw in controls.items():
        p=output/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    (output/'manifest.json').write_bytes(json_bytes(manifest))
    # Ignore the entire private candidate directory, not a public vendor copy.
    ignore=output.parent/'.gitignore'
    if not ignore.exists():ignore.write_text('*\n!.gitignore\n')
    return dict(project=str(output),manifest_sha256=sha((output/'manifest.json').read_bytes()),
                custom_sources=len(sources),vendor_sources=len(vendor),status=manifest['status'])
