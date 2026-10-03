"""Identity-only author handoff of the original successful application FULL.

Read retained typed/raw artifacts once; no validator import, model execution,
independent verdict, board/HIP simulation, or promotion is performed here.
"""
import json
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha, need, dump

ROOT = Path(__file__).resolve().parents[1]
ID = 's4-p16-c2-r15-shell-application-full-normal-q1-v9'
ROLE = ROOT / 'results/throughput-20260929/trackS-r15-shell-application-native-v4/full-live-monitor-v9-closure-v2'
EVIDENCE = ROOT / 'queue/evidence' / ID
OUT = ROLE / 'owner-outcome-v1.json'
PINS = {
    'role': 'f0a1f13299b4fb3922723acffac3027c4ff6870070a9fa31061300f29d515661',
    'gate': 'f4b1897e1ececd739e479a0fcb0bd3baa34abd840807cb39fca69af3ee205c22',
    'approved': '50a5bda54ded407d1b5261c3c9d2bd698b61d513b3a638aee6541b63c8ea837f',
    'report': '112f013f404f4c800e30bb27a56eebe8c93c0c8ec8a160bbd06ab55ab1c7aafc',
    'stdout': 'e8539319a4846623be5c254970924f4a3b0ba3eb33a7f2560de397f4f2c96d0c',
}


def collect():
    paths = dict(role=ROLE/'manifest.json', gate=EVIDENCE/'gate-receipt.json')
    native = EVIDENCE/'attempt-0/collected/output/native'
    paths.update(approved=native/'approved-manifest.json', report=native/'report.json',
                 stdout=native/'normal-full-r15-application-v4-live-monitor-v9.log')
    need(all(sha(p.read_bytes()) == PINS[k] for k,p in paths.items()), 'R15_APP_V9_EXACT_TERMINAL_PINS')
    role,gate,approved,report = (json.loads(paths[k].read_bytes()) for k in ('role','gate','approved','report'))
    done = json.loads((ROOT/'queue/done'/f'{ID}.json').read_bytes())
    bundle = json.loads((ROLE/'production-bundle.json').read_bytes())
    production = {'rtl/'+n:sha(t.encode()) for n,t in bundle['files'].items()}
    need(len(production) == 70 and len(approved['build']['sv_sources']) == 71 and
         all(approved['sources'].get(n) == h == report['sources'].get(n) for n,h in production.items()) and
         approved['build'] == role['build'], 'R15_APP_V9_LITERAL70_SOURCE_AND_BUILD_ASSOCIATION')
    parameters = approved['build']['parameters']
    build = next(s for s in report['steps'] if s['name'] == 'build')
    need(len(parameters) == 38 and parameters['EPOCH_SEED0'] == parameters['EPOCH_SEED1'] == 0 and
         all(f'-G{k}={v}' in build['command'] for k,v in parameters.items()) and
         report['model_threads'] == 1 and report['compile_workers'] == 2,
         'R15_APP_V9_ACTUAL_PHYSICAL0_0_PARAMETER_ARGV_AND_THREADS')
    need(gate['status'] == done['result']['status'] == 'PASS_expected_contracts' and
         done['dispatch']['invocation'] == 'ef3859292b7b43b0ad9f3bbe24f9fe54' and
         done['result']['properties']['ExecMainStatus'] == '0' and
         done['result']['archive_sha256'] == 'e3e4b067dd9c4300194b072bef7e972dbf170bc2b56b6da0721ff638f189ef3e',
         'R15_APP_V9_SAME_ORIGINAL_INVOCATION_ACTUAL_PASS')
    measured = gate['steps'][0]['validation']['measurements']
    need(measured['actual_live_canonical_trace'] == dict(first=[25324,684788],peer_edges=130,
         publication_edges=[680689,1340153],signed96_words=262144,error=0) and
         measured['squares'] == 4 and measured['interval'] == 8461 and
         measured['independent_reference'] is True and all(s['returncode'] == 0 for s in report['steps']),
         'R15_APP_V9_ACTUAL_ALLWORD_ORACLE_LIVE_PEER_AND_PUBLICATION')
    record = dict(schema='gfn16-r15-application-full-owner-outcome-v1', status='AUTHOR_TYPED_PASS_HANDOFF',
       id=ID, collected_at=done['result']['completed'], invocation=done['dispatch']['invocation'],
       native_start=done['result']['properties']['ExecMainStartTimestamp'],
       native_exit=done['result']['properties']['ExecMainExitTimestamp'],
       pins={k:dict(path=str(p.relative_to(ROOT)),sha256=PINS[k]) for k,p in paths.items()},
       raw_archive_sha256=done['result']['archive_sha256'], production70=production,
       production_bundle_sha256=sha((ROLE/'production-bundle.json').read_bytes()),
       compiled_parameters=parameters, model_threads=1, compile_workers=2, measurements=measured,
       executable_sha256=report['executable_sha256'],
       original_v7_v8_failures_preserved=True, monitor_only_correction=True,
       strict_conjunction_header_reference_program_horizon_unchanged=True,
       scope=gate['steps'][0]['validation']['scope'], independent_review=False,
       vendor_hip_simulated=False, board_pll_metastability_proof=False,
       external_guard_fault_coverage=False, host_GL=False, period_ns=None, promotion_allowed=False)
    need(not OUT.exists(), 'R15_APP_V9_FRESH_ADDITIVE_AUTHOR_RECEIPT')
    dump(OUT,record)
    return dict(path=str(OUT),sha256=sha(OUT.read_bytes()),status=record['status'])


if __name__ == '__main__':print(json.dumps(collect(),indent=2))
