"""Fresh generation input for aperture-guarded real PCIe system v2.

Writes only private source artifacts. No vendor execution or fitted claim.
"""
import hashlib
import json
from pathlib import Path
from .stream27_r15_qsys_application_v2 import component as application_component
from .stream27_r15_qsys_aperture_component_v1 import component as aperture_component
from .stream27_r15_qsys_guarded_recipe_v1 import recipe

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/trackS-r15-real-pcie-shell-v2'
GUARD='rtl/kernel/genefer_stream27_r15_dma_aperture_v1.sv'
GUARD_PIN='244ec8e67e8f61dddc3cb7c91f82ebe17fb92de2252a13fd3e55fccbc90fd644'
SELF='reference/stream27_r15_qsys_source_v2.py'


def prepare(bundle,output):
    out=Path(output).resolve()
    if not out.is_relative_to(BASE) or out.exists():raise ValueError('R15_QSYS_V2_FRESH_PRIVATE_OUTPUT')
    if bundle['parameters'].get('AW')!=16 or len(bundle['rtl_sources'])!=70 or bundle['r15_shell_application'].get('application_version')!=4:
        raise ValueError('R15_QSYS_V2_EXACT_APP_V4')
    if any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')):raise ValueError('R15_QSYS_PAUSE')
    guard=(ROOT/GUARD).read_text()
    if hashlib.sha256(guard.encode()).hexdigest()!=GUARD_PIN:raise ValueError('R15_QSYS_GUARD_FROZEN_PIN')
    if 'module genefer_stream27_r15_dma_aperture_v1' not in guard:raise ValueError('R15_QSYS_GUARD_TOP')
    files={'r15_application_v2_hw.tcl':application_component(bundle),
      'r15_dma_aperture_v1_hw.tcl':aperture_component(),
      'generate.tcl':recipe(),
      'rtl/genefer_stream27_r15_dma_aperture_v1.sv':guard}
    for p in bundle['rtl_sources']:files['rtl/'+p]=bundle['files'][p]
    pins={p:hashlib.sha256(text.encode()).hexdigest() for p,text in files.items()}
    effective=dict(bundle['parameters'],EPOCH_SEED0=0,EPOCH_SEED1=0)
    metadata={'schema':'r15-real-system-generation-input-v2',
      'status':'SOURCE_PREPARED_NO_VENDOR_EXECUTION','system_top':'r15_pcie_system_v2',
      'component_top':bundle['top'],'parameters':bundle['parameters'],
      'effective_parameters':effective,'parameter_binding':'source-locked-qsys',
      'epoch_binding':'literal application defaults0/0 forwarded to core; native full role must match',
      'files':pins,'custom_application_sources':bundle['rtl_sources'],
      'additional_native_guard_sources':{GUARD:hashlib.sha256(guard.encode()).hexdigest()},
      'source_dependencies':bundle['source_sha256'],
      'generator_sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
        (SELF,'reference/stream27_r15_qsys_application_v2.py',
         'reference/stream27_r15_qsys_aperture_component_v1.py',
         'reference/stream27_r15_qsys_guarded_recipe_v1.py','synthesis/r15_pcie_system_v1.tcl',GUARD)},
      'device':'10AX115N4F40E3SG','device_grade_changed':False,
      'clock_intent':{'hip_hz':250000000,'oscillator_hz':100000000,'core_requested_hz':83333333.0},
      'vendor_simulation_ready':False,'board_constraints_ready':False,
      'scope':'Actual generation and generated-port/QIP/decoder closure still required. No fit or board claim.'}
    out.mkdir(parents=True)
    for name,text in files.items():
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('x') as f:f.write(text)
    with (out/'input-manifest.json').open('x') as f:json.dump(metadata,f,indent=2);f.write('\n')
    with (out/'.gitignore').open('x') as f:f.write('*\n!.gitignore\n')
    return {'path':str(out),'sha256':hashlib.sha256((out/'input-manifest.json').read_bytes()).hexdigest(),
            'files':len(files),'status':metadata['status']}
