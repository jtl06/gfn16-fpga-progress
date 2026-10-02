"""Controls-only F16 four-worker counterpart of the exact AWS6 whole core.

No DUT, native arithmetic, clock, seed or false-path changes. Fit owner alone
performs fresh USD60 aggregate rolling-cap/live-host/slot/budget admission.
"""
import copy
import hashlib
import json
from pathlib import Path
from . import stream27_host_chain_physical_v1 as physical
from . import stream27_host_chain_fit_context_v1 as native
from fpga.tools import plain_fit_queue_v3 as queue
from fpga.tools.prefit_structural_guard_v1 import source_inventory, identities

ROOT = physical.ROOT


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(destination):
    destination = Path(destination).resolve()
    if destination.exists() or (ROOT / 'docs/briefs/PAUSE').exists():
        raise ValueError('S4_F164_FRESH_PAUSE')
    result = physical.prepare(destination, workers=4)
    project = destination / 'project'
    aws_project = ROOT / native.structural.parent.PROJECT
    old = json.loads((aws_project / 'manifest.json').read_text())
    new = json.loads((project / 'manifest.json').read_text())
    owner = json.loads(native.OWNER.read_text())
    if sha(native.OWNER) != native.OWNER_PIN or sha(native.PHASE) != native.PHASE_PIN:
        raise ValueError('S4_F164_NATIVE_PIN')
    if new['source_sha256'] != old['source_sha256'] or new['source_sha256'] != owner['standalone_generated_sha256']:
        raise ValueError('S4_F164_49_RTL_BYTES')
    if new['core_parameters'] != old['core_parameters'] or new['compile_processors'] != 4:
        raise ValueError('S4_F164_PARAMETERS_WORKERS')
    expected_qsf = (aws_project / 'probe.qsf').read_text().replace(
        'set_global_assignment -name NUM_PARALLEL_PROCESSORS 6\n',
        'set_global_assignment -name NUM_PARALLEL_PROCESSORS 4\n')
    if (project / 'probe.qsf').read_text() != expected_qsf:
        raise ValueError('S4_F164_ONLY_WORKER_QSF_DELTA')
    for filename in ('probe.qpf', 'probe.sdc', 'run.tcl'):
        if (project / filename).read_bytes() != (aws_project / filename).read_bytes():
            raise ValueError('S4_F164_OTHER_CONTROL_CHANGED')
    if sha(native.INVENTORY) != native.INVENTORY_PIN:
        raise ValueError('S4_F164_PARENT_INVENTORY_PIN')
    inventory = copy.deepcopy(json.loads(native.INVENTORY.read_text()))
    inventory['settings'] = {**new['control_sha256'], 'manifest.json': sha(project / 'manifest.json')}
    findings = source_inventory(project, inventory)
    if findings['findings']:
        raise ValueError('S4_F164_STRUCTURAL_FINDINGS')
    spec_path = destination / 'structural-inventory.json'
    spec_path.write_text(json.dumps(inventory, indent=2) + '\n')
    descriptor = queue.variant_descriptor(project.resolve(), 'gfn16-azure-f16',
        structural_spec=dict(path=str(spec_path.resolve()), sha256=sha(spec_path)))
    variant_path = destination / 'variant-f164.json'
    variant_path.write_text(json.dumps(descriptor, indent=2) + '\n')
    review = ROOT / 'results/throughput-20260929/s4-full-host-qualification-recovery-independent-v1.json'
    if not review.is_file():
        raise ValueError('S4_F164_INDEPENDENT_RECEIPT_MISSING')
    receipt = dict(status='PASS_controls_only_source_context_NOT_native_fit_admission',
        **identities(inventory), project=str(project.resolve()), project_manifest_sha256=sha(project / 'manifest.json'),
        aws_parent_manifest_sha256=native.structural.parent.PROJECT_PIN,
        candidate_root_sha256=owner['candidate_root_sha256'], rtl_sources=49, all_RTL_bytes_unchanged=True,
        parameters=new['core_parameters'], workers=4, seed=1, clock_period_ns=10,
        snapshots_ON=True, full_TCL_unchanged=True, false_paths_added=False,
        structural_inventory=str(spec_path.resolve()), structural_inventory_sha256=sha(spec_path),
        structural_guard_findings=findings['findings'], transfer_count=len(inventory['transfers']),
        variant_sha256=sha(variant_path), project_context=descriptor['project'],
        native_owner_sha256=native.OWNER_PIN, actual_native_report_sha256=owner['report_sha256'],
        actual_native_gate_sha256=owner['gate_sha256'], phase_clarification_sha256=native.PHASE_PIN,
        independent_receipt=str(review.resolve()), independent_receipt_sha256=sha(review),
        source_archive_sha256=result['archive_sha256'], preparer_sha256=sha(__file__),
        whole_horizon_seconds=21780, field_sizing_exemption=False,
        fit_allowed=False, promotion_allowed=False,
        remaining=['Fresh ordinary fit-owner resources/live host/slot/budget/deadline admission under approved aggregate Azure rolling60 policy',
                   'Actual whole synthesis/fit/four-corner STA; field timing is not whole timing'],
        delta='NUM_PARALLEL_PROCESSORS6→4 and compile_workers metadata/control hashes only; AWS6 preserved')
    (destination / 'source-handoff.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    import sys
    result = prepare(sys.argv[1])
    print(json.dumps({key: result[key] for key in ('status', 'project', 'project_manifest_sha256',
        'structural_inventory_sha256', 'variant_sha256', 'candidate_root_sha256', 'workers',
        'all_RTL_bytes_unchanged', 'native_owner_sha256', 'independent_receipt_sha256')}, indent=2))
