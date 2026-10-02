"""Native pre-fit adapter v2: use CDB for read-only synthesis DA loading.

The Tcl scripts are executable through an admitted Linux owner runner. This
module only constructs argv and parses reports; it never dispatches a cloud job.
Unknown, disabled, missing or truncated checks fail closed. DA high/critical/
fatal findings all block: no count-only inherited-warning exemption is inferred.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

FPGA = Path(__file__).resolve().parents[1]
SCRIPTS = {'da': FPGA/'synthesis/prefit_design_assistant_v1.tcl',
           'postplace': FPGA/'synthesis/postplace_timing_diagnostic_v1.tcl'}
SEVERITY = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3, 'fatal': 4}
VERSION = '26.1.0 Build 110'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode())


def identities(spec):
    source, settings = canonical(spec['sources']), canonical(spec['settings'])
    return {'source_sha256': source, 'settings_sha256': settings,
            'design_sha256': canonical(dict(source_sha256=source,
                settings_sha256=settings, identity=spec['identity']))}


def native_argv(mode, bin_directory, project, revision, output, design_sha256, clock=None):
    """Concrete command for an existing admitted worker, not an execution grant."""
    if mode not in SCRIPTS or not re.fullmatch('[0-9a-f]{64}', design_sha256):
        raise ValueError('mode/design identity')
    paths = [Path(x) for x in (bin_directory, project, output)]
    if not all(p.is_absolute() for p in paths) or not re.fullmatch('[A-Za-z0-9_-]+', revision):
        raise ValueError('absolute worker paths and safe revision required')
    executable = 'quartus_cdb' if mode == 'da' else 'quartus_sta'
    args = [str(paths[0]/executable), '-t', str(SCRIPTS[mode]),
            str(paths[1]), revision, str(paths[2]), design_sha256]
    if mode == 'postplace':
        if not clock or not re.fullmatch('[A-Za-z0-9_]+', clock):
            raise ValueError('explicit selected clock')
        args.append(clock)
    return args


def markers(log, prefix):
    return [line.split('\t')[1:] for line in log.splitlines() if line.startswith(prefix+'\t')]


def native_errors(log, returncode):
    errors = []
    if returncode != 0:
        errors.append('native_returncode_'+str(returncode))
    if VERSION not in log or 'Pro Edition' not in log:
        errors.append('unsupported_or_missing_native_version')
    if re.search(r'^(?:Error(?:\s|\()|ERROR:)', log, re.M | re.I):
        errors.append('native_error_message')
    return errors


def parse_da(log, report, design_sha256, returncode):
    errors = native_errors(log, returncode)
    data = markers(log, 'PREFIT_DA')
    identity = [r for r in data if r[0] == 'IDENTITY']
    complete = [r for r in data if r[0] == 'COMPLETE']
    required = [r[1:] for r in data if r[0] == 'REQUIRED']
    if any(r[0] == 'FAILED' for r in data):
        errors.append('native_design_assistant_failed')
    if len(identity) != 1 or len(identity[0]) != 4 or identity[0][1:3] != [design_sha256, 'synthesized']:
        errors.append('missing_or_wrong_synthesized_design_identity')
    if not required or len({r[0] for r in required}) != len(required) or any(
            len(r) != 2 or r[1] not in ('high', 'critical', 'fatal') for r in required):
        errors.append('incomplete_native_high_severity_inventory')
    if len(complete) != 1 or complete[0] != ['COMPLETE', str(len(required))]:
        errors.append('missing_native_completion')
    title = re.findall(r'^;\s*Design Assistant \(Synthesized\) Results - (\d+) of (\d+) Rules Failed\s*;', report, re.M | re.I)
    if len(title) != 1:
        errors.append('missing_or_ambiguous_synthesis_rule_summary')
    rows = []
    for line in report.splitlines():
        if not re.match(r'^;\s*[A-Z]+-\d+\s+-', line):
            continue
        fields = [x.strip() for x in line.strip().strip(';').split(';')]
        if len(fields) == 1:
            # Native reports repeat the rule name as a detailed-section heading.
            continue
        if len(fields) != 5 or not fields[2].isdigit() or not fields[3].isdigit():
            errors.append('malformed_rule_row'); continue
        rule = fields[0].split(' - ', 1)[0].strip()
        severity = fields[1].lower()
        if severity not in SEVERITY:
            errors.append('unknown_rule_severity_'+rule); continue
        rows.append(dict(rule=rule, severity=severity, violations=int(fields[2]),
                         waived=int(fields[3]), tags=fields[4]))
    by_rule = {r['rule']: r for r in rows}
    if len(rows) != len(by_rule):
        errors.append('duplicate_rule_rows')
    if not rows or (title and (int(title[0][1]) != len(rows) or
            int(title[0][0]) != sum(r['violations'] > r['waived'] for r in rows))):
        errors.append('incomplete_or_inconsistent_rule_table')
    for entry in required:
        if len(entry) != 2:
            continue
        rule, severity = entry
        actual = by_rule.get(rule)
        if actual is None or SEVERITY.get(actual['severity'], -1) < SEVERITY.get(severity, 9):
            errors.append('missing_or_demoted_native_high_rule_'+rule)
    high = [r for r in rows if SEVERITY[r['severity']] >= 2 and (r['violations'] or r['waived'])]
    if any(r['waived'] for r in high):
        errors.append('unreviewed_high_severity_waiver')
    return dict(supported=not any('unsupported' in e for e in errors),
        complete=not errors, phase='post_synthesis', rules_checked=sorted(by_rule),
        high_severity_findings=high, new_high_severity_findings=high,
        high_severity_classification_complete=True, blockers=errors,
        passed=not errors and not high, severity_policy='All High/Critical/Fatal findings block; warnings use rule severity, not compiler-message labels.',
        coverage='Native enabled synthesis-applicable rules only; no claim of full N2 physical categories or cross-block path completeness.')


def parse_timing_paths(report):
    """Read actual Quartus ASCII path slack entries, including negative slack."""
    slacks = [float(x) for x in re.findall(r'^;\s*Slack\s*;\s*([-+]?\d+(?:\.\d+)?)\s*(?:\((?:VIOLATED|MET)\))?\s*;', report, re.M)]
    if not slacks or any(not math.isfinite(x) for x in slacks):
        raise ValueError('missing native path slack entries')
    snapshots = re.findall(r'^Snapshot:\s*\n\s*(\S+)', report, re.M)
    return dict(reported_paths=len(slacks), worst_slack_ns=min(slacks),
                snapshot=snapshots[0] if len(snapshots) == 1 else None)


def parse_postplace(log, reports, design_sha256, clock, period_ns, returncode, scope):
    errors = native_errors(log, returncode)
    data = markers(log, 'POSTPLACE')
    identity = [r for r in data if r[0] == 'IDENTITY']
    if len(identity) != 1 or len(identity[0]) != 5 or identity[0][1:4] != [design_sha256, 'placed', clock]:
        errors.append('wrong_or_missing_placed_clock_identity')
    else:
        try:
            actual_period, expected_period = float(identity[0][4]), float(period_ns)
            if not all(math.isfinite(x) and x > 0 for x in (actual_period, expected_period)) or abs(actual_period-expected_period) > 1e-6:
                errors.append('clock_period_mismatch')
        except ValueError:
            errors.append('invalid_clock_period')
    corners, measurements = {}, []
    for row in data:
        if row[0] == 'CORNER':
            try:
                index, name, hold_only = int(row[1]), bytes.fromhex(row[2]).decode(), row[3]
                if len(row) != 4 or index in corners or hold_only not in ('0', '1'):
                    raise ValueError('corner')
                corners[index] = dict(name=name, hold_only=hold_only == '1')
            except (ValueError, IndexError, UnicodeDecodeError):
                errors.append('malformed_or_duplicate_corner')
        elif row[0] == 'TIMING':
            try:
                index, kind, count, slack, filename = int(row[1]), row[2], int(row[3]), float(row[4]), row[5]
                if len(row) != 6 or kind not in ('setup', 'hold') or not 1 <= count <= 20 or not math.isfinite(slack):
                    raise ValueError('timing')
                raw = parse_timing_paths(reports[filename])
                if raw['snapshot'] != 'placed' or raw['reported_paths'] != count or abs(raw['worst_slack_ns']-slack) > 0.0011:
                    raise ValueError('raw report disagrees with native return value')
                measurements.append(dict(corner=index, type=kind, paths=count, worst_slack_ns=slack, raw_report=filename))
            except (ValueError, KeyError, IndexError):
                errors.append('invalid_or_missing_raw_timing_report')
    expected = {(i, kind) for i, c in corners.items() for kind in ('setup', 'hold') if kind == 'hold' or not c['hold_only']}
    actual = {(m['corner'], m['type']) for m in measurements}
    if not corners or expected != actual or len(actual) != len(measurements):
        errors.append('incomplete_or_duplicate_corner_analysis')
    if [r for r in data if r[0] == 'COMPLETE'] != [['COMPLETE', str(len(corners))]] or any(r[0] == 'FAILED' for r in data):
        errors.append('missing_native_timing_completion')
    return dict(complete=not errors, phase='post_place', scope=scope, corners=corners,
        measurements=measurements, blockers=errors,
        selected_clock_setup_hold_nonnegative=not errors and all(m['worst_slack_ns'] >= 0 for m in measurements),
        routed_clock_qualification=False, whole_core_clock_claim=False,
        cross_block_coverage_complete=False, pulse_width_checked=False,
        limitation='Placed-snapshot selected-clock setup/hold diagnostics only, at the unmodified SDC period. Finite worst20 paths per corner; no signoff, pulse-width, unconstrained-path, reset-release or exhaustive cross-block proof.')


def validate_execution(context, spec, mode, ids, raw, returncode):
    """Validate a caller's admitted execution context; never manufacture one."""
    if context.get('schema') != 'quartus-prefit-execution-v1' or context.get('platform') != 'Linux':
        raise ValueError('admitted Linux native execution context required')
    expected = dict(**ids, tool_sha256=spec['vendor_tool_sha256'],
                    helper_sha256=sha(Path(__file__).read_bytes()),
                    native_script_sha256=sha(SCRIPTS[mode].read_bytes()))
    if any(context.get(k) != v for k, v in expected.items()) or context.get('returncode') != returncode:
        raise ValueError('native execution source/tool/helper identity mismatch')
    for name, expected_map in (('source', spec['sources']), ('settings', spec['settings'])):
        if context.get(name+'_before_sha256') != expected_map or context.get(name+'_after_sha256') != expected_map:
            raise ValueError('native execution input drift: '+name)
    before, after = context.get('database_before_sha256'), context.get('database_after_sha256')
    if not before or before != after or not isinstance(before, dict) or any(
            not re.fullmatch('[0-9a-f]{64}', pin) for pin in before.values()):
        raise ValueError('native DB before/after identity required')
    if context.get('raw_report_sha256') != raw or context.get('owner_admission_passed') is not True:
        raise ValueError('native raw report or owner admission mismatch')


def receipt(root, spec, mode, log_path, report_paths, returncode, execution_path=None):
    root = Path(root).resolve()
    ids = identities(spec)
    paths = [Path(log_path), *map(Path, report_paths)]
    raw = {}
    for path in paths:
        path = path.resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('raw report outside evidence root')
        raw[str(path.relative_to(root))] = sha(path.read_bytes())
    log = Path(log_path).read_text()
    reports = {Path(p).name: Path(p).read_text() for p in report_paths}
    result = dict(schema='quartus-prefit-evidence-v1', **ids, scope=spec['scope'],
        helper_sha256=sha(Path(__file__).read_bytes()), native_script_sha256=sha(SCRIPTS[mode].read_bytes()),
        tool_sha256=spec['vendor_tool_sha256'], raw_report_sha256=raw,
        phase='post_synthesis' if mode == 'da' else 'post_place',
        cross_block_coverage=dict(supported=False, complete=False, observed_crossings=[], uncovered_endpoints=[], unjustified_findings=[]),
        native_execution_identity_verified=False,
        native_execution_context=None, fit_allowed=False, promotion_allowed=False,
        blocker='An admitted Linux execution context with exact source/settings/tool/DB before/after identities is required; parsing does not establish it.')
    if execution_path:
        context_path = Path(execution_path).resolve()
        if not context_path.is_relative_to(root) or not context_path.is_file():
            raise ValueError('bounded native execution context required')
        context_raw = context_path.read_bytes()
        validate_execution(json.loads(context_raw), spec, mode, ids, raw, returncode)
        relative = str(context_path.relative_to(root))
        context_pin = sha(context_raw)
        result['raw_report_sha256'][relative] = context_pin
        result['native_execution_identity_verified'] = True
        result['native_execution_context'] = dict(path=relative, sha256=context_pin)
        result.pop('blocker')
    if mode == 'da':
        if len(reports) != 1:
            raise ValueError('one complete native DA report required')
        result['design_assistant'] = parse_da(log, next(iter(reports.values())), ids['design_sha256'], returncode)
    else:
        result['timing_diagnostic'] = parse_postplace(log, reports, ids['design_sha256'],
            spec['selected_clock'], spec['identity']['clock_period_ns'], returncode, spec['scope'])
        result['design_assistant'] = dict(supported=False, complete=False, rules_checked=[], high_severity_findings=[], new_high_severity_findings=[])
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--mode', choices=SCRIPTS, required=True)
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--report', type=Path, action='append', required=True)
    parser.add_argument('--returncode', type=int, required=True)
    parser.add_argument('--execution-context', type=Path)
    args = parser.parse_args()
    result = receipt(args.root, json.loads(args.spec.read_text()), args.mode,
                     args.log, args.report, args.returncode, args.execution_context)
    print(json.dumps(result, indent=2))
    good = (result.get('design_assistant', {}).get('passed') if args.mode == 'da' else
            result.get('timing_diagnostic', {}).get('selected_clock_setup_hold_nonnegative'))
    raise SystemExit(0 if good and result['native_execution_identity_verified'] else 2)
