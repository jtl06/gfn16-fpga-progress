"""Source-only matched F2 plain-Tcl successor, no remote/vendor execution."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

from fpga.cloud import plain_fit_v2 as plain
from fpga.tools import prefit_structural_guard_v1 as structural


ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT/'artifacts/f2-registered-aw16-f0-physical-policy-v2'
PINS = dict(parent='96e28f0003ad9c18760f6ee434d4b0ab86184d098d75dd848fe17e38463a2966',
            candidate='caa6f6ac84714047109f09a6d3c23bbf0b296cff083aced023532821b69a750d')
NATIVE = 'edc6bea7c2308b841bc643c5e94e85fb38aa267e35fd3b500d776f09e2fba23e'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def prepare(output):
    structural.need(not (ROOT/'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    structural.need(sha(ROOT/'results/throughput-20260929/f2-registered-native-independent-v1.json') == NATIVE,
                    'scoped registered AW5 independent receipt')
    output = Path(output)
    structural.need(output.is_absolute() and not output.exists() and output.parent.is_dir()
                    and output.parent.resolve() == output.parent, 'fresh canonical plain successor')
    results = {}
    for role, pin in PINS.items():
        source = PARENT/role
        structural.need(sha(source/'manifest.json') == pin, 'policy-v2 parent manifest')
        old = json.loads((source/'manifest.json').read_text())
        spec = json.loads((source/'structural-spec.json').read_text())
        structural.source_inventory(source, spec)
        project = output/role
        files = {**{'rtl/'+name: digest for name,digest in old['source_sha256'].items()},
                 **old['control_sha256']}
        for name, digest in files.items():
            structural.need(sha(source/name) == digest, 'immutable source/control parent')
            destination = project/name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if name == 'run.tcl':
                destination.write_text(plain.FULL_TCL)
            else:
                shutil.copyfile(source/name, destination)
                structural.need(sha(destination) == digest, 'unchanged plain source/control copy')
        manifest = dict(old)
        manifest.update(status='source_ready_F2_registered_plain_fit_v1_not_executed',
            control_sha256={name: sha(project/name) for name in old['control_sha256']},
            native_small_gate_pending=False, native_small_independent_receipt_sha256=NATIVE,
            actual_AW16_integration_pending=True,
            plain_flow=dict(source='cloud/plain_fit_v2.py', generator_sha256=sha(plain.__file__),
                Quartus_version=plain.VERSION, run_tcl_sha256=sha(project/'run.tcl'),
                stages=['syn','fit','sta'], declared_STA='multi-corner; actual corner reports must be checked after execution',
                no_assembler=True, no_system_Python_pin=True),
            lineage=dict(parent_manifest_sha256=pin, unchanged_rtl_files=8,
                unchanged_QSF_SDC_QPF=True, exact_native_control_delta=['run.tcl'],
                manifest_metadata_only_delta=True))
        (project/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
        spec['settings'] = {**manifest['control_sha256'], 'manifest.json': sha(project/'manifest.json')}
        inventory = structural.source_inventory(project, spec)
        (project/'structural-spec.json').write_text(json.dumps(spec, indent=2)+'\n')
        result = dict(status='PASS_source_ready_registered_one_field_plain_fit_r53',
            **structural.identities(spec), source_inventory=inventory,
            design_policy_allows_exploratory_fit=True, exemption='component_sizing_probe',
            normal_source_Quartus_version_PAUSE_resource_budget_deadline_locks_required=True,
            native_AW5_independent_receipt_sha256=NATIVE, actual_AW16_integration_pending=True,
            DA_early_placement_graph_post_fit_only=True, no_fit_launched=True,
            physical_timing_proven=False, production_promotion_allowed=False)
        (project/'structural-source-result.json').write_text(json.dumps(result, indent=2)+'\n')
        archive = output/(role+'-plain-source-v1.tar.gz')
        with tarfile.open(archive, 'x:gz') as stream:
            for path in sorted(project.rglob('*')):
                if path.is_file():
                    stream.add(path, arcname='project/'+path.relative_to(project).as_posix(), recursive=False)
        results[role] = dict(project_root=str(project), manifest_sha256=sha(project/'manifest.json'),
            run_tcl_sha256=sha(project/'run.tcl'), archive_sha256=sha(archive), archive_bytes=archive.stat().st_size,
            source_sha256=manifest['source_sha256'], control_sha256=manifest['control_sha256'])
    result = dict(status='source_ready_F2_matched_plain_projects_no_remote_or_vendor_work', projects=results,
                  normal_dispatch_checks_required=True, actual_AW16_pending=True, promotion_allowed=False)
    (output/'preparation.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
