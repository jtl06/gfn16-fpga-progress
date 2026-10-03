"""Settings-only response to actual Quartus18805; no pin/RTL/clock rewrite."""
import copy
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/trackS-r15-real-pcie-shell-v2'
PARENT=BASE/'physical-source-v4/project'
PARENT_SHA='b442e1d6db03b8f6978a8a93551efbc857872781733da6f75e9f22c11f6e63c1'
SPEC=BASE/'physical-source-v4/structural-inventory.json'
SPEC_SHA='6127cd3df10a60ff84d67bd66a33d0c1259968115e1c63d4b283ea89cbf3f782'
SELF='reference/stream27_r15_real_shell_clock_global_v1.py'
ASSIGNMENT='set_instance_assignment -name GLOBAL_SIGNAL "GLOBAL CLOCK" -to {clk_u59}\n'
FIT_REPORT=ROOT/'queue/standing-fit-state/terminal/s4-r15-real-pcie-shell-whole-12000-azure8-v1/evidence/project/output_files/probe.fit.rpt'

def sha(raw):return hashlib.sha256(raw).hexdigest()
def encoded(value):return (json.dumps(value,indent=2)+'\n').encode()

def prepare(output):
    out=Path(output).resolve()
    if not out.is_relative_to(BASE) or out.exists():raise ValueError('R15_GLOBAL_FRESH_OUTPUT')
    raw=(PARENT/'manifest.json').read_bytes()
    if sha(raw)!=PARENT_SHA or sha(SPEC.read_bytes())!=SPEC_SHA:raise ValueError('R15_GLOBAL_PARENT_IDENTITY')
    m=json.loads(raw);d=m['r15_real_shell'];report=FIT_REPORT.read_bytes()
    if b'Error (18805): No dedicated path available for refclk signal, clk_u59.' not in report:
        raise ValueError('R15_GLOBAL_ACTUAL_FAILURE_REQUIRED')
    before={str(p.relative_to(PARENT)):p.read_bytes() for p in PARENT.rglob('*') if p.is_file()}
    if any(p.is_symlink() for p in PARENT.rglob('*')):raise ValueError('R15_GLOBAL_NO_SYMLINK')
    for name,pin in m['control_sha256'].items():
        if sha(before[name])!=pin:raise ValueError('R15_GLOBAL_PARENT_CONTROL')
    for name,pin in m['source_sha256'].items():
        if sha(before['rtl/'+name])!=pin:raise ValueError('R15_GLOBAL_PARENT_RTL')
    qsf=before['probe.qsf'].decode()
    if '-name GLOBAL_SIGNAL' in qsf or 'set_location_assignment PIN_AP20 -to {clk_u59}' not in qsf:
        raise ValueError('R15_GLOBAL_UNIQUE_AP20_CLOCK')
    proof=dict(schema='r15-real-shell-global-refclk-v1',status='SUPPORTED_SETTINGS_CORRECTION_NOT_PHYSICAL_PASS',
      parent_manifest_sha256=PARENT_SHA,fit_report=dict(path=str(FIT_REPORT.relative_to(ROOT)),sha256=sha(report)),
      qsf_added_line=ASSIGNMENT.strip(),pin='AP20',input_hz=100000000,pll_period_ns=12,
      unchanged=['all72_custom_RTL','all335_vendor_inputs','five_QIPs','all_SDCs','device','seed','workers','native_parameters'],
      new_generation_required=False,new_native_arithmetic_gate_required=False,
      support=[dict(url='https://www.intel.com/programmable/technical-pdfs/683296.pdf',section='GLOBAL_SIGNAL',
        finding='Arria10 Global Clock assignment routes a pin-driven signal through the specified GLOBAL buffer.'),
        dict(url='https://www.intel.com/programmable/technical-pdfs/683461.pdf',section='Clock Networks and PLLs',
        finding='Core clock networks may source the IOPLL; non-dedicated/global routing has jitter implications and dedicated input is preferred.')],
      installed_support='Actual26.1 Error18805 explicitly recommends global promotion for this exact refclk.',
      calibration_warning='18326 retained: AP20 CLKUSR requires100–125MHz; pinned board source is100MHz. AUTO_RESERVE_CLKUSR_FOR_CALIBRATION is unchanged.',
      caveats=['Native fitter must establish actual global route and PLL legality.',
        'Do not add false paths, suppress timing errors, move pins, change device grade or infer board jitter/link qualification.',
        'Non-dedicated PLL reference jitter and all original E3/PHY warnings remain subject to physical/board validation.'])
    d['pin_qsf']+=ASSIGNMENT
    d['clock_routing_correction']=proof
    bundle=json.loads(before['rtl/proofs/source-bundle.json'])
    bundle['r15_real_shell']['pin_qsf']+=ASSIGNMENT
    bundle['r15_real_shell']['clock_routing_correction']=copy.deepcopy(proof)
    bundle['source_dependencies'].append(SELF);bundle['source_sha256'][SELF]=sha((ROOT/SELF).read_bytes())
    updates={'probe.qsf':(qsf+ASSIGNMENT).encode(),
      'rtl/proofs/source-bundle.json':encoded(bundle),'rtl/proofs/global-refclk-correction.json':encoded(proof)}
    d['source_bundle']['sha256']=sha(updates['rtl/proofs/source-bundle.json'])
    updates['rtl/proofs/real-shell.json']=encoded(d)
    for name,data in updates.items():m['control_sha256'][name]=sha(data)
    m['preparation_source_sha256'][SELF]=sha((ROOT/SELF).read_bytes())
    m['settings_parent_manifest_sha256']=PARENT_SHA
    updates['manifest.json']=encoded(m)
    # A fresh additive artifact only; frozen parent remains byte-for-byte.
    shutil.copytree(PARENT,out)
    for name,data in updates.items():(out/name).write_bytes(data)
    spec=json.loads(SPEC.read_bytes())
    spec['settings']=dict(m['control_sha256'],**{'manifest.json':sha(updates['manifest.json'])})
    spec['source_owner_binding']['project_manifest_sha256']=sha(updates['manifest.json'])
    spec['clock_routing_correction']=proof
    (out.parent/'structural-inventory.json').write_bytes(encoded(spec))
    return dict(project=str(out),manifest_sha256=sha(updates['manifest.json']),
      structural_sha256=sha(encoded(spec)),qsf_only_functional_delta=ASSIGNMENT.strip(),
      new_generation_required=False,new_native_gate_required=False)
