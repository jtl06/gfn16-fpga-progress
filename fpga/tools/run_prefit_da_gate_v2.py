"""Post-synthesis DA gate for an already admitted fresh Linux fit project.

Usage: python3 run_prefit_da_gate_v2.py PROJECT
The fit owner retains CPU/RAM/slot/HOST-HOURS admission and closes its Quartus
project after synthesis before invoking this gate. A zero exit grants only DA
clearance, not crossing coverage, fit permission, timing or promotion.
"""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys

PARSER_SHA = '33b43d63978e71f055424bcda290ab3ab86ac18057ddece427000225be987f2b'
SCRIPT_SHA = '95c82e6638d6d140b09290fee7c37d41519368e798b638904d53f34d1691cc38'
CDB_WRAPPER_SHA = '06c1bd805bc078d9636015c472e09a054160c405f3f06b7c555e7a4b6f7d3f14'
CDB_BINARY_SHA = '69290861124085f2fa55540bc0f7a5593cd14a5ae6eb035022847ba3fdc3a4ec'
QSF_SUFFIX = b'set_global_assignment -name LAST_QUARTUS_VERSION "26.1.0 Pro Edition"\n'
CONTROLS = {'manifest.json', 'probe.qsf', 'probe.qpf', 'probe.sdc', 'run.tcl'}
MAX_SECONDS = 400


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def regular(path):
    path = Path(path)
    need(path.is_absolute() and path.resolve() == path and path.is_file() and path.stat().st_nlink == 1, 'regular canonical source/evidence required: '+str(path))
    return path.read_bytes()


def write_once(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def verify_inputs(project, context):
    source = context['source_sha256']; control = context['control_sha256']
    need(source and set(control) == CONTROLS, 'closed nonempty RTL and five-control source context required')
    need(all(re.fullmatch(r'[A-Za-z0-9_.-]+\.sv', name) for name in source), 'safe RTL names')
    need({path.name for path in (project/'rtl').iterdir()} == set(source), 'exact RTL closure')
    actual_source = {}
    for name, pin in source.items():
        raw = regular(project/'rtl'/name)
        need(sha(raw) == pin, 'RTL source drift: '+name)
        actual_source['rtl/'+name] = pin
    actual_control = {}
    appended = False
    for name, pin in control.items():
        raw = regular(project/name)
        exact = sha(raw) == pin
        extension = name == 'probe.qsf' and raw.endswith(QSF_SUFFIX) and sha(raw[:-len(QSF_SUFFIX)]) == pin
        need(exact or extension, 'control drift: '+name)
        actual_control[name] = sha(raw)
        appended = appended or (not exact and extension)
    need(actual_control['manifest.json'] == context['manifest_sha256'], 'context/manifest identity mismatch')
    manifest = json.loads(regular(project/'manifest.json'))
    need(manifest['source_sha256'] == source, 'manifest/source context mismatch')
    if 'control_sha256' in manifest:
        need(manifest['control_sha256'] == {name: control[name] for name in manifest['control_sha256']}, 'manifest/control context mismatch')
    parameters = dict(context.get('qsf_parameters', manifest.get('core_parameters', {})))
    need(all(parameters.get(key) == value for key, value in manifest.get('core_parameters', {}).items()), 'manifest parameter correspondence')
    if manifest.get('address_width') is not None:
        need(parameters.get('AW') == manifest['address_width'], 'manifest AW correspondence')
    identity = dict(top=manifest['top'], device=manifest['device'], parameters=parameters,
                    clock_period_ns=manifest['clock_period_ns'], seed=manifest['seed'])
    return actual_source, actual_control, identity, appended


def database(project):
    result = {}
    for directory in ('qdb', 'db', 'incremental_db'):
        for path in sorted((project/directory).rglob('*')):
            need(not path.is_symlink(), 'symlink in compiled DB')
            if path.is_file():
                result[str(path.relative_to(project))] = sha(regular(path))
    need(result, 'nonempty synthesized DB required')
    message = 'qdb/_compiler/probe/_flat/26.1.0/legacy/1/probe.cdb.qmsgdb'
    generated = {}
    if message in result:
        with sqlite3.connect('file:'+str(project/message)+'?mode=ro', uri=True) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            columns = [row[1] for row in connection.execute('PRAGMA table_info(messages)')]
        need(tables == {'messages', 'hierarchy', 'tags', 'tag_types'} and columns ==
             ['sequence_id', 'message_id', 'time', 'source', 'type', 'text', 'flag', 'suppressible', 'file', 'line', 'location'],
             'CDB message output does not match captured native logging schema')
        generated[message] = result.pop(message)
    need(result, 'nonempty compiled inputs after message-output classification')
    return result, generated


def native_environment(environment):
    """Do not inherit Quartus shell initialization sentinels or loader state.

    HOME retains the existing local evaluation/license lookup. PATH/LANG are
    ordinary process basics. No credentials or environment values are logged.
    """
    return {key: environment[key] for key in ('HOME', 'PATH', 'LANG') if key in environment}


def gate(project):
    need(sys.platform == 'linux' and os.geteuid() != 0, 'admitted nonroot Linux worker required')
    project = Path(project)
    need(project.is_absolute() and project.resolve() == project and project.is_dir(), 'canonical admitted project required')
    context_path = project/'execution-context.json'
    context_raw = regular(context_path); context = json.loads(context_raw)
    admission = context.get('azure_admission', {}).get('prefit_gate', {})
    need(admission.get('scope') in ('whole_core', 'component_probe'), 'explicit owner prefit scope required')
    tools_dir = Path(__file__).resolve().parent
    script = tools_dir/'prefit_design_assistant_v2.tcl'; parser = tools_dir/'quartus_prefit_native_v3.py'
    expected_helpers = {str(Path(__file__).resolve()): sha(regular(Path(__file__).resolve())), str(script): SCRIPT_SHA, str(parser): PARSER_SHA}
    need(admission.get('helper_sha256') == expected_helpers, 'exact owner-bound qualified DA helper closure required')
    for name, pin in expected_helpers.items():
        need(sha(regular(Path(name))) == pin, 'qualified DA helper drift: '+name)
    tools = admission.get('tool_sha256', {})
    wrappers = [Path(name) for name in tools if Path(name).name == 'quartus_cdb' and Path(name).parent.name == 'bin']
    need(len(wrappers) == 1, 'one native CDB wrapper required')
    cdb = wrappers[0]; binary = cdb.parent.parent/'linux64/quartus_cdb'
    need(tools == {str(cdb): CDB_WRAPPER_SHA, str(binary): CDB_BINARY_SHA}, 'qualified 26.1 CDB tool closure required')
    for name, pin in tools.items():
        need(sha(Path(name).read_bytes()) == pin, 'native CDB tool drift: '+name)
    source, settings, identity, appended = verify_inputs(project, context)
    specification = dict(scope=admission['scope'], sources=source, settings=settings, identity=identity, vendor_tool_sha256=tools)
    module_spec = importlib.util.spec_from_file_location('qualified_native_da', parser)
    native = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(native)
    # The flat staged package uses the exact qualified script bytes, not the
    # repository's directory layout. Receipt validation binds this actual path.
    native.SCRIPTS['da'] = script
    ids = native.identities(specification)
    output = project/'prefit-da-output'; output.mkdir(exist_ok=False)
    raw_output = output/'native'; raw_output.mkdir()
    write_once(output/'specification.json', specification)
    before, generated_before = database(project)
    command = native.native_argv('da', cdb.parent, project/'probe', 'probe', raw_output, ids['design_sha256'])
    log = output/'native.log'; started = datetime.now(timezone.utc).isoformat()
    write_once(output/'native-start-context.json', dict(schema='quartus-da-gate-start-v1', **ids,
        parent_execution_context_sha256=sha(context_raw), helper_sha256=expected_helpers,
        tool_sha256=tools, source_before_sha256=source, settings_before_sha256=settings,
        database_before_sha256=before, generated_message_before_sha256=generated_before,
        command=command, started_at_utc=started, native_timeout_seconds=MAX_SECONDS))
    with log.open('x') as stream:
        environment = native_environment(os.environ)
        run = subprocess.run(['/usr/bin/timeout', '--kill-after=15s', str(MAX_SECONDS)+'s', *command], cwd=project,
                             stdout=stream, stderr=subprocess.STDOUT, timeout=MAX_SECONDS+20, env=environment)
    after, generated_after = database(project)
    after_source, after_settings, after_identity, _ = verify_inputs(project, context)
    intact = source == after_source and settings == after_settings and identity == after_identity and before == after
    need(regular(context_path) == context_raw, 'parent execution context changed during DA')
    report = raw_output/'design-assistant-rules.tsv'
    raw = {str(path.relative_to(output)): sha(regular(path)) for path in ([log, report] if report.exists() else [log])}
    execution = dict(schema='quartus-prefit-execution-v1', platform='Linux', **ids,
        helper_sha256=PARSER_SHA, native_script_sha256=SCRIPT_SHA, tool_sha256=tools, returncode=run.returncode,
        source_before_sha256=source, source_after_sha256=after_source, settings_before_sha256=settings, settings_after_sha256=after_settings,
        database_before_sha256=before, database_after_sha256=after, raw_report_sha256=raw, owner_admission_passed=True,
        parent_execution_context_sha256=sha(context_raw), command=command, started_at_utc=started,
        finished_at_utc=datetime.now(timezone.utc).isoformat(), generated_message_before_sha256=generated_before,
        generated_message_after_sha256=generated_after, original_tree_unchanged=None,
        preservation_scope='Current fresh synthesized candidate, not preserved original DB. Every compiled input file except exact schema-validated CDB message output is immutable.')
    execution_path = output/'native-execution-context.json'; write_once(execution_path, execution)
    evidence = None
    if report.exists() and intact:
        evidence = native.receipt(output, specification, 'da', log, [report], run.returncode, execution_path)
        write_once(output/'native-evidence.json', evidence)
    helper_tools_intact = all(sha(regular(Path(name))) == pin for name, pin in expected_helpers.items()) and all(sha(Path(name).read_bytes()) == pin for name, pin in tools.items())
    passed = bool(intact and helper_tools_intact and run.returncode == 0 and evidence and evidence['native_execution_identity_verified'] and evidence['design_assistant']['passed'])
    receipt = dict(schema='quartus-da-gate-result-v1', passed=passed, scope=specification['scope'], **ids,
        source_files=len(source), control_files=len(settings), qsf_vendor_append_accepted=appended,
        immutable_source_settings_compiled_db=intact, native_returncode=run.returncode,
        helper_tools_unchanged=helper_tools_intact, parent_execution_context_sha256=sha(context_raw),
        native_evidence=dict(path='native-evidence.json', sha256=sha(regular(output/'native-evidence.json'))) if evidence else None,
        native_execution_context_sha256=sha(regular(execution_path)), log_sha256=sha(regular(log)),
        native_timeout_seconds=MAX_SECONDS, native_environment_policy='Allow HOME/PATH/LANG only; Quartus wrapper initializes its own loader state.', cross_block_coverage_complete=False, fit_allowed=False, promotion_allowed=False,
        limitation='Only synthesis-stage native DA clearance. Caller must independently apply source-bound crossing policy/exemption and fit resource/HOST-HOURS admission.')
    write_once(output/'prefit-da-receipt.json', receipt)
    print(json.dumps(receipt, indent=2))
    return 0 if passed else 2


if __name__ == '__main__':
    need(len(sys.argv) == 2, 'usage: run_prefit_da_gate_v2.py ABSOLUTE_PROJECT')
    raise SystemExit(gate(Path(sys.argv[1])))
