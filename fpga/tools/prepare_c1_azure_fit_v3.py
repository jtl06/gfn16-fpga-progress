"""Mechanical exact C1 packet assembly and fresh authenticated budget capture."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tarfile

FPGA = Path(__file__).resolve().parents[1]
DEST = FPGA/'artifacts/core27-crtmont-c1-8ns-azure-v3-prepared'
REMOTE_TOOLS = Path('/home/azureuser/gfn16-worker/c1-fit-tools-v3')


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True); stream.write('\n')


def main():
    assert not (FPGA/'docs/briefs/PAUSE').exists()
    fit = module('c1_runtime', FPGA/'cloud/azure_c1_fit_v3.py')
    old = module('c1_frozen_azure', FPGA/'cloud/azure_fit_v2.py')
    guard = module('c1_inherited', FPGA/'tools/prefit_c1_constraint_only_v1.py')
    meter = module('c1_hours', FPGA/'cloud/host_hours_azure_v2.py')
    project = DEST/'project'
    context = old.parent_verify_project(project)
    fit.exact_tcl((project/'run.tcl').read_text()); assessed = guard.assess(project)
    assert assessed['synthesis_allowed'] and not assessed['fit_allowed']
    observation = json.loads((DEST/'native-admission-observation-v1.json').read_text())
    assert observation['hostname'] == 'gfn16-azure-f16' and observation['protected'] == fit.PROTECTED
    assert observation['available_bytes'] >= 28 << 30 and observation['memory_total_bytes'] >= 120 << 30
    tools = DEST/'tools'; tools.mkdir(exist_ok=False)
    mapping = {name: FPGA/'cloud'/name for name in ('azure_c1_fit_v3.py','azure_fit_v2.py','aws_fit_v6.py','run-c1-azure-fit-v3.sh')}
    mapping.update({name: FPGA/'tools'/name for name in ('prefit_c1_constraint_only_v1.py','run_prefit_da_gate_v1.py','quartus_prefit_native_v3.py')})
    mapping['prefit_design_assistant_v2.tcl'] = FPGA/'synthesis/prefit_design_assistant_v2.tcl'
    mapping['fpga/cloud/host_hours_azure_v2.py'] = FPGA/'cloud/host_hours_azure_v2.py'
    assert set(mapping) == fit.HELPERS
    pins = {name: sha(path) for name, path in mapping.items()}
    assert all(pins[name] == pin for name,pin in fit.PINS.items())
    assert pins['run_prefit_da_gate_v1.py'] == 'fd6713ab06216347ebf9b12094bda0feb7f56c996fbf4ebae14f7073f3720477'
    assert pins['prefit_c1_constraint_only_v1.py'] == 'ee4c1a4086e05ac6fd68951ec96df48ca569caca0109921b460d83d3630855d1'
    provider = meter.provider_inputs()
    provider_path = DEST/'provider-inputs-v1.json'; save(provider_path, provider)
    provider_relative = str(provider_path.relative_to(FPGA))
    budget = meter.make_budget('gfn16-azure-f16', fit.MAX_SECONDS, provider_relative, sha(provider_path), context['manifest_sha256'])
    admitted = meter.validate_budget(budget, 'gfn16-azure-f16', fit.MAX_SECONDS, source_sha256=context['manifest_sha256'])
    topology = dict(schema='azure-fit-topology-v1',profile=old.PROFILE,
                    **{k:observation[k] for k in ('hostname','observed_at','cpus','memory_total_bytes')},slots=old.SLOTS)
    old.validate_topology(topology, 'a', [0,1,2,3], observation['cpus'], observation['hostname'], datetime.now(timezone.utc))
    save(tools/'topology.json', topology)
    for name, pin in meter.evidence_pins(budget).items():
        source = FPGA/name; assert sha(source) == pin
        target = tools/'fpga'/name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source,target)
    for name, path in mapping.items():
        target = tools/name; target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists(): shutil.copy2(path,target)
        assert sha(target) == pins[name]
    gate = dict(scope='whole_core', helper_sha256={str(REMOTE_TOOLS/name):pins[name] for name in
       ('run_prefit_da_gate_v1.py','prefit_design_assistant_v2.tcl','quartus_prefit_native_v3.py')},
       tool_sha256={name:pin for name,pin in observation['tool_sha256'].items() if name.endswith('/quartus_cdb')})
    ancestors = {path.name:sha(path) for path in (project/'evidence').iterdir()}
    assert set(ancestors) == {'parent-manifest.json','parent-sta-review.json','prior-c1-review.json','parent-probe.sdc'}
    approved = dict(schema='c1-azure-fit-exploration-v3',status='prepared_not_executed',project_name=fit.PROBE,
         unit=fit.UNIT,slot='a',promotion_allowed=False,project=context,helper_sha256=pins,
         tool_sha256=observation['tool_sha256'],prefit_gate=gate,topology_sha256=sha(tools/'topology.json'),
         host_hours_budget=budget,ancestor_evidence_sha256=ancestors,
         scope='Exact promoted-parent sixteen RTL/four workers/seed1, constraint-only8ns exploration; DA runs after syn and blocks fit on actual native failure/high severity. No timing/production claim.')
    save(tools/'approval.json', approved); save(DEST/'host-hours-admission-v1.json',admitted)
    with tarfile.open(DEST/'package-v3.tar.gz','w:gz') as archive:
        archive.add(project,arcname=fit.PROBE)
        archive.add(tools,arcname='c1-fit-tools-v3')
    report = dict(approval_sha256=sha(tools/'approval.json'),archive_sha256=sha(DEST/'package-v3.tar.gz'),
         archive_size=(DEST/'package-v3.tar.gz').stat().st_size, project=context,
         helper_sha256=pins, provider_observed=provider['observed_at_utc'], host_hours=admitted,
         source_preparer_sha256=sha(__file__))
    save(DEST/'packet-v3.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('project','host_hours','helper_sha256')},indent=2))


if __name__ == '__main__': main()
