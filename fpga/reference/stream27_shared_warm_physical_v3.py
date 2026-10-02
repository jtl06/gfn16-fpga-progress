"""Plain-runner control-name adapter. All 23 native-qualified RTL stay exact."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

from .stream27_shared_field_v1 import ROOT
from fpga.cloud.plain_fit_v2 import FULL_TCL
from fpga.cloud.aws_fit_v6 import verify_project

PARENT='artifacts/stream27-s4-aw16-p16-warm-sizing-v2/project'
PARENT_PIN='faa666771eb4f1057daedda57dd4ace365a504cb06e8c031265b3916a9c5af98'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(destination):
    destination=Path(destination).resolve();parent=ROOT/PARENT
    if destination.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('S4_PLAIN_CONTROL_FRESH_PAUSE')
    if sha(parent/'manifest.json')!=PARENT_PIN:raise ValueError('S4_PLAIN_CONTROL_PARENT_DRIFT')
    m=json.loads((parent/'manifest.json').read_text())
    for group,subdir in (('source_sha256','rtl/'),('control_sha256','')):
        for name,pin in m[group].items():
            if sha(parent/(subdir+name))!=pin:raise ValueError('S4_PLAIN_CONTROL_INPUT_DRIFT:'+name)
    project=destination/'project';(project/'rtl').mkdir(parents=True)
    for name in m['source_sha256']:shutil.copyfile(parent/'rtl'/name,project/'rtl'/name)
    qsf=(parent/'warm.qsf').read_text()
    if qsf.count('SDC_FILE warm.sdc')!=1:raise ValueError('S4_PLAIN_CONTROL_SDC_ANCHOR')
    controls={'probe.qsf':qsf.replace('SDC_FILE warm.sdc','SDC_FILE probe.sdc'),
        'probe.qpf':'PROJECT_REVISION = "probe"\n','probe.sdc':(parent/'warm.sdc').read_text(),'run.tcl':FULL_TCL}
    for name,text in controls.items():(project/name).write_text(text)
    m['control_sha256']={name:hashlib.sha256(text.encode()).hexdigest() for name,text in controls.items()}
    m['sizing_control_adapter']=dict(parent_manifest_sha256=PARENT_PIN,
        preparer_sha256=sha(ROOT/'reference/stream27_shared_warm_physical_v3.py'),
        plain_runner_sha256=sha(ROOT/'cloud/plain_fit_v2.py'),
        delta='warm controls renamed probe; project revision probe; SDC filename reference; exact plain FULL_TCL. No RTL/parameters/clock/seed/worker/snapshot change.')
    (project/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    context=verify_project(project)
    if context['source_sha256']!=m['source_sha256']:raise ValueError('S4_PLAIN_CONTROL_RTL_DRIFT')
    result=dict(status='plain_control_source_verified_not_dispatched',project=context,
        source_files=len(m['source_sha256']),parent_manifest_sha256=PARENT_PIN,
        rtl_unchanged=True,clock_period_ns=10,seed=1,compile_processors=4,
        allowed_stages=['syn','fit','sta'],sizing_exemption='component_sizing_probe',
        native_report_sha256=m['native_report_sha256'],native_gate_sha256=m['native_gate_sha256'],
        promotion_allowed=False)
    (destination/'preparation.json').write_text(json.dumps(result,indent=2)+'\n')
    with tarfile.open(destination/'source.tar.gz','x:gz') as archive:
        for path in sorted(project.rglob('*')):
            if path.is_file():archive.add(path,arcname='project/'+str(path.relative_to(project)),recursive=False)
        archive.add(destination/'preparation.json',arcname='preparation.json',recursive=False)
    result['archive_sha256']=sha(destination/'source.tar.gz');return result


if __name__=='__main__':
    import sys
    if len(sys.argv)!=2:raise ValueError('S4_PLAIN_CONTROL_USAGE')
    r=prepare(sys.argv[1]);print(json.dumps(r,indent=2))
