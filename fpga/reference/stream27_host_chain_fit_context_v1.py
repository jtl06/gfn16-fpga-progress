"""Source-only whole-core fit handoff, not launch or money admission.

Joins the actual full-N native owner closure to the exact standalone project
and prepares the existing queue's read-only AWS descriptor. Frozen artifacts
are never relabeled; this receipt records the newly satisfied prerequisites.
"""
import hashlib
import json
from pathlib import Path
from . import stream27_host_chain_structural_v2 as structural
from fpga.tools import plain_fit_queue_v3 as queue

ROOT = structural.ROOT
OWNER = ROOT / 'results/throughput-20260929/s4-aw16-p8-full-host-owner-native-v1.json'
OWNER_PIN = 'eedb35c373ee4f5a082ec154bca3b7641b3a206575e7490e6c1bf094cbe0d10e'
PHASE = ROOT / 'results/throughput-20260929/s4-aw16-p8-full-host-closure-v2.json'
PHASE_PIN = '4e28b5da8b0e12f86fc4db466087fd69c231786c8fa7112d22cbfba2d5364af8'
INVENTORY = ROOT / 'results/throughput-20260929/s4-p8-whole-host-structural-source-v2/inventory.json'
INVENTORY_PIN = '205d13f6978c08d3b2beb276fae27aae05ebce554f0e072da246e299ec1ce316'
QUEUE_PIN = '540715a6f0a30b1d697a304d04c48546760b5bb6f759b6e93f49b82a88181ede'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(destination):
    destination = Path(destination).resolve()
    if destination.exists() or (ROOT / 'docs/briefs/PAUSE').exists():
        raise ValueError('S4_WHOLE_CONTEXT_FRESH_PAUSE')
    for path, pin in [(OWNER, OWNER_PIN), (PHASE, PHASE_PIN), (INVENTORY, INVENTORY_PIN),
                      (ROOT / 'tools/plain_fit_queue_v3.py', QUEUE_PIN)]:
        if sha(path) != pin:
            raise ValueError('S4_WHOLE_CONTEXT_PIN:' + str(path))
    owner, phase = json.loads(OWNER.read_text()), json.loads(PHASE.read_text())
    project = ROOT / structural.parent.PROJECT
    manifest = json.loads((project / 'manifest.json').read_text())
    if owner['status'] != 'PASS_owner_exploration_replay' or phase['status'] != owner['status']:
        raise ValueError('S4_WHOLE_CONTEXT_NATIVE_STATUS')
    if owner['standalone_generated_sha256'] != manifest['source_sha256']:
        raise ValueError('S4_WHOLE_CONTEXT_49_RTL_JOIN')
    if phase['physical_manifest_sha256'] != structural.parent.PROJECT_PIN:
        raise ValueError('S4_WHOLE_CONTEXT_PHYSICAL_JOIN')
    if manifest['core_parameters'] != dict(AW=16, P=8, CONTEXTS=1, EPOCH_SEED=65534):
        raise ValueError('S4_WHOLE_CONTEXT_PARAMETERS')
    structural.inventory()
    descriptor = queue.variant_descriptor(project.resolve(), 'gfn16-aws-m8i',
        structural_spec=dict(path=str(INVENTORY.resolve()), sha256=INVENTORY_PIN))
    destination.mkdir()
    (destination / 'variant-aws6.json').write_text(json.dumps(descriptor, indent=2) + '\n')
    receipt = dict(status='PASS_source_context_ONLY_NOT_fit_admitted',
        project=str(project.resolve()), project_manifest_sha256=structural.parent.PROJECT_PIN,
        structural_inventory=str(INVENTORY.resolve()), structural_inventory_sha256=INVENTORY_PIN,
        variant_sha256=sha(destination / 'variant-aws6.json'), project_context=descriptor['project'],
        native_owner_sha256=OWNER_PIN, native_phase_clarification_sha256=PHASE_PIN,
        actual_native_report_sha256=owner['report_sha256'], actual_native_gate_sha256=owner['gate_sha256'],
        candidate_root_sha256=owner['candidate_root_sha256'], standalone_rtl=49, paired_rtl=60,
        source_queue_api_sha256=QUEUE_PIN, preparer_sha256=sha(__file__),
        whole_horizon_seconds=21780, field_sizing_exemption=False,
        directly_asserted_native_programs=phase['direct_native_program_assertions'],
        source_event_ledger_not_native_trace=phase['source_event_ledger_not_separate_native_trace'],
        direct_native_schedule_assertions=phase['direct_native_schedule_assertions'],
        fit_allowed=False, promotion_allowed=False,
        remaining=['Fit-owner live budget/deadline/resources/slot admission; no allowance increase inferred',
                   'Actual whole-core synthesis/packing/four-corner STA; no field timing inheritance',
                   'Independent review and advisor verification before promotion'],
        scope='Exact full-N P8 source/native/config handoff; two jobs/nine arithmetic operations, not full-N PRP')
    (destination / 'source-context.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    import sys
    print(json.dumps(prepare(sys.argv[1]), indent=2))
