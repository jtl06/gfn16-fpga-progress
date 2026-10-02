"""Exact C1/G4 constraint-only topology justification; never grants fit or clock."""
import hashlib
import json
from pathlib import Path

PARENT = '93af1da3453947be920e73ad3f9ead17da3a8249966c7d7db5353f4502f6ece3'
AUDIT = 'fe70997804d364f0b79058cc00f233e6be01552226568f31aca42bf2bae5708e'
PRIOR_C1 = '5691177fed3b4b7b03628c802e962d539f70ccc9c42fa38d6e27e004761262e9'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def assess(project):
    project = Path(project).resolve()
    parent_path = project/'evidence/parent-manifest.json'
    audit_path = project/'evidence/parent-sta-review.json'
    prior_path = project/'evidence/prior-c1-review.json'
    for path, pin in ((parent_path, PARENT), (audit_path, AUDIT), (prior_path, PRIOR_C1)):
        require(digest(path) == pin, 'exact fitted/audited ancestor evidence')
    parent = json.loads(parent_path.read_text())
    candidate = json.loads((project/'manifest.json').read_text())
    sources = parent['source_sha256']
    require(len(sources) == 16 and candidate['source_sha256'] == sources, 'exact sixteen unchanged RTL files')
    require({p.name for p in (project/'rtl').iterdir()} == set(sources), 'no additional RTL inputs')
    for name, pin in sources.items():
        require(digest(project/'rtl'/name) == pin, 'RTL byte drift: '+name)
    for name in ('probe.qsf', 'probe.qpf'):
        require(digest(project/name) == parent['control_sha256'][name], 'exact parent four-worker QSF/QPF')
    parent_sdc = project/'evidence/parent-probe.sdc'
    require(digest(parent_sdc) == parent['control_sha256']['probe.sdc'], 'exact parent SDC evidence')
    # Known C1 textual delta only; no new false paths or functional settings.
    expected_sdc = parent_sdc.read_text().replace('Exploratory 10 ns clock', 'Exploratory 8 ns clock').replace('-period 10 ', '-period 8 ')
    require(expected_sdc != parent_sdc.read_text() and (project/'probe.sdc').read_text() == expected_sdc, 'only exact 10-to-8ns SDC change')
    for key in ('device', 'top', 'address_width', 'core_parameters', 'arithmetic_profile', 'core_field_basis', 'seed'):
        require(candidate[key] == parent[key], 'unchanged functional identity: '+key)
    require(candidate['clock_period_ns'] == 8 and candidate['compile_processors'] == 4, 'exact 8ns/four-worker C1 target')
    return dict(schema='prefit-c1-constraint-only-v1', status='PASS_exact_C1_inherited_topology_justification',
        checker_sha256=digest(__file__), manifest_sha256=digest(project/'manifest.json'),
        sources=sources, settings={name: digest(project/name) for name in ('probe.qsf','probe.qpf','probe.sdc','run.tcl')},
        ancestor_evidence_sha256={'parent_manifest': PARENT, 'parent_clock_audit': AUDIT, 'prior_C1_fit_review': PRIOR_C1},
        justification='Exact already-fitted G4/crtmont RTL and functional settings; only 10ns to 8ns target. Inherited topology is explicitly justified for provisional constraint-only exploration under adopted r44/r45, not proven newly pipelined.',
        synthesis_allowed=True, crossing_requirement_satisfied_by_explicit_justification=True,
        native_crossing_coverage_complete=False, native_design_assistant_pass=False,
        fit_allowed=False, promotion_allowed=False, physical_timing_proven=False,
        remaining_gate='Pinned runtime adapter must validate its exact run.tcl/helper/tool/source closure and stop after synthesis unless candidate-native Design Assistant passes; budget/resource admission remains separate.',
        limits='No arbitrary Tcl safety claim, changed-RTL exception, 125MHz claim, or whole-core crossing completeness.')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path)
    args = parser.parse_args()
    print(json.dumps(assess(args.project), indent=2))
