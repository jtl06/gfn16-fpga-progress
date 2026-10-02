"""Read-only ten-chunk source/artifact gate and adjacent-boundary combination.

Uses recorded Linux GMP/native outcomes, never imports GMP or recalculates a
full-N integer reference on the coordinator. This is a dependency gate, not
independent promotion review or an uninterrupted-controller soak certificate.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
CASE = '2730e05de298ecbf5d7125acb7d6859b581b21ed8c84fb1bbfd7d3aaccd007ba'
REFERENCE = 'reference/core27_t5b_soak_v1.py'
REFERENCE_SHA = '636460b5fd8e96696112d53ca792a340f5d2ad1ad843f6f23135877bae6ce962'
GATE = 'tools/native_gate_receipt_v1.py'
GATE_SHA = '131d4e6b9cafd424935094c3ec50ef81d7c2e8024efae6a5d37ce20d0c5a29d3'
CORE = 'rtl/kernel/genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1.sv'
CORE_SHA = '704f7fed433d724dbc8e56c7b725824ec36cce78d6ce8f021307837d2a96b8e7'
CPP = 'rtl/tb/core27_t5b_soak_v1.cpp'
CPP_SHA = 'c4972670a55bbb0c7b039e7a0175ee6918e5a95f3e0dd4a5a96c7dbc7175fab7'
IDS = [f'soak-t5b-aw16-chunk-{i:02d}-q3-v{2 if 3 <= i <= 6 else 1}' if i != 7
       else 'soak-t5b-aw16-chunk-07-cross-burst16-q3-v1' for i in range(10)]
BASE = 'reference/core27_crtmont_soak_v1.py'
BASE_SHA = '8075e2033a01b09b9bbc344b72f23df4ebbc90b8489caadfbd0546e6f3bcfe3a'
PARENT_SHA = '1a1a67980f1744be70c0b089dcdf7e20c4cdd8714cbac26bd5798c28abbcc011'
GCP_RUNTIME = '84fb40c8e6452d4b660d9302e83584dd3c4761aa6219495e57f2df582401cf0b'
AZURE_RUNTIME = '1a5125fa55711298b5412df91105e47aa4c13b6b42ab32191fd8b23696f081f2'
DURATION = 'results/throughput-20260929/soak-t5b-aw16-chunk-activation-v1/duration-admission.json'
DURATION_SHA = 'ccd3602422b315d32806cfae44d6a526efd37a57791d8787135f9dc389373980'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(name, pin):
    path = ROOT / name
    need(path.is_file() and not path.is_symlink() and sha(path) == pin, 'pinned pure gate source')
    spec = importlib.util.spec_from_file_location('_chunk_coverage_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_plan(plan):
    need(plan['case_id'] == CASE and plan['profile']['aw'] == 16 and plan['profile']['n'] == 65536
         and plan['profile']['base'] == 604832956 and plan['lineage'] == 'promoted-t5b'
         and plan['parent_manifest_sha256'] == PARENT_SHA and plan['squares'] == 1000
         and plan['checkpoints'] == list(range(0, 1001, 100))
         and plan['chunks'] == [dict(index=i, start=100*i, end=100*(i+1)) for i in range(10)],
         'fixed AW16 ten-by100 case')
    content = {k: v for k, v in plan.items() if k != 'case_id'}
    need(hashlib.sha256(json.dumps(content, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == CASE,
         'byte-derived exact plan identity')
    return plan


def combine(plan, results):
    # Execute ONLY the pinned pure combination function, not the reference
    # module or its numeric/model/backend definitions/imports.
    need(sha(ROOT / REFERENCE) == REFERENCE_SHA and sha(ROOT / BASE) == BASE_SHA,
         'frozen metadata combination source')
    raw = (ROOT / BASE).read_text()
    begin, end = raw.index('def combine_chunks(plan, results):'), raw.index('\ndef stage_segment(', raw.index('def combine_chunks('))
    namespace = dict(check_plan=check_plan, require=need, re=re, PARENT_SHA=PARENT_SHA)
    exec(compile(raw[begin:end], '[pinned-pure-chunk-combination-only]', 'exec'), namespace)
    return namespace['combine_chunks'](plan, results)


def collect(queue_done, reference_ticket, config=None, registry=None):
    """All-or-fail; pending/missing/failed/wrong-host results never release it."""
    need(not any(k == 'gmpy2' or k.startswith('gmpy2.') for k in sys.modules), 'pure metadata process')
    done, reference_ticket = Path(queue_done).resolve(), Path(reference_ticket).resolve()
    reference = json.loads(reference_ticket.read_text())
    need(reference['id'] == 'soak-t5b-aw16-full-reference-q3-v1'
         and reference['reference_execution_receipt']['status'] == 'PASS_reference_execution_outputs_not_HDL_or_import',
         'actual full reference receipt')
    output = Path(reference['result']['evidence']) / 'output'
    ref_report = output / 'command-report.json'
    need(sha(ref_report) == reference['reference_execution_receipt']['report_sha256'], 'full reference report identity')
    report = json.loads(ref_report.read_text())
    need(report['outputs'] == reference['reference_execution_receipt']['outputs'], 'full output receipt identity')
    for name, row in report['outputs'].items():
        need(sha(output / name) == row['sha256'], 'full reference artifact identity')
    plan_path = output / 'reference/plan.json'
    plan = json.loads(plan_path.read_text())
    gate = load(GATE, GATE_SHA)
    validations, evidence = [], []
    for index, identifier in enumerate(IDS):
        path = done / (identifier + '.json')
        need(path.is_file(), 'missing completed chunk ' + identifier)
        ticket = json.loads(path.read_text())
        if registry is not None:
            need(identifier in registry and registry[identifier] == ticket, 'current exact terminal queue registry')
        props = ticket['result']['properties']
        need(ticket['id'] == identifier and ticket['owner'] == 'soak-chunks'
             and props['Result'] == 'success' and props['ExecMainStatus'] == '0'
             and props['MainPID'] == '0' and props['ControlGroup'] == '', 'actual terminal native chunk')
        package = ticket['package']
        target = 'gfn16-azure-sim-f32' if index == 7 else 'gfn16-pilot-c4d'
        need((package['profile'].startswith('azure-burst16-static8g') if index == 7
              else package['profile'] in ('gcp-c4d-static01-v1', 'gcp-c4d-static23-v1'))
             and sha(package['archive']) == package['sha256'], 'original-host immutable selected package')
        prepared = Path(package['archive']).parent / 'manifest.json'
        need(sha(prepared) == package['manifest_sha256'], 'selected prepared manifest')
        with tarfile.open(package['archive'], 'r:gz') as archive:
            archived = archive.extractfile('manifest.json').read()
        need(hashlib.sha256(archived).hexdigest() == package['manifest_sha256'], 'archive manifest binding')
        manifest = json.loads(archived)
        need(manifest['host'] == target
             and manifest['sources'][CORE] == CORE_SHA and manifest['sources'][CPP] == CPP_SHA
             and manifest['sources'][REFERENCE] == REFERENCE_SHA
             and manifest['build']['parameters'] == {'AW': 16, 'NTT_LANES': 64}
             and manifest['probe']['expected_json'] == dict(context_threads=1, model_threads=1, expected_threads=1)
             and manifest['soak']['case_id'] == CASE and manifest['soak']['segment'] == f'chunk-{index:02d}'
             and len(manifest['steps']) == 1
             and manifest['steps'][0]['validator']['config'] == {'negative': 'none'}, 'exact same T5b chunk contract')
        if config is not None:
            need(manifest['build'] == config['source_model_build']
                 and all(manifest['sources'].get(k) == v for k, v in config['source_model_pins'].items()),
                 'common source/model configuration identity')
        native_report = Path(ticket['result']['evidence']) / 'output/native/report.json'
        native = json.loads(native_report.read_text())
        outcome = gate.validate_result(gate.make_contract(identifier, prepared), native_report, id=identifier)
        link = ticket['dependency_gate']
        if config is not None:
            need(link['functional_sha256'] == config['chunk_identities'][identifier], 'expected machine gate functional identity')
        need(link['status'] == 'PASS_expected_contracts' and sha(link['path']) == link['sha256']
             and json.loads(Path(link['path']).read_text()) == outcome
             and sha(native_report) == ticket['result']['queue_report']['report_sha256'], 'source/artifact gate replay')
        row = native['validations']['soak-normal']
        runtime = AZURE_RUNTIME if index == 7 else GCP_RUNTIME
        need(row['lineage'] == 'promoted-t5b' and row['readbacks'] == 2
             and row['auxiliary_reference_runtime']['status'] == 'passed_exact_auxiliary_reference_runtime'
             and row['auxiliary_reference_runtime']['runtime_manifest_sha256'] ==
                 runtime, 'actual native GMP provenance')
        if index == 7:
            need(manifest['sources']['reference/core27_t5b_soak_cross_runtime_v1.py'] ==
                 '3be94f597e09455a2b9f3f363dfc6a4ac36a240eb26b22a1717e91a072ea1e83'
                 and manifest['sources']['soak/cross-runtime.json'] == AZURE_RUNTIME
                 and row['original_generation_not_rehosted'] is True
                 and row['generation_host'] == 'gfn16-pilot-c4d' and row['replay_host'] == target
                 and row['generation_runtime_manifest_sha256'] == GCP_RUNTIME
                 and row['replay_runtime_manifest_sha256'] == AZURE_RUNTIME, 'explicit qualified two-runtime bridge')
        validations.append(row)
        normal = next(step for step in native['steps'] if step['name'] == 'soak-normal')
        evidence.append(dict(id=identifier, ticket_sha256=sha(path), invocation=props['InvocationID'],
            gate_sha256=link['sha256'], report_sha256=sha(native_report), manifest_sha256=sha(prepared),
            model_seconds=normal['seconds'], model_cpu_seconds=normal['user_seconds'],
            memory_peak_bytes=int(props['MemoryPeak'])))
    combined = combine(plan, validations)
    need(not any(k == 'gmpy2' or k.startswith('gmpy2.') for k in sys.modules), 'combination imported GMP')
    return dict(schema='core27-t5b-ten-chunk-coverage-gate-v1', status='PASS_chunk_continuity_not_continuous_soak',
        case_id=CASE, combination=combined, inputs=evidence, plan_sha256=sha(plan_path),
        full_reference_ticket_sha256=sha(reference_ticket), uninterrupted_1000_square_rtl=False,
        continuous_gate='still_required', promotion_allowed=False, arithmetic_executed=False,
        scope='Recorded native GMP outcomes and exact source/raw artifact replay; not independent promotion review.')


def validate_queue_chunks(config, registry):
    """Fixed dispatcher preclaim ABI; no role/model/GMP imports or hooks."""
    need(type(config) is dict and set(config) == {'schema', 'case_id', 'chunk_identities', 'source_model_build',
        'source_model_pins', 'runtime_by_id', 'reference_ticket'}, 'exact ten-chunk preclaim config')
    need(config['schema'] == 'core27-t5b-ten-chunk-preclaim-config-v1' and config['case_id'] == CASE
         and set(config['chunk_identities']) == set(IDS)
         and all(re.fullmatch('[0-9a-f]{64}', pin) for pin in config['chunk_identities'].values()), 'fixed ten source-bound logical IDs')
    need(config['runtime_by_id'] == {identifier: AZURE_RUNTIME if index == 7 else GCP_RUNTIME
                                     for index, identifier in enumerate(IDS)}, 'explicit per-chunk target runtime identity')
    need(sha(ROOT / DURATION) == DURATION_SHA, 'unchanged source/model baseline proof')
    baseline = json.loads((ROOT / DURATION).read_text())
    wanted = {k: v for k, v in baseline['source_model_pins'].items()
              if k not in ('reference/core27_t5b_soak_native_v1.py', 'soak/runtime.json')}
    wanted[BASE] = BASE_SHA
    need(config['source_model_build'] == baseline['source_model_build'] and config['source_model_pins'] == wanted,
         'complete exact common20-source model pins')
    reference = config['reference_ticket']
    need(type(reference) is dict and set(reference) == {'path', 'sha256'}
         and Path(reference['path']).resolve() == ROOT / 'queue/done/soak-t5b-aw16-full-reference-q3-v1.json'
         and reference['sha256'] == '137f03c43494a7d6744c76dddb4f9a4b0a19a9f6bf796a9022d1a34f285cba16'
         and sha(reference['path']) == reference['sha256'], 'unchanged actual full reference receipt')
    return collect(ROOT / 'queue/done', reference['path'], config, registry)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('queue-done', 'reference-ticket'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(collect(args.queue_done, args.reference_ticket), indent=2))
