"""Bounded STA capture after admitted new-project plan/place; no compilation.

record-stage PROJECT ABS_STAGE_LOG RETURN_CODE creates successful stage ancestry.
PROJECT runs finite STA on the exact retained placed DB. The owner supplies all
CPU/RAM/HOST-HOURS/physical lock admission. Zero means capture only, not fit or
cross-block policy clearance. Unknown DB mutations fail closed and are retained.
"""
from datetime import datetime, timezone
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

PINS = {
 'early_place_setup_top100_v1.py': '8501f6bc66f1ca8b40683ffd79ef61facf5c00cdc6741a39829bbab01e99ce79',
 'early_place_setup_top100_v1.tcl': '41cce7a61b2331b7ee3607a28aa11e460968520137f5d5559067cd8293ca07bb',
 'staged_placement_qualification_v1.tcl': '4ca357e38794d71d12a6108a5f70462d3b51e0bd3f422a242ec72a3e36eee93e',
 'quartus_prefit_native_v3.py': '33b43d63978e71f055424bcda290ab3ab86ac18057ddece427000225be987f2b',
 'run_prefit_da_gate_v2.py': '64b5da40151f32cc5f3479622119c0f50091844f43b0a47f9b365b3bf3e5e02f',
 'quartus_sta_output_guard_v1.py': 'b1fe9cd4d681820f9cb0a95d69b5cee7096ec1188d6ea45dc3bf6518758d158f'}
STA_WRAPPER_SHA = '06c1bd805bc078d9636015c472e09a054160c405f3f06b7c555e7a4b6f7d3f14'
STA_BINARY_SHA = '2003267399aa7ce6ff34e1a39322107d99b66a7731cc65a1acbf807994c4de1e'
MAX_SECONDS = 400
STAGES = ['synthesized', 'design_assistant', 'planned', 'placed', 'stopped_before_route']


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def validate_stage_log(base, log, returncode):
    expected = [row for stage in STAGES[:-1] for row in [['START', stage], ['COMPLETE', stage]]]
    expected.append(['COMPLETE', STAGES[-1]])
    if base.native_errors(log, returncode) or base.markers(log, 'PLACEMENT_STAGE') != expected:
        raise ValueError('actual complete synthesis/DA/plan/place-only log required')


def setup(project):
    if sys.platform != 'linux' or os.geteuid() == 0:
        raise ValueError('admitted nonroot Linux native worker required')
    project = Path(project)
    if not project.is_absolute() or project.resolve() != project or not project.is_dir():
        raise ValueError('canonical admitted project required')
    tools = Path(__file__).resolve().parent
    if hashlib.sha256((tools/'run_prefit_da_gate_v2.py').read_bytes()).hexdigest() != PINS['run_prefit_da_gate_v2.py']:
        raise ValueError('source guard bytes drift before import')
    guard = load('source_guard', tools/'run_prefit_da_gate_v2.py')
    expected = {str(tools/name): pin for name, pin in PINS.items()}
    expected[str(Path(__file__).resolve())] = guard.sha(guard.regular(Path(__file__).resolve()))
    context_raw = guard.regular(project/'execution-context.json'); context = json.loads(context_raw)
    admission = context.get('azure_admission', {}).get('earlyplace_gate', {})
    guard.need(admission.get('scope') in ('component_probe', 'whole_core'), 'explicit early-placement scope required')
    guard.need(admission.get('helper_sha256') == expected, 'exact owner-bound early-placement helper closure')
    for name, pin in expected.items():
        guard.need(guard.sha(guard.regular(Path(name))) == pin, 'early-placement helper drift: '+name)
    native_tools = admission.get('tool_sha256', {})
    wrappers = [Path(name) for name in native_tools if Path(name).name == 'quartus_sta' and Path(name).parent.name == 'bin']
    guard.need(len(wrappers) == 1, 'one STA wrapper required')
    sta = wrappers[0]
    guard.need(native_tools == {str(sta): STA_WRAPPER_SHA, str(sta.parent.parent/'linux64/quartus_sta'): STA_BINARY_SHA}, 'qualified native STA closure')
    for name, pin in native_tools.items():
        guard.need(guard.sha(Path(name).read_bytes()) == pin, 'native STA drift')
    parser = load('early_place_parser', tools/'early_place_setup_top100_v1.py')
    parser.SCRIPT = tools/'early_place_setup_top100_v1.tcl'
    source, settings, identity, appended = guard.verify_inputs(project, context)
    clock = admission.get('selected_clock')
    guard.need(clock == 'kernel_clk', 'exact admitted selected clock required')
    specification = dict(scope=admission['scope'], sources=source, settings=settings, identity=identity,
        selected_clock=clock, vendor_tool_sha256=native_tools)
    return project, tools, guard, context_raw, expected, native_tools, sta, parser, specification, appended


def record_stage(project, log_path, returncode):
    project, tools, guard, context_raw, helpers, native_tools, sta, parser, specification, appended = setup(project)
    log_path = Path(log_path)
    guard.need(log_path.is_relative_to(project), 'native stage log within new project required')
    log_raw = guard.regular(log_path)
    validate_stage_log(parser.base, log_raw.decode(), returncode)
    db, generated = guard.database(project)
    ids = parser.base.identities(specification)
    value = dict(schema='quartus-placement-stage-v1', **ids, native_returncode=returncode,
        successful_stages=STAGES, source_sha256=specification['sources'], settings_sha256=specification['settings'],
        database_after_sha256=db, generated_message_sha256=generated, helper_sha256=helpers,
        parent_execution_context_sha256=guard.sha(context_raw),
        raw_log=dict(path=str(log_path.relative_to(project)), sha256=guard.sha(log_raw)),
        qsf_vendor_append_accepted=appended, snapshot_retention=True, stopped_before_route=True,
        recorded_at_utc=datetime.now(timezone.utc).isoformat(), fit_allowed=False, promotion_allowed=False)
    guard.write_once(project/'placement-stage-receipt.json', value)
    print(json.dumps(value, indent=2))
    return 0


def gate(project):
    project, tools, guard, context_raw, helpers, native_tools, sta, parser, specification, appended = setup(project)
    stage_raw = guard.regular(project/'placement-stage-receipt.json'); stage = json.loads(stage_raw)
    ids = parser.base.identities(specification)
    guard.need(stage.get('schema') == 'quartus-placement-stage-v1' and all(stage.get(key) == value for key, value in ids.items())
        and stage.get('native_returncode') == 0 and stage.get('successful_stages') == STAGES
        and stage.get('source_sha256') == specification['sources'] and stage.get('settings_sha256') == specification['settings']
        and stage.get('helper_sha256') == helpers and stage.get('parent_execution_context_sha256') == guard.sha(context_raw),
        'exact successful source-bound new placement stage required')
    stage_log = guard.regular(project/stage['raw_log']['path'])
    guard.need(guard.sha(stage_log) == stage['raw_log']['sha256'], 'native placement stage log drift')
    validate_stage_log(parser.base, stage_log.decode(), stage['native_returncode'])
    output = project/'earlyplace-output'; output.mkdir(exist_ok=False)
    native_output = output/'native'; native_output.mkdir()
    before_all, generated_before = guard.database(project)
    guard.need(before_all == stage['database_after_sha256'], 'placed snapshot drift before STA')
    classifier = load('observed_sta_output_guard', tools/'quartus_sta_output_guard_v1.py')
    before, derived_before = classifier.classify(project, before_all)
    guard.write_once(output/'specification.json', specification)
    command = parser.native_argv(sta.parent, project/'probe', 'probe', native_output, ids['design_sha256'], specification['selected_clock'])
    started = datetime.now(timezone.utc).isoformat()
    guard.write_once(output/'native-start-context.json', dict(schema='quartus-earlyplace-start-v1', **ids,
        helper_sha256=helpers, tool_sha256=native_tools, command=command,
        database_before_sha256=before, generated_message_before_sha256=generated_before,
        derived_output_before_sha256=derived_before, placement_stage_receipt_sha256=guard.sha(stage_raw),
        started_at_utc=started, native_timeout_seconds=MAX_SECONDS))
    log = output/'native.log'
    with log.open('x') as stream:
        run = subprocess.run(['/usr/bin/timeout', '--kill-after=15s', f'{MAX_SECONDS}s', *command], cwd=project,
            stdout=stream, stderr=subprocess.STDOUT, timeout=MAX_SECONDS+20, env=guard.native_environment(os.environ))
    after_all, generated_after = guard.database(project)
    guard.write_once(output/'native-db-after.json', dict(database_sha256=after_all, generated_message_sha256=generated_after))
    after, derived_after = classifier.classify(project, after_all)
    after_source, after_settings, after_identity, _ = guard.verify_inputs(project, json.loads(context_raw))
    intact = before == after and specification['sources'] == after_source and specification['settings'] == after_settings and specification['identity'] == after_identity
    helper_tools_intact = all(guard.sha(guard.regular(Path(name))) == pin for name, pin in helpers.items()) and all(guard.sha(Path(name).read_bytes()) == pin for name, pin in native_tools.items())
    guard.need(guard.regular(project/'execution-context.json') == context_raw and guard.regular(project/'placement-stage-receipt.json') == stage_raw, 'parent native ancestry drift')
    table = native_output/'setup-top100.tsv'; reports = sorted(native_output.glob('*.rpt'))
    artifacts = [log, *([table] if table.exists() else []), *reports]
    raw = {str(path.relative_to(output)): guard.sha(guard.regular(path)) for path in artifacts}
    execution = dict(schema='quartus-earlyplace-execution-v1', platform='Linux', **ids,
        phase='post_place', snapshot='placed', returncode=run.returncode,
        helper_sha256=parser.sha(Path(parser.__file__)), native_script_sha256=parser.sha(parser.SCRIPT),
        dependency_helper_sha256={'quartus_prefit_native_v3.py': parser.sha(parser.BASE_PATH)}, tool_sha256=native_tools,
        source_before_sha256=specification['sources'], source_after_sha256=after_source,
        settings_before_sha256=specification['settings'], settings_after_sha256=after_settings,
        database_before_sha256=before, database_after_sha256=after,
        raw_report_sha256=raw, selected_clock=specification['selected_clock'], owner_admission_passed=True,
        placement_stage_receipt_sha256=guard.sha(stage_raw), derived_output_before_sha256=derived_before,
        derived_output_after_sha256=derived_after, generated_message_before_sha256=generated_before,
        generated_message_after_sha256=generated_after, command=command, started_at_utc=started,
        finished_at_utc=datetime.now(timezone.utc).isoformat(),
        compiled_db_changed_paths=sorted(name for name in set(before)|set(after) if before.get(name) != after.get(name)))
    execution_path = output/'native-execution-context.json'; guard.write_once(execution_path, execution)
    parsed = None
    if table.exists():
        parsed = parser.receipt(output, specification, log, table, reports, run.returncode, execution_path if intact and helper_tools_intact else None)
        guard.write_once(output/'native-paths.json', parsed)
    passed = bool(intact and helper_tools_intact and run.returncode == 0 and parsed and parsed['complete'] and parsed['native_execution_identity_verified'])
    value = dict(schema='quartus-earlyplace-gate-result-v1', passed=passed, **ids, scope=specification['scope'],
        snapshot='placed', selected_clock=specification['selected_clock'], native_returncode=run.returncode,
        immutable_source_settings_compiled_db=intact, helper_tools_unchanged=helper_tools_intact,
        parsed_paths_sha256=guard.sha(guard.regular(output/'native-paths.json')) if parsed else None,
        native_execution_context_sha256=guard.sha(guard.regular(execution_path)), log_sha256=guard.sha(guard.regular(log)),
        compiled_db_changed_paths=execution['compiled_db_changed_paths'], native_timeout_seconds=MAX_SECONDS,
        exhaustive_cross_block_coverage=False, fit_allowed=False, promotion_allowed=False,
        limitation='Native finite placed selected-clock top100 capture only. Source/macroblock crossing policy and registered-positive-slack semantic decisions remain separate.')
    guard.write_once(output/'earlyplace-receipt.json', value); print(json.dumps(value, indent=2))
    return 0 if passed else 2


if __name__ == '__main__':
    if len(sys.argv) == 5 and sys.argv[1] == 'record-stage':
        raise SystemExit(record_stage(Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4])))
    if len(sys.argv) != 2:
        raise ValueError('usage: run_early_place_gate_v1.py PROJECT | record-stage PROJECT LOG RC')
    raise SystemExit(gate(Path(sys.argv[1])))
