"""Reanalyse captured C1 native DA; never executes Quartus or rewrites its proof.

The original gate-v2 result remains FAILED. This additive interpretation proves
its exact metadata-only QSF append and reports native High-rule clearance, not
a new gate-v3 execution, fit permission, crossing coverage or clock success.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

FPGA = Path(__file__).resolve().parents[1]
CAPTURE = FPGA/'results/throughput-20260929/quartus-c1-da-v4-readonly-v1'
REMOTE_RAW_PINS = {
 'native.log': '6563babf21af19b04d8dd98e2faf6240380f242efe9925da3d64ce4de8457f01',
 'specification.json': 'a66568c32fe856b8290fc2030e2064ba75cb9d481cd275cdf424234b215ee4f8',
 'native-execution-context.json': 'ee9695231bf799c101b8331ccfd8d41f8bbeda4f4a84aeebee47d1ee0695a40f',
 'prefit-da-receipt.json': '184d0ca6ef2cf40faefe9719febd37dea524f1a97d7e41f52724e7113b26b5d1',
 'design-assistant-rules.tsv': '998a2b6177c88549ab08f9010c22069638631710a5db2b8f5f6792c0c8122de5',
 'probe.qsf': '12fdd3fa0053f0d36be2a94cd78a1984ff9d7647daf0eaaec22a5f14ae91e96f'}


def need(ok, why):
    if not ok: raise ValueError(why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def analyze(root=CAPTURE):
    root = Path(root)
    raw = {name: (root/name).read_bytes() for name in REMOTE_RAW_PINS}
    need({name: sha(value) for name, value in raw.items()} == REMOTE_RAW_PINS, 'exact readonly remote SHA collection required')
    base = load('qualified_native_parser', FPGA/'tools/quartus_prefit_native_v3.py')
    gate = load('normalized_settings_helper', FPGA/'tools/run_prefit_da_gate_v3.py')
    need(sha(Path(base.__file__).read_bytes()) == gate.PARSER_SHA, 'qualified parser bytes')
    specification = json.loads(raw['specification.json']); execution = json.loads(raw['native-execution-context.json'])
    old = json.loads(raw['prefit-da-receipt.json']); ids = base.identities(specification)
    need(all(execution.get(key) == value and old.get(key) == value for key, value in ids.items()), 'native source/settings/design identities')
    need(specification['scope'] == old['scope'] == 'whole_core' and execution['schema'] == 'quartus-prefit-execution-v1'
        and execution['platform'] == 'Linux' and execution['owner_admission_passed'] is True, 'actual admitted whole-core native DA context')
    need(execution['helper_sha256'] == gate.PARSER_SHA and execution['native_script_sha256'] == gate.SCRIPT_SHA
        and execution['tool_sha256'] == specification['vendor_tool_sha256'] and old['helper_tools_unchanged'] is True, 'actual qualified native helper/tool identity')
    need(set(execution['tool_sha256'].values()) == {gate.CDB_WRAPPER_SHA, gate.CDB_BINARY_SHA}, 'native CDB closure')
    parent = json.loads((FPGA/'results/throughput-20260929/core27-crtmont-c1-8ns-aws-fit-v1/execution-context.json').read_text())
    need(specification['sources'] == {'rtl/'+name: pin for name, pin in parent['source_sha256'].items()}
        and execution['source_before_sha256'] == execution['source_after_sha256'] == specification['sources']
        and len(specification['sources']) == 16, 'exact known C1 RTL unchanged in native execution')
    need(specification['identity']['parameters'] == {'AW':16, 'NTT_LANES':64}
        and specification['identity']['clock_period_ns'] == 8.0 and specification['identity']['seed'] == 1, 'C1 parameter/constraint scope')
    need(execution['returncode'] == old['native_returncode'] == 0 and old['passed'] is False, 'original wrapper failure/native rc0 retained')
    native_raw = {'native.log': REMOTE_RAW_PINS['native.log'], 'native/design-assistant-rules.tsv': REMOTE_RAW_PINS['design-assistant-rules.tsv']}
    need(execution['raw_report_sha256'] == native_raw
        and old['native_execution_context_sha256'] == REMOTE_RAW_PINS['native-execution-context.json']
        and old['log_sha256'] == REMOTE_RAW_PINS['native.log'], 'actual raw native report closure')
    before = execution['database_before_sha256']; after = execution['database_after_sha256']
    need(before and before == after, 'strict compiled DB before/after identity')
    settings_before = execution['settings_before_sha256']; settings_after = execution['settings_after_sha256']
    need(settings_before == specification['settings'] and sha(raw['probe.qsf']) == settings_after['probe.qsf'], 'actual raw QSF before/after identity')
    need(raw['probe.qsf'].endswith(gate.QSF_SUFFIX), 'exact native metadata suffix')
    recovered_before = raw['probe.qsf'][:-len(gate.QSF_SUFFIX)]
    proof = gate.qsf_append_proof(settings_before, settings_after, recovered_before, raw['probe.qsf'], settings_before['probe.qsf'])
    need(proof['transition_accepted'] and proof['appended_during_native'], 'only exact approved metadata append explains settings delta')
    parsed = base.parse_da(raw['native.log'].decode(), raw['design-assistant-rules.tsv'].decode(), ids['design_sha256'], 0)
    need(parsed['complete'] and parsed['passed'], 'actual High-rule diagnostic clearance')
    return dict(schema='quartus-native-da-metadata-reanalysis-v1',
        status='NATIVE_DA_HIGH_CLEARANCE_WRAPPER_FAILED_EXACT_METADATA_APPEND', **ids, scope='whole_core',
        invocation='28c8aa9b13a44803a1d128d28963cbe1', unit='gfn16-azure-crtmont-c1-8ns-v4.service',
        observed_terminal=dict(active_state='failed', main_pid=0, outer_status=3, native_CDB_status=0, exit_utc='2026-10-01T09:06:58Z'),
        actual_native_design_assistant=parsed, source_compiled_db_unchanged=True,
        raw_settings_unchanged=False, qsf_metadata_append_proof=proof,
        raw_settings_before_sha256=settings_before, raw_settings_after_sha256=settings_after,
        original_native_context_unmodified=True, original_gate_result_passed=False,
        interpreted_by_helper_sha256=sha(Path(__file__).read_bytes()),
        raw_report_sha256=REMOTE_RAW_PINS, native_tool_sha256=execution['tool_sha256'],
        native_gate_v3_executed=False, fit_allowed=False, promotion_allowed=False,
        exhaustive_cross_block_coverage=False, whole_core_clock_claim=False,
        limitation='Read-only interpretation of actual gate-v2 CDB execution, not a new helper-v3 run. High-rule clearance only; Medium/Low findings remain in raw native output. r53 diagnostics never gate launch.')


if __name__ == '__main__':
    result = analyze()
    with (CAPTURE/'native-metadata-reanalysis-v1.json').open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps(result, indent=2, allow_nan=False))
