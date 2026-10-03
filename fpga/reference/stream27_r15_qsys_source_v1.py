"""Prepare only the exact real-system generation input, never run vendor tools.

Qsys must still validate/generate the requested interconnect. Its actual output
tree, board wrapper and constraints form a later physical source closure.
"""
import hashlib
import json
from pathlib import Path
from .stream27_r15_qsys_application_v1 import component

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/trackS-r15-real-pcie-shell-v1'
RECIPE='synthesis/r15_pcie_system_v1.tcl'


def prepare(bundle,output):
    out=Path(output).resolve()
    if not out.is_relative_to(BASE) or out.exists():
        raise ValueError('R15_QSYS_FRESH_PRIVATE_OUTPUT')
    if bundle['parameters'].get('AW')!=16 or len(bundle['rtl_sources'])!=70:
        raise ValueError('R15_QSYS_EXACT_FULL_APPLICATION')
    if any((ROOT/p).exists() for p in ('queue/PAUSE','docs/briefs/PAUSE')):
        raise ValueError('R15_QSYS_PAUSE')
    files={'r15_application_v1_hw.tcl':component(bundle),
           'generate.tcl':(ROOT/RECIPE).read_text()}
    for name in bundle['rtl_sources']:
        files['rtl/'+name]=bundle['files'][name]
    pins={k:hashlib.sha256(v.encode()).hexdigest() for k,v in files.items()}
    meta={'schema':'r15-real-system-generation-input-v1',
      'status':'SOURCE_PREPARED_NO_VENDOR_EXECUTION',
      'component_top':bundle['top'],'parameters':bundle['parameters'],
      'files':pins,'custom_application_sources':bundle['rtl_sources'],
      'parent_component':bundle['r15_shell_application']['component_top'],
      'parent_component_parameters':bundle['r15_shell_application']['component_parameters'],
      'vendor_simulation_ready':False,'board_constraints_ready':False,
      'device':'10AX115N4F40E3SG','device_grade_changed':False,
      'clock_intent':{'hip_hz':250000000,'oscillator_hz':100000000,'core_requested_hz':83333333.0},
      'source_dependencies':bundle['source_sha256'],
      'generator_sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
        ('reference/stream27_r15_qsys_source_v1.py','reference/stream27_r15_qsys_application_v1.py',RECIPE)},
      'scope':'Vendor Qsys generation input only. No fit, real-I/O timing, hardware, DMA software or license signoff.'}
    out.mkdir(parents=True)
    for name,text in files.items():
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('x') as f:f.write(text)
    with (out/'input-manifest.json').open('x') as f:json.dump(meta,f,indent=2);f.write('\n')
    # All actual vendor output is private and is never part of public backup.
    with (out/'.gitignore').open('x') as f:f.write('*\n!.gitignore\n')
    return {'path':str(out),'files':len(files),'bytes':sum(len(v.encode()) for v in files.values()),
            'sha256':hashlib.sha256((out/'input-manifest.json').read_bytes()).hexdigest(),
            'status':meta['status']}
