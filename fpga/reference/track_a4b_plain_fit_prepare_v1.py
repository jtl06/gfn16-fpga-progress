"""Mechanical r53 A4b project preparation; no vendor execution or launch."""
import copy,hashlib,json,shutil
from pathlib import Path
from fpga.cloud.plain_fit_v1 import FULL_TCL
from fpga.tools.prefit_structural_guard_v1 import source_inventory,identities
ROOT=Path(__file__).resolve().parents[1]
PARENT='results/throughput-20260929/track-a4b-prefit-source-v1/project'
PARENT_SHA='6117a39fb1c5f10ecb304153331a0bee0833518b51c7a291e0445b7617e72c92'
SPEC='results/throughput-20260929/track-a4b-prefit-source-v2/inventory.json'
SPEC_SHA='47469dffa965c20843f2d65ca263f603a51eec9391c22dbc65a597bcc7c6eb7a'
CHECKER_SHA='9494570410b0cfb083ae0d383164cf773bf7f8e8298e2b81dca7580914383979'
EVIDENCE={
 'results/throughput-20260929/track-a4b-representative-aw16-native-independent-v1.json':'4106cd4b7707eaf891db940305c406a013ed83b926614703f692e6b4bdcbb011',
 'results/throughput-20260929/track-a4b-admission-mutants-native-independent-v1.json':'28bf62afd1db820bd447c829a0a0e87f60ede5eba1934a090e61559191a26a37'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,value):p.write_text(json.dumps(value,indent=2)+'\n')

def prepare(output):
    output=Path(output).resolve();parent=ROOT/PARENT
    if output.exists() or (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('fresh output/no PAUSE')
    if sha(parent/'manifest.json')!=PARENT_SHA or sha(ROOT/SPEC)!=SPEC_SHA or sha(ROOT/'tools/prefit_structural_guard_v1.py')!=CHECKER_SHA:raise ValueError('frozen source inventory identity')
    for name,pin in EVIDENCE.items():
        if sha(ROOT/name)!=pin:raise ValueError('native prerequisite receipt drift')
    m=json.loads((parent/'manifest.json').read_text());original=copy.deepcopy(m)
    if len(m['source_sha256'])!=29 or m['compile_processors']!=6 or m['seed']!=1 or m['clock_period_ns']!=10:raise ValueError('exact predecessor geometry')
    project=output/'project';(project/'rtl').mkdir(parents=True)
    for name,pin in m['source_sha256'].items():
        src=parent/'rtl'/name
        if sha(src)!=pin:raise ValueError('RTL drift')
        shutil.copyfile(src,project/'rtl'/name)
    for name,pin in m['control_sha256'].items():
        if sha(parent/name)!=pin:raise ValueError('control drift')
        shutil.copyfile(parent/name,project/name)
    qsf=(project/'probe.qsf').read_text()
    if 'ENABLE_INTERMEDIATE_SNAPSHOTS' in qsf:raise ValueError('unexpected existing snapshot assignment')
    (project/'probe.qsf').write_text(qsf+'set_global_assignment -name ENABLE_INTERMEDIATE_SNAPSHOTS ON\n')
    (project/'run.tcl').write_text(FULL_TCL)
    m.update(status='source_prepared_plain_fit_not_dispatched',edition='pro',allowed_stages=['syn','fit','sta'],
             parent_manifest_sha256=PARENT_SHA,intermediate_snapshots=True,promotion_allowed=False,
             note='r53 plain exploratory fit; unchanged29RTL. Structural source check only pre-fit; vendor diagnostics post-fit. No dispatch authority or physical claim.')
    m['control_sha256']={name:sha(project/name) for name in original['control_sha256']}
    save(project/'manifest.json',m)
    spec=json.loads((ROOT/SPEC).read_text());spec['settings']={**m['control_sha256'],'manifest.json':sha(project/'manifest.json')}
    # All source/port/stage/exception declarations are byte-for-value inherited.
    result=source_inventory(project,spec)
    if result['findings']:raise ValueError('structural source findings')
    save(output/'inventory.json',spec)
    context=dict(manifest_sha256=sha(project/'manifest.json'),source_sha256=m['source_sha256'],
                 control_sha256={**m['control_sha256'],'manifest.json':sha(project/'manifest.json')},qsf_parameters=m['core_parameters'])
    save(output/'project-context.json',context)
    report=dict(status='PASS_source_inventory_only',project=str(project),**identities(spec),
                manifest_sha256=sha(project/'manifest.json'),inventory_sha256=sha(output/'inventory.json'),
                context_sha256=sha(output/'project-context.json'),checker_sha256=CHECKER_SHA,
                parent_manifest_sha256=PARENT_SHA,parent_inventory_sha256=SPEC_SHA,
                native_prerequisite_receipts=EVIDENCE,source_inventory=result,
                rtl_changes=0,changed_controls=['probe.qsf: intermediate snapshots ON','run.tcl: exact plain_fit_v1.FULL_TCL'],
                preserved_settings=dict(workers=6,seed=1,clock_period_ns=10,AW=16),
                vendor_executed=False,fit_launched=False,promotion_allowed=False)
    save(output/'source-preparation.json',report);return report

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(prepare(a.output),indent=2))
