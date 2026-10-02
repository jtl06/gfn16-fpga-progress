"""Additive r53 metadata handoff for the unchanged matched F2 probes.

Keeps every RTL/QSF/SDC/run file byte-identical to the prepared v1 projects.
Retires r47's DA/early-placement launch blockers explicitly; those checks and
native wrapper/AW16 qualification remain result/promotion diagnostics. No job,
host/budget reservation, RTL mutation, or vendor invocation happens here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

from fpga.tools import prefit_structural_guard_v1 as structural


ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT/'artifacts/f2-registered-aw16-f0-physical-v1'
PINS = dict(parent='de1e4a6bfcf484102b80708a21c8384d6d3c5b8d9d440c1d094622833a9921d9',
            candidate='31f2177bf4ea18a934f49e58ab3976775a785690b32e3dde0b198edf9af9fc72')
CHECKER_SHA = '9494570410b0cfb083ae0d383164cf773bf7f8e8298e2b81dca7580914383979'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def prepare(output):
    structural.need(not (ROOT/'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    structural.need(sha(structural.__file__) == CHECKER_SHA, 'structural checker pin')
    output = Path(output)
    structural.need(output.is_absolute() and not output.exists() and output.parent.is_dir()
                    and output.parent.resolve() == output.parent, 'fresh canonical policy successor')
    projects = {}
    for role, pin in PINS.items():
        source = PARENT/role
        structural.need(sha(source/'manifest.json') == pin, 'frozen v1 project manifest')
        old = json.loads((source/'manifest.json').read_text())
        spec = json.loads((source/'structural-spec.json').read_text())
        structural.source_inventory(source, spec)
        project = output/role
        files = {**{'rtl/'+name: digest for name,digest in old['source_sha256'].items()},
                 **old['control_sha256']}
        for name, digest in files.items():
            structural.need(sha(source/name) == digest, 'v1 source/control closure')
            target = project/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source/name, target)
            structural.need(sha(target) == digest, 'unchanged source/control copy')
        manifest = dict(old)
        manifest.update(status='source_ready_exploratory_registered_one_field_probe_r53',
            r53_policy=dict(directly_adopted=True, scope='one_field_registered_sizing_wrapper_probe',
                design_prescreen_exempt=True, structural_inventory_retained=True,
                design_policy_allows_exploratory_fit=True,
                normal_dispatch_resource_source_version_PAUSE_budget_deadline_locks_required=True,
                superseded_r47_launch_blockers=['native Design Assistant','early-placement screen','exhaustive graph coverage'],
                post_fit_diagnostics=['Design Assistant','top100 crossing paths','graph coverage'],
                native_wrapper_and_AW16_gates='Parallel qualification; missing evidence prohibits promotion, not this exploratory probe launch.'),
            r47_scope='Historical v1 declared component inventory retained; launch policy superseded by directly adopted r53.',
            lineage=dict(parent_manifest_sha256=pin, unchanged_rtl_files=8,
                         unchanged_QSF_SDC_run_files=True, metadata_only_successor=True),
            native_small_gate_pending=True, physical_timing_proven=False)
        (project/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
        spec['settings']['manifest.json'] = sha(project/'manifest.json')
        inventory = structural.source_inventory(project, spec)
        (project/'structural-spec.json').write_text(json.dumps(spec, indent=2)+'\n')
        receipt = dict(status='PASS_declared_component_inventory_exploratory_fit_policy_r53',
            **structural.identities(spec), checker_sha256=CHECKER_SHA,
            source_inventory=inventory, inventory_sha256=structural.digest(spec),
            source_evidence_only=True, design_policy_allows_exploratory_fit=True,
            resource_admission_not_performed_by_preparer=True,
            old_fit_allowed_false_is_superseded_r47_metadata=True,
            DA_early_placement_graph_are_post_fit_diagnostics=True,
            native_small_registered_gate_pending=True, actual_AW16_integration_pending=True,
            production_promotion_allowed=False, physical_timing_proven=False)
        (project/'structural-source-result-v2.json').write_text(json.dumps(receipt, indent=2)+'\n')
        archive = output/(role+'-source-v2.tar.gz')
        with tarfile.open(archive, 'x:gz') as bundle:
            for path in sorted(project.rglob('*')):
                if path.is_file():
                    bundle.add(path, arcname='project/'+path.relative_to(project).as_posix(), recursive=False)
        projects[role] = dict(project_root=str(project), manifest_sha256=sha(project/'manifest.json'),
            source_archive=str(archive), source_archive_sha256=sha(archive), source_archive_bytes=archive.stat().st_size,
            source_sha256=manifest['source_sha256'], control_sha256=manifest['control_sha256'],
            structural_source_result_sha256=sha(project/'structural-source-result-v2.json'))
    result = dict(status='source_ready_matched_registered_F2_r53_handoff_no_job_launched', projects=projects,
                  no_RTL_QSF_SDC_run_delta=True, no_vendor_execution=True,
                  normal_dispatch_checks_still_required=True, design_policy_allows_exploratory_fit=True,
                  independent_native_pending=True, actual_AW16_pending=True, promotion_allowed=False)
    (output/'preparation.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
