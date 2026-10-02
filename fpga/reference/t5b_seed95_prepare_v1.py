"""Mechanical source-only T5b seed2/3 trial preparation; never dispatches."""
import copy
import json
from pathlib import Path
import shutil
from fpga.tools.prefit_t5b_seed95_v1 import PARENT,EVIDENCE,assess,need,run_tcl,sha

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/core27-t5b-provisional-fit-stage-v1/project'


def prepare(output,seed):
    output=Path(output).resolve();need(seed in (2,3) and not output.exists(),'fresh bounded seed project')
    need(not (ROOT/'docs/briefs/PAUSE').exists(),'brief PAUSE')
    need(sha(BASE/'manifest.json')==PARENT,'frozen production physical parent')
    parent=json.loads((BASE/'manifest.json').read_text())
    for name,pin in parent['source_sha256'].items():need(sha(BASE/'rtl'/name)==pin,'parent RTL')
    for name,pin in parent['control_sha256'].items():need(sha(BASE/name)==pin,'parent controls')
    evidence={
      'parent-manifest.json':BASE/'manifest.json',
      'parent-100-review.json':ROOT/'results/throughput-20260929/core27-t5b-100-audit-m8azn-v1/independent-review-v1.json',
      'parent-9668-review.json':ROOT/'results/throughput-20260929/core27-t5b-selected9668-audit-m8azn-v3/independent-review-v1.json',
      'advisor-verification-T5b.md':ROOT/'docs/briefs/2026-10-01-advisor-verification-T5b.md'}
    for name,path in evidence.items():need(sha(path)==EVIDENCE[name],'promoted evidence')
    (output/'rtl').mkdir(parents=True);(output/'evidence').mkdir()
    for name in parent['source_sha256']:shutil.copyfile(BASE/'rtl'/name,output/'rtl'/name)
    for name,path in evidence.items():shutil.copyfile(path,output/'evidence'/name)
    for name in parent['control_sha256']:shutil.copyfile(BASE/name,output/'evidence'/('parent-'+name))
    qsf=(BASE/'probe.qsf').read_text().replace('NUM_PARALLEL_PROCESSORS 6','NUM_PARALLEL_PROCESSORS 4').replace('SEED 1\n',f'SEED {seed}\n')
    sdc=(BASE/'probe.sdc').read_text().replace('Exploratory 10 ns clock','Exploratory 9.5 ns clock').replace('-period 10 ','-period 9.5 ')
    (output/'probe.qsf').write_text(qsf);(output/'probe.sdc').write_text(sdc)
    shutil.copyfile(BASE/'probe.qpf',output/'probe.qpf')
    (output/'run.tcl').write_text(run_tcl((BASE/'run.tcl').read_text()))
    m=copy.deepcopy(parent)
    for key in ('adapter_sha256','resource_policy_sha256','frozen_policy_sha256','resource_profile','execution_changes','evidence_sha256','qualification'):
        m.pop(key,None)
    m.update(seed=seed,clock_period_ns=9.5,compile_processors=4,
      target=f'T5b_seed{seed}_95ns_azure_source_v1',status='prepared_not_executed',
      parent_physical_manifest_sha256=PARENT,T5b_correctness_complete=True,
      note='Exact promoted T5b RTL. Seed/constraint-only provisional record trial; no inherited higher clock or throughput claim. Host/workers differ from parent.',
      isolated_RTL_change='none',runtime_single_variable_comparison=False,
      qualification_scope='Parent promotion retained exclusions: no >=1000-square soak or board/reset-release signoff.',
      control_sha256={name:sha(output/name) for name in parent['control_sha256']})
    (output/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    result=assess(output);(output.parent/'source-preparation.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.output,a.seed),indent=2))
