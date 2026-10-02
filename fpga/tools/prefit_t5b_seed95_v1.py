"""Exact promoted-T5b seeds2/3,9.5ns source gate; synthesis only, no execution."""
import hashlib
import json
from pathlib import Path

PARENT='1a1a67980f1744be70c0b089dcdf7e20c4cdd8714cbac26bd5798c28abbcc011'
EVIDENCE={
 'parent-manifest.json':PARENT,
 'parent-100-review.json':'62933e09762f05ec7ad49338d734b23591275af92b7b9e931c98e6e3c3c87cea',
 'parent-9668-review.json':'bdc8295fc1dac155b28635b915c39c80b24e121001de9c6a8cba595de327bec2',
 'advisor-verification-T5b.md':'7a48c720b486799078fe6e4b0df4ef56840b0a295da576d6e7c2c93e1d28f04f'}
DA_HELPER='/home/azureuser/gfn16-worker/t5b-seeds-fit-tools-v1/run_prefit_da_gate_v2.py'
DA_SHA='64b5da40151f32cc5f3479622119c0f50091844f43b0a47f9b365b3bf3e5e02f'


def need(ok,why):
    if not ok:raise ValueError(why)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_tcl(parent):
    needle='    execute_module -tool syn\n'
    need(parent.count(needle)==1,'exact parent synthesis entry')
    text=parent.replace(needle,needle+'    project_close\n'+
        f'    exec /usr/bin/python3 {DA_HELPER} [pwd]\n'+
        '    project_open probe\n')
    needle='    project_close\n    error $failure'
    need(text.count(needle)==1,'exact parent error cleanup')
    return text.replace(needle,'    catch {project_close}\n    error $failure')


def assess(project):
    p=Path(project).resolve();e=p/'evidence'
    for name,pin in EVIDENCE.items():need(sha(e/name)==pin,'exact promoted parent evidence '+name)
    parent=json.loads((e/'parent-manifest.json').read_text());m=json.loads((p/'manifest.json').read_text())
    seed=m['seed'];need(type(seed) is int and seed in (2,3),'only requested seed2/3')
    need(m['source_sha256']==parent['source_sha256'] and len(m['source_sha256'])==16,'unchanged sixteen RTL')
    need({x.name for x in (p/'rtl').iterdir()}==set(m['source_sha256']),'closed RTL inputs')
    for name,pin in m['source_sha256'].items():need(sha(p/'rtl'/name)==pin,'RTL byte drift '+name)
    for name,pin in parent['control_sha256'].items():need(sha(e/('parent-'+name))==pin,'exact parent control '+name)
    qsf=(e/'parent-probe.qsf').read_text()
    need(qsf.count('NUM_PARALLEL_PROCESSORS 6')==1 and qsf.count('SEED 1\n')==1,'unique workers/seed anchors')
    qsf=qsf.replace('NUM_PARALLEL_PROCESSORS 6','NUM_PARALLEL_PROCESSORS 4').replace('SEED 1\n',f'SEED {seed}\n')
    sdc=(e/'parent-probe.sdc').read_text().replace('Exploratory 10 ns clock','Exploratory 9.5 ns clock').replace('-period 10 ','-period 9.5 ')
    need((p/'probe.qsf').read_text()==qsf and (p/'probe.sdc').read_text()==sdc,'only exact worker/seed/clock changes')
    need(sha(p/'probe.qpf')==parent['control_sha256']['probe.qpf'],'unchanged QPF')
    need((p/'run.tcl').read_text()==run_tcl((e/'parent-run.tcl').read_text()),'only exact DA gate insertion/caught error cleanup')
    for key in ('top','device','address_width','core_parameters','arithmetic_profile','core_field_basis','core_montgomery_radix_bits','root_profile_format','bitstream_generation'):
        need(m[key]==parent[key],'unchanged functional setting '+key)
    need(m['compile_processors']==4 and m['clock_period_ns']==9.5,'four workers/9.5ns only')
    controls={name:sha(p/name) for name in parent['control_sha256']}
    need(m['control_sha256']==controls and m['parent_physical_manifest_sha256']==PARENT,'manifest/control/parent correspondence')
    need(m['promotion_allowed'] is False and m['usable_clock_mhz'] is None and m['throughput'] is None,'no unmeasured promotion')
    return dict(status='PASS_T5b_seed95_source_synthesis_only',checker_sha256=sha(__file__),
      manifest_sha256=sha(p/'manifest.json'),parent_manifest_sha256=PARENT,seed=seed,
      clock_period_ns=9.5,workers=4,source_sha256=m['source_sha256'],control_sha256=controls,
      native_DA_helper=dict(path=DA_HELPER,sha256=DA_SHA),synthesis_allowed=True,
      inherited_topology_justification='Exact promoted T5b RTL; only seed, target clock and worker count differ. Not a new crossing proof.',
      native_crossing_coverage_complete=False,native_design_assistant_pass=False,fit_allowed=False,promotion_allowed=False,
      remaining='Runtime adapter must pin the qualified DA helper closure/tools and source context; native High/Critical/failure stops before fit. Host/slot/budget admission is separate.')


if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('project',type=Path);print(json.dumps(assess(a.parse_args().project),indent=2))
