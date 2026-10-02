"""Preserve P16-c RTL, repair explicit parameters, retain future fitter snapshots.

Preparation only: no synthesis, DA, cross-block, fitter or timing qualification.
The original probe project and all thirteen RTL sources remain immutable.
"""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'artifacts/stream27-p16c-aw16-p16-f0-prepared-v1/project'
PIN='42901776c0a7c55aeeb8bde4e6de695cb05e0eb6a610de9d408becffcae38530'
SNAPSHOT='set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS on\n'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(destination):
    destination=Path(destination).resolve()
    assert not destination.exists() and not (ROOT/'docs/briefs/PAUSE').exists()
    assert sha(PARENT/'manifest.json')==PIN
    old=json.loads((PARENT/'manifest.json').read_text())
    assert old['address_width']==16 and len(old['source_sha256'])==13
    files={**{'rtl/'+name:pin for name,pin in old['source_sha256'].items()},**old['control_sha256']}
    assert {str(p.relative_to(PARENT)) for p in PARENT.rglob('*') if p.is_file()}==set(files)|{'manifest.json'}
    for name,pin in files.items():assert sha(PARENT/name)==pin
    project=destination/'project';project.mkdir(parents=True)
    for name in files:
        target=project/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(PARENT/name,target)
    qsf=(project/'probe.qsf').read_text()
    assert 'ENABLE_INTERMEDIATE_SNAPSHOTS' not in qsf
    assert qsf.count('set_parameter -name AW 16\n')==1
    assert qsf.count('set_parameter -name CONTEXTS 1\n')==1
    (project/'probe.qsf').write_text(qsf+SNAPSHOT)
    new=dict(old)
    new.update(status='prepared_provisional_P16C_metadata_snapshot_successor_not_executed',
        core_parameters={'AW':16,'CONTEXTS':1},
        control_sha256={name:sha(project/name) for name in old['control_sha256']},
        successor_lineage=dict(parent_manifest_sha256=PIN,unchanged_rtl_files=13,
            metadata_delta='Declare existing QSF AW16/CONTEXTS1 explicitly; no RTL or parameter change.',
            settings_delta=SNAPSHOT.strip(),
            snapshot_scope='Retain planned/placed/routed/retimed databases for future post-place diagnostics; extra disk design-dependent and unmeasured.',
            native_small_control_report_sha256='9821d28d1615e88b3bf41eebed3fef2165dfdc0c84266baaf855048bf29fdf66',
            gate='Bounded synthesis-only then exact-source native DA and mapped cross-block checks before fit admission. N64 control is not N65536 numerical qualification.'))
    (project/'manifest.json').write_text(json.dumps(new,indent=2)+'\n')
    assert new['source_sha256']==old['source_sha256']
    from fpga.cloud.aws_fit_v6 import verify_project
    verified=verify_project(project)
    assert verified['qsf_parameters']=={'AW':16,'CONTEXTS':1}
    closure={str(p.relative_to(project)):sha(p) for p in sorted(project.rglob('*')) if p.is_file()}
    result=dict(status='SOURCE_ONLY_READY_FOR_SYNTHESIS_ADMISSION',project_manifest_sha256=sha(project/'manifest.json'),
        parent_manifest_sha256=PIN,source_sha256=old['source_sha256'],project_sha256=closure,
        exact_changed_project_files=['manifest.json','probe.qsf'],settings_delta=SNAPSHOT.strip(),
        fit_allowed=False,promotion_allowed=False,missing=['native synthesis','exact native Design Assistant severity report','complete native mapped cross-block coverage','host-specific source adapter and fresh budget/resource admission'])
    (destination/'preparation.json').write_text(json.dumps(result,indent=2)+'\n')
    with tarfile.open(destination/'source.tar.gz','x:gz') as archive:
        for name in closure:archive.add(project/name,arcname='project/'+name,recursive=False)
        archive.add(destination/'preparation.json',arcname='preparation.json',recursive=False)
    return result


if __name__=='__main__':
    import sys
    assert len(sys.argv)==2
    r=prepare(sys.argv[1]);print(json.dumps({k:r[k] for k in ('status','project_manifest_sha256','exact_changed_project_files','fit_allowed','missing')},indent=2))
