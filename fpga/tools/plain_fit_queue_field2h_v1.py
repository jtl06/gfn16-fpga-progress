"""Finite FIELD-only2h controller derived from pinned queue_v3.

New jobs must be component_probe + component_sizing_probe. Actual services use
7200s/60s, native runner uses7200s, fresh host-hours uses7260s. Original six-hour
jobs may be adopted unchanged; only newly marked field requests use the2h
terminal contract. Same fixed pools, slot restrictions, source closure, PAUSE,
policy, cutoff, journal and uncertain-handle reconciliation. No new allocator,
scheduler, lifecycle or accounting authority. CLI is the frozen queue CLI.

The frozen source is transformed only at unique checked anchors in memory.
SSH receives the expanded policy, not a wrapper needing Mac files on workers.
"""
import hashlib
from pathlib import Path

FIELD_PARENT_SHA='540715a6f0a30b1d697a304d04c48546760b5bb6f759b6e93f49b82a88181ede'
FIELD_RUNNER_SHA='1ba445d8a8b9865ce3d2e4a38d37caba7a13544a93bac3c198289d18c80af579'
FIELD_CONTRACT=dict(kind='field-fit-two-hour-v1',native_timeout_seconds=7200,outer_runtime_seconds=7200,
                    timeout_stop_seconds=60,host_hours_horizon_seconds=7260)


def expanded_source():
    path=Path(__file__).resolve().parent/'plain_fit_queue_v3.py'
    if path.resolve()!=path or not path.is_file() or path.stat().st_nlink!=1 or hashlib.sha256(path.read_bytes()).hexdigest()!=FIELD_PARENT_SHA:
        raise ValueError('frozen queue_v3 source drift')
    source=path.read_text()
    old_variant="need(set(variant) in ({'path','files','project','structural_spec'},{'path','files','project','exemption'}),'closed source variant')"
    field_guard="need(job['scope']=='component_probe' and job['variants'][host].get('exemption')=='component_sizing_probe' and 'structural_spec' not in job['variants'][host],'two-hour new launches are FIELD sizing only')"
    launch_guard="need(handle.get('scope')=='component_probe' and approved.get('scope')=='component_probe' and approved.get('exemption')=='component_sizing_probe' and approved.get('mode')=='full' and 'structural_spec' not in approved and approved.get('runtime_contract')==FIELD_CONTRACT and all(type(approved['runtime_contract'][key]) is int for key in FIELD_CONTRACT if key!='kind'),'two-hour native launch is FIELD sizing only')"
    terminal_anchor="    context=json.loads(regular(root/'project/execution-context.json')); config=HOSTS[handle['host']]"
    terminal_guard="""    native_timeout=21600
    if 'runtime_contract' in request:
        need(request.get('scope')=='component_probe' and handle['scope']=='component_probe' and request.get('exemption')=='component_sizing_probe'
             and request.get('mode')=='full' and 'structural_spec' not in request and request['runtime_contract']==FIELD_CONTRACT
             and all(type(request['runtime_contract'][key]) is int for key in FIELD_CONTRACT if key!='kind'),'exact field terminal request contract')
        native_timeout=7200
        need(proof['manager_elapsed_seconds']<=7260,'field invocation exceeds actual outer+grace bound')
    context=json.loads(regular(root/'project/execution-context.json')); config=HOSTS[handle['host']]
    if native_timeout==7200:
        need(context.get('runtime_kind')==FIELD_CONTRACT['kind'] and context.get('outer_runtime_max_seconds')==7200
             and context.get('outer_timeout_stop_seconds')==60 and context.get('allowed_cpus')==config['slots'][handle['slot']]
             and context.get('launcher_sha256')==PINS['cloud/plain_fit_field2h_v1.py'],'actual two-hour native cgroup/source metadata')"""
    changes=[
      ('RUNTIME, GRACE, HORIZON = 21720, 60, 21780','RUNTIME, GRACE, HORIZON = 7200, 60, 7260\nFIELD_CONTRACT='+repr(FIELD_CONTRACT)),
      ("PINS = {","PINS = {\n 'cloud/plain_fit_field2h_v1.py':"+repr(FIELD_RUNNER_SHA)+','),
      ("job['scope'] in ('component_probe','whole_core') and job['variants']","job['scope']=='component_probe' and job['variants']"),
      (old_variant,"need(set(variant)=={'path','files','project','exemption'} and variant['exemption']=='component_sizing_probe','two-hour queue accepts only component sizing variants')"),
      ("    if op=='launch':\n        slot_preflight(host,handle['slot'])","    if op=='launch':\n        "+launch_guard+"\n        slot_preflight(host,handle['slot'])"),
      ("'--property=RuntimeMaxSec=21720'","'--property=RuntimeMaxSec=7200'"),
      ("str(helpers/'plain_fit_v2.py')","str(helpers/'plain_fit_field2h_v1.py')"),
      ('        source=regular(Path(__file__).resolve()).decode()','        source=FIELD_CONTROLLER_SOURCE'),
      (terminal_anchor,terminal_guard),
      ("context['timeout_seconds']==21600","context['timeout_seconds']==native_timeout"),
      ('def prepare(job,host,slot,directory,topology,now):\n',
       'def prepare(job,host,slot,directory,topology,now):\n    '+field_guard+"\n    regular(FPGA/'cloud/plain_fit_field2h_v1.py',PINS['cloud/plain_fit_field2h_v1.py'])\n"),
      ("for relative in ('cloud/plain_fit_v2.py','cloud/aws_fit_v6.py','tools/prefit_structural_guard_v1.py'):",
       "for relative in ('cloud/plain_fit_field2h_v1.py','cloud/plain_fit_v2.py','cloud/aws_fit_v6.py','tools/prefit_structural_guard_v1.py'):"),
      ("topology_sha256=digest(regular(tools/'topology.json')),promotion_allowed=False)",
       "topology_sha256=digest(regular(tools/'topology.json')),promotion_allowed=False,scope='component_probe',runtime_contract=FIELD_CONTRACT)"),
      ('# Do not start a six-hour fit whose admitted outer bound reaches past','# Do not start a two-hour FIELD fit whose actual outer bound reaches past'),
      ("if __name__=='__main__': main()","if False: main()")]
    for before,after in changes:
        if source.count(before)!=1: raise ValueError('exact unique frozen field-controller anchor: '+before)
        source=source.replace(before,after,1)
    return source


FIELD_CONTROLLER_SOURCE=expanded_source()
exec(compile(FIELD_CONTROLLER_SOURCE,'plain_fit_queue_v3.py[field2h-bound-only]','exec'),globals())


if __name__=='__main__': main()
