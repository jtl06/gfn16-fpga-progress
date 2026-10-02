"""Mechanical source-only C1 Azure project; never invokes vendor tools."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'results/throughput-20260929/core27-rootfused-crtmont64-aws-fit-v1'
C1=ROOT/'results/throughput-20260929/core27-crtmont-c1-8ns-aws-fit-v1'
OUTPUT=ROOT/'artifacts/core27-crtmont-c1-8ns-azure-v3-prepared'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def need(ok,why):
    if not ok:raise ValueError(why)
def dump(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')

def prepare():
    need(not (ROOT/'docs/briefs/PAUSE').exists(),'PAUSE')
    need(not OUTPUT.exists(),'fresh source-only output')
    need(sha(PARENT/'manifest.json')=='93af1da3453947be920e73ad3f9ead17da3a8249966c7d7db5353f4502f6ece3','exact promoted source parent')
    manifest=json.loads((PARENT/'manifest.json').read_text())
    for name,pin in manifest['source_sha256'].items():need(sha(PARENT/'rtl'/name)==pin,'unchanged RTL')
    controls={name:C1/'evidence'/('parent-'+name) for name in manifest['control_sha256']}
    for name,pin in manifest['control_sha256'].items():need(sha(controls[name])==pin,'unchanged initial parent control')
    need(sha(C1/'probe.sdc')=='137429e8c97e5322b5e02da7e24fac0100d18d36e9e47abdebf67c921698b5c7','exact prior C1 eight-ns constraint')
    need(sha(C1/'independent-review-v1.json')=='5691177fed3b4b7b03628c802e962d539f70ccc9c42fa38d6e27e004761262e9','prior C1 preserved review')
    qsf=controls['probe.qsf'].read_text()
    need('set_global_assignment -name NUM_PARALLEL_PROCESSORS 4' in qsf,'four-worker matched parent QSF')
    raw=controls['run.tcl'].read_text();anchor='    execute_module -tool syn\n'
    need(raw.count(anchor)==1,'unique post-synthesis gate point')
    inserted=anchor+'    project_close\n    exec /usr/bin/python3 -I -B /home/azureuser/gfn16-worker/c1-fit-tools-v3/run_prefit_da_gate_v1.py [pwd]\n    project_open probe\n'
    run=raw.replace(anchor,inserted,1)
    OUTPUT.mkdir(parents=True);project=OUTPUT/'project';(project/'rtl').mkdir(parents=True)
    for name in manifest['source_sha256']:shutil.copyfile(PARENT/'rtl'/name,project/'rtl'/name)
    for name in ('probe.qsf','probe.qpf'):shutil.copyfile(controls[name],project/name)
    shutil.copyfile(C1/'probe.sdc',project/'probe.sdc')
    with (project/'run.tcl').open('x') as stream:stream.write(run)
    manifest.update(clock_period_ns=8.0,compile_processors=4,provisional=True,promotion_allowed=False,
        physical_fit_qualified=False,usable_clock_mhz=None,status='prepared_source_only_native_DA_conditional',
        note='Exact 16-RTL promoted parent, parent four-worker QSF and prior C1 8ns SDC; only new post-synthesis native DA gate before fit. No execution or audited clock claim.',
        frozen_parent_manifest_sha256=sha(PARENT/'manifest.json'),
        inherited_parent_audit_sha256='fe70997804d364f0b79058cc00f233e6be01552226568f31aca42bf2bae5708e',
        prior_C1_independent_review_sha256=sha(C1/'independent-review-v1.json'),
        native_DA_gate=dict(required=True,phase='after_syn_before_fit',executable='/usr/bin/python3',
            script='/home/azureuser/gfn16-worker/c1-fit-tools-v3/run_prefit_da_gate_v1.py',
            source_binding='Runtime adapter must bind exact shared gate/crossing policy pins before dispatch; this project alone is not admission'),
        inherited_launcher_sha256=manifest.pop('launcher_sha256'),
        inherited_shell_launcher_sha256=manifest.pop('shell_launcher_sha256'))
    manifest['control_sha256']={name:sha(project/name) for name in ('probe.qsf','probe.qpf','probe.sdc','run.tcl')}
    dump(project/'manifest.json',manifest)
    for name,pin in manifest['source_sha256'].items():need(sha(project/'rtl'/name)==pin,'prepared RTL closure')
    need((project/'run.tcl').read_text().replace(inserted,anchor,1)==raw,'only exact gate Tcl insertion')
    result=dict(status='prepared_source_only_no_vendor_execution',project=str(project),manifest_sha256=sha(project/'manifest.json'),
        control_sha256=manifest['control_sha256'],rtl_files=len(manifest['source_sha256']),source_sha256=manifest['source_sha256'],
        parent_manifest_sha256=sha(PARENT/'manifest.json'),source_preparer_sha256=sha(Path(__file__)))
    dump(OUTPUT/'preparation.json',result);return result

if __name__=='__main__':print(json.dumps(prepare(),indent=2))
