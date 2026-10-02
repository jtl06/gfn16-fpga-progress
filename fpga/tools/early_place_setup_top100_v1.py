"""Finite placed setup-path export parser; macroblock decisions belong to guard.

Completeness means this selected-clock top100 query was captured at the native
setup corners, never exhaustive paths, full timing signoff or missing-register
proof. Native FF endpoints/clock relationships and slack remain separate data.
"""
import importlib.util
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

FPGA = Path(__file__).resolve().parents[1]
SCRIPT = FPGA/'synthesis/early_place_setup_top100_v1.tcl'
BASE_PATH = FPGA/'tools/quartus_prefit_native_v3.py'
if not BASE_PATH.is_file():
    BASE_PATH = Path(__file__).resolve().with_name('quartus_prefit_native_v3.py')
spec = importlib.util.spec_from_file_location('qualified_prefit_base', BASE_PATH)
base = importlib.util.module_from_spec(spec); spec.loader.exec_module(base)


def hextext(value):
    return bytes.fromhex(value).decode('utf-8')


def number(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('nonfinite native timing value')
    return result


def node(fields):
    if len(fields) != 5 or fields[1] not in ('reg', 'port', 'pin', 'net', 'comb', 'none'):
        raise ValueError('native node/cell metadata')
    return dict(name=hextext(fields[0]), type=fields[1], cell_name=hextext(fields[2]),
                cell_type=hextext(fields[3]), primitive_type=hextext(fields[4]))


def native_argv(bin_directory, project, revision, output, design_sha256, clock):
    if not re.fullmatch('[0-9a-f]{64}', design_sha256) or not re.fullmatch('[A-Za-z0-9_]+', clock) or not re.fullmatch('[A-Za-z0-9_-]+', revision):
        raise ValueError('exact design/clock/revision identity')
    if not all(Path(path).is_absolute() for path in (bin_directory, project, output)):
        raise ValueError('absolute worker paths required')
    return [str(Path(bin_directory)/'quartus_sta'), '-t', str(SCRIPT), str(project), revision, str(output), design_sha256, clock]


def parse(log, table, reports, design_sha256, clock, period_ns, returncode):
    blockers = base.native_errors(log, returncode)
    rows = [line.split('\t') for line in table.splitlines()]
    markers = base.markers(log, 'EARLY_SETUP')
    expected_period = number(period_ns)
    if not rows or len(rows[0]) != 6 or rows[0][:3] != ['QUARTUS_EARLY_SETUP_TOP100_V1', design_sha256, 'placed']:
        blockers.append('wrong_or_missing_placed_table_identity')
    else:
        try:
            if hextext(rows[0][3]) != clock or rows[0][5] != 'ns' or abs(number(rows[0][4])-expected_period) > 1e-6 or expected_period <= 0:
                raise ValueError('clock/period/units')
        except (ValueError, UnicodeDecodeError):
            blockers.append('wrong_native_clock_period_or_units')
    identity = [row for row in markers if row[0] == 'IDENTITY']
    if len(identity) != 1 or len(identity[0]) != 6 or identity[0][1:3] != [design_sha256, 'placed'] or identity[0][5] != 'ns':
        blockers.append('missing_native_identity_marker')
    else:
        try:
            if hextext(identity[0][3]) != clock or abs(number(identity[0][4])-expected_period) > 1e-6:
                raise ValueError('clock')
        except (ValueError, UnicodeDecodeError):
            blockers.append('native_clock_marker_mismatch')
    options, corners, queries, paths, points, endpaths, endcorners, complete = [], {}, {}, {}, {}, {}, {}, []
    for fields in rows[1:]:
        try:
            kind = fields[0]
            if kind == 'OPTIONS':
                options.append(fields[1:])
            elif kind == 'CORNER' and len(fields) == 6:
                index = int(fields[1])
                if index in corners or fields[3] not in ('0', '1') or fields[4] != 'ns' or abs(number(fields[5])-expected_period) > 1e-6:
                    raise ValueError('corner')
                corners[index] = dict(name=hextext(fields[2]), hold_only=fields[3] == '1', units='ns', selected_clock_period_ns=number(fields[5]))
            elif kind == 'QUERY' and len(fields) == 6:
                index, requested, count = map(int, fields[1:4])
                if index in queries or requested != 100 or not 1 <= count <= 100 or fields[5] != f'corner-{index}-setup100.rpt':
                    raise ValueError('query')
                queries[index] = dict(requested_paths=requested, returned_paths=count, worst_slack_ns=number(fields[4]), raw_report=fields[5])
            elif kind == 'PATH' and len(fields) == 25:
                key = (int(fields[1]), int(fields[2]))
                if key in paths or fields[21] not in ('0', '1') or fields[22] not in ('0', '1'):
                    raise ValueError('path')
                paths[key] = dict(corner=key[0], rank=key[1], slack_ns=number(fields[3]), source=node(fields[4:9]), destination=node(fields[9:14]),
                    from_clock=hextext(fields[14]), to_clock=hextext(fields[15]), launch_time_ns=number(fields[16]), latch_time_ns=number(fields[17]),
                    clock_relationship_ns=number(fields[18]), setup_start_multicycle=number(fields[19]), setup_end_multicycle=number(fields[20]),
                    from_clock_inverted=fields[21] == '1', to_clock_inverted=fields[22] == '1', native_corner=hextext(fields[23]), arrival_point_count=int(fields[24]))
                if paths[key]['from_clock'] != clock or paths[key]['to_clock'] != clock or paths[key]['arrival_point_count'] < 1:
                    raise ValueError('path clocks/points')
            elif kind == 'POINT' and len(fields) == 10:
                key = tuple(map(int, fields[1:4]))
                if key in points:
                    raise ValueError('duplicate point')
                points[key] = dict(**node(fields[4:9]), native_point_type=hextext(fields[9]))
            elif kind == 'ENDPATH' and len(fields) == 4:
                key = (int(fields[1]), int(fields[2]))
                if key in endpaths:
                    raise ValueError('duplicate path end')
                endpaths[key] = int(fields[3])
            elif kind == 'ENDCORNER' and len(fields) == 3:
                index = int(fields[1])
                if index in endcorners:
                    raise ValueError('duplicate corner end')
                endcorners[index] = int(fields[2])
            elif kind == 'COMPLETE' and len(fields) == 3:
                complete.append(tuple(map(int, fields[1:])))
            else:
                raise ValueError('unknown or malformed native row')
        except (ValueError, UnicodeDecodeError):
            blockers.append('malformed_native_top100_row')
    if options != [['setup', 'npaths:100', 'selected_clock_both_ends', 'points:path_only', 'non_exhaustive']]:
        blockers.append('wrong_native_top100_query_scope')
    setup_corners = {index for index, entry in corners.items() if not entry['hold_only']}
    if not setup_corners or set(queries) != setup_corners or set(endcorners) != setup_corners or sorted(corners) != list(range(len(corners))):
        blockers.append('incomplete_native_setup_corners')
    expected_keys = {(index, rank) for index, query in queries.items() for rank in range(query['returned_paths'])}
    if set(paths) != expected_keys or set(endpaths) != expected_keys:
        blockers.append('incomplete_native_top100_paths')
    expected_points = set()
    for key, path in paths.items():
        count = path['arrival_point_count']
        expected_points.update((key[0], key[1], ordinal) for ordinal in range(count))
        if endpaths.get(key) != count:
            blockers.append('native_path_point_count_mismatch')
        path['arrival_points'] = [points.get((key[0], key[1], ordinal)) for ordinal in range(count)]
    if set(points) != expected_points:
        blockers.append('incomplete_or_extra_native_arrival_points')
    for index, query in queries.items():
        try:
            raw = base.parse_timing_paths(reports[query['raw_report']])
            native_slacks = [path['slack_ns'] for key, path in paths.items() if key[0] == index]
            if raw['snapshot'] != 'placed' or raw['reported_paths'] != query['returned_paths'] or endcorners.get(index) != query['returned_paths'] or not native_slacks or \
                    abs(raw['worst_slack_ns']-query['worst_slack_ns']) > 0.0011 or abs(min(native_slacks)-query['worst_slack_ns']) > 0.0011:
                raise ValueError('raw snapshot/count/slack mismatch')
        except (KeyError, ValueError):
            blockers.append('missing_inconsistent_or_nonplaced_raw_setup_report')
    if complete != [(len(corners), len(setup_corners))] or not rows or rows[-1][0] != 'COMPLETE' or \
            [row for row in markers if row[0] == 'COMPLETE'] != [['COMPLETE', str(len(corners)), str(len(setup_corners))]] or any(row[0] == 'FAILED' for row in markers):
        blockers.append('native_top100_completion_missing')
    if set(reports) != {query['raw_report'] for query in queries.values()}:
        blockers.append('raw_setup_report_set_mismatch')
    if any(row[0] not in ('IDENTITY', 'COMPLETE', 'FAILED') for row in markers):
        blockers.append('unknown_native_top100_marker')
    return dict(schema='quartus-earlyplace-top100-paths-v1', complete=not blockers, blockers=blockers, snapshot='placed', selected_clock=clock,
        selected_clock_period_ns=expected_period, units='ns', corners=corners, queries=queries, paths=[paths[key] for key in sorted(paths)],
        requested_paths_per_setup_corner=100, query_scope='Native selected-clock setup worst100 per supported setup corner, ordered arrival points with path_only detail.',
        native_execution_identity_verified=False, exhaustive_cross_block_coverage=False, routed_clock_qualification=False, whole_core_clock_claim=False, fit_allowed=False, promotion_allowed=False,
        interpretation='Capture only. Macroblock crossing/one-cycle classification and registered-positive-slack semantic conflicts require the source guard/advisor, not invented register-stage counts.')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_execution(context, specification, raw, returncode):
    """Bind actual admitted execution, not just a syntactically plausible TSV."""
    ids = base.identities(specification)
    expected = dict(schema='quartus-earlyplace-execution-v1', platform='Linux', **ids,
        phase='post_place', snapshot='placed', returncode=returncode,
        helper_sha256=sha(Path(__file__)), native_script_sha256=sha(SCRIPT),
        dependency_helper_sha256={'quartus_prefit_native_v3.py': sha(BASE_PATH)},
        tool_sha256=specification['vendor_tool_sha256'], raw_report_sha256=raw,
        selected_clock=specification['selected_clock'], owner_admission_passed=True)
    if any(context.get(name) != value for name, value in expected.items()):
        raise ValueError('native early-placement execution identity mismatch')
    for prefix, identity in (('source', specification['sources']), ('settings', specification['settings'])):
        if context.get(prefix+'_before_sha256') != identity or context.get(prefix+'_after_sha256') != identity:
            raise ValueError('source/settings drift during native placed STA')
    before, after = context.get('database_before_sha256'), context.get('database_after_sha256')
    if not isinstance(before, dict) or not before or before != after or any(
            not re.fullmatch('[0-9a-f]{64}', pin) for pin in before.values()):
        raise ValueError('actual immutable placed compiled snapshot required')
    if not re.fullmatch('[0-9a-f]{64}', context.get('placement_stage_receipt_sha256', '')):
        raise ValueError('source-bound successful plan/place stage ancestry required')


def receipt(root, specification, log_path, table_path, report_paths, returncode, execution_path=None):
    root = Path(root).resolve()
    raw = {}
    for path in [Path(log_path), Path(table_path), *map(Path, report_paths)]:
        if path.resolve() != path or not path.is_relative_to(root) or not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError('regular raw artifact within evidence root required')
        raw[str(path.relative_to(root))] = sha(path)
    ids = base.identities(specification)
    result = parse(Path(log_path).read_text(), Path(table_path).read_text(),
        {Path(path).name: Path(path).read_text() for path in report_paths}, ids['design_sha256'],
        specification['selected_clock'], specification['identity']['clock_period_ns'], returncode)
    result.update(**ids, scope=specification['scope'], raw_report_sha256=raw,
        helper_sha256=sha(Path(__file__)), native_script_sha256=sha(SCRIPT),
        dependency_helper_sha256={'quartus_prefit_native_v3.py': sha(BASE_PATH)},
        tool_sha256=specification['vendor_tool_sha256'], native_execution_context=None)
    if execution_path:
        path = Path(execution_path)
        if path.resolve() != path or not path.is_relative_to(root) or not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError('regular native execution context within evidence root required')
        validate_execution(json.loads(path.read_text()), specification, raw, returncode)
        relative = str(path.relative_to(root)); pin = sha(path)
        result['raw_report_sha256'][relative] = pin
        result['native_execution_context'] = dict(path=relative, sha256=pin)
        result['native_execution_identity_verified'] = True
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--table', type=Path, required=True)
    parser.add_argument('--report', type=Path, action='append', required=True)
    parser.add_argument('--returncode', type=int, required=True)
    parser.add_argument('--execution-context', type=Path)
    args = parser.parse_args()
    result = receipt(args.root, json.loads(args.spec.read_text()), args.log, args.table,
        args.report, args.returncode, args.execution_context)
    print(json.dumps(result, indent=2, allow_nan=False))
    raise SystemExit(0 if result['complete'] and result['native_execution_identity_verified'] else 2)
