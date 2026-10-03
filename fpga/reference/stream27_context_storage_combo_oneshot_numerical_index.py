"""Own R6 promotion index from existing automatic receipts, not native replay."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-oneshot-ownlong-v1'
NORMAL=ROOT/'results/throughput-20260929/trackS-c2-storage-combo-oneshot-native-v1'
IDS=[
 's4-p16-c2-combo-r6-aw8-normal-q1-v1',
 's4-p16-c2-combo-r6-full-normal-q1-v1',
 's4-p16-c2-combo-r6-aw8-wrap-normal-q1-v3',
 's4-p16-c2-combo-r6-aw8-wrap-old-proposal-q1-v2',
 's4-p16-c2-combo-r6-full-wrap-normal-q1-v1',
 's4-p16-c2-combo-r6-own100-serial-q1-v1',
 's4-p16-c2-combo-r6-full-contracts-q1-v1',
 's4-p16-c2-combo-r6-full-early-cache-q1-v1',
 's4-p16-c2-combo-r6-crosstalk-q1-v1',
 's4-p16-c2-combo-r6-continuous1000-q1-v1']
REVIEWS=[
 's4-p16-c2-combo-r6-oneshot-source-independent-v1.json',
 's4-p16-c2-combo-r6-normal-wrap-independent-v1.json',
 's4-p16-c2-combo-r6-normal-wrap-index-binding-independent-v1.json',
 's4-p16-c2-combo-r6-pilot100-cache-independent-v1.json',
 's4-p16-c2-combo-r6-fullcontracts-independent-v1.json',
 's4-p16-c2-combo-r6-crosstalk-independent-v1.json']
def need(ok,why):
    if not ok:raise ValueError('R6_NUMERICAL_INDEX_'+why)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def pin(path):return dict(path=str(Path(path).resolve()),sha256=sha(path))
def load(path):return json.loads(Path(path).read_bytes())
def job(identifier):
    evidence=ROOT/'queue/evidence'/identifier
    gate_path=evidence/'gate-receipt.json';gate=load(gate_path)
    native=evidence/'attempt-0/collected/output/native'
    report_path=native/'report.json';manifest_path=native/'approved-manifest.json'
    report=load(report_path);manifest=load(manifest_path);done=load(ROOT/'queue/done'/(identifier+'.json'))
    need(gate['status']=='PASS_expected_contracts' and gate['id']==identifier,'ACTUAL_GATE')
    need(gate['manifest_sha256']==sha(manifest_path)==report['manifest_sha256'] and
         gate['report_sha256']==sha(report_path) and report['sources']==manifest['sources'],'AUTOMATIC_JOIN')
    need(done['package']['manifest_sha256']==gate['manifest_sha256'] and done['result']['status']=='PASS_expected_contracts','SELECTED_PACKAGE')
    rows=[]
    for step in gate['steps']:
        measurement=(step.get('validation') or {}).get('measurements')
        if measurement is not None:
            measurement=dict(measurement)
            if 'launches' in measurement:
                launches=measurement.pop('launches')
                measurement['launches_count_first_last']=[[len(row),row[0],row[-1]] for row in launches]
        rows.append(dict(name=step['name'],actual_returncode=step['actual_returncode'],expected_returncode=step['expected_returncode'],
            stdout_sha256=step['stdout_sha256'],stderr_sha256=step['stderr_sha256'],typed_validator_sha256=step['typed_validator_sha256'],
            measurements=measurement,stdout_path=str(native/(step['name']+'.log')),stderr_path=str(native/(step['name']+'.stderr.log'))))
    return dict(id=identifier,gate=pin(gate_path),selected_manifest=pin(manifest_path),report=pin(report_path),
        selected_package=done['package'],collected=done['result']['evidence'],collected_archive_sha256=done['result']['archive_sha256'],
        automatic_contract_sha256=gate['contract_sha256'],artifact_inventory_sha256=gate['artifact_inventory_sha256'],
        native_host=report['host'],model_threads=report['model_threads'],compiled_top=manifest['build']['top'],
        compiled_sv_count=len(manifest['build']['sv_sources']),compiled_parameters=manifest['build']['parameters'],
        compiled_sources={name:manifest['sources'][name] for name in manifest['build']['sv_sources']},steps=rows)
def prepare():
    out=BASE/'numerical-index-v1.json';need(not out.exists(),'FRESH_INDEX')
    bundle=load(NORMAL/'full-normal/production-bundle.json');normal=load(NORMAL/'full-normal/manifest.json')
    need(len(bundle['files'])==55 and normal['build']['parameters']==dict(bundle['parameters'],EPOCH_SEED0=65534,EPOCH_SEED1=42),'OWN55_PARAMETERS')
    jobs=[job(identifier) for identifier in IDS]
    long=jobs[-1]['steps'][0]['measurements']
    need(long['squares']==2000 and long['descriptors']==1998 and long['doubles']==1022 and long['reads']==262144 and
         long['initial_resets']==1 and long['initial_load_words']==131072 and long['interval']==8459 and
         long['joint_cycles']==9847766 and long['peer_live_reads']==65536 and long['signed96'] and long['independent_reference'], 'OWN_UNINTERRUPTED1000')
    root=bundle['top']+'.sv';ledger=ROOT/'reference/stream27_c2_storage_combo_oneshot_record_ledger_v1.py'
    need(sha(ledger)=='924b93e04e3aefa1a321cb56d1736d8d24f55d1c70f9b2ae4409a0830f16d2de','OWN_SOURCE_LEDGER')
    value=dict(schema='stream27-c2-r6-numerical-evidence-index-v1',
        status='OWN_NUMERICAL_AND_EXPLICITLY_SCOPED_FAULT_LADDER_PASS_OWN_CLOCK_PENDING',
        created_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),owner='merged-ntt-model',
        production=dict(binder=pin(ROOT/'reference/stream27_context_storage_combo_oneshot_bind.py'),
            captured_bundle=pin(NORMAL/'full-normal/production-bundle.json'),captured_manifest=pin(NORMAL/'full-normal/manifest.json'),
            aw8_bundle=pin(NORMAL/'aw8-normal/production-bundle.json'),production_sv_count=55,native_full_observer_sv_count=1,
            top=bundle['top'],root_sha256=bundle['generated_sha256'][root],all55_generated_sha256=bundle['generated_sha256'],
            source_dependency_pins=bundle['source_sha256'],compiled_parameters=normal['build']['parameters'],geometry=bundle['geometry'],
            rtl_ready_at_utc='2026-10-02T12:52:10Z',source_delta='Only accepted-one-shot/pending second-cold control on exact R5; downstream54 literal.',
            single_context_scope='Single-active context0/context1 runs of SAME C2 RTL, not C1-source pairing.'),
        ledger_producer=dict(**pin(ledger),sample_pair_cycles=16173357856,own_native1000_pair_cycles=9847766,
            selected_period_ns=None,projected_pair_seconds=None,projected_amortized_seconds=None,
            source_calendar_join_pending_core=True,clock_review_pending=True,no_old_period_or_seconds_inherited=True),
        jobs=jobs,existing_closed_review_receipts=[pin(ROOT/'results/throughput-20260929'/name) for name in REVIEWS],
        prior_five_job_index=pin(BASE/'normal-wrap-subset-index-v1.json'),
        scopes=dict(host_timestamp_fastforward_only=True,real_protocol_arithmetic_owner_watchdog_time_not_forced=True,
            billions_of_protocol_edges_claim=False,wrap_table_checks='Actual context/epoch/generation sequence, not independent bank oracle.',
            healthy_accept_only_retirement='Noncolliding legal traces; forced cold/auto collision remains sticky-aborting by literal source authority.',
            forced_cold_auto_collision_native_case_in_index=False,
            fullcache='Actual early matching token observed; later genuine token retained; eventual duplicate-abort/no publication only, NOT immediate origin-age rejection.',
            crosstalk='Native-only output-word bit corruption/comparator detection, all65536 peer words unchanged; NOT production RAM/configuration fault.',
            reset='Own fullCOUNT2/seed65534 ends65535; no epoch-wrap credit from that footer. Actual own1000 crosses epoch16 wrap.',
            representative_full_owner_bits_not_exhaustive=True,no_unknown_or_arbitrary_fault_protection_claim=True,
            no_reload_or_checkpoint_in_own1000=True,full_N_numeric_locally_performed=False,
            old_C2_complete_sample_projections_promotion='HOLD; finite/native/layout evidence preserved.',
            source_frozen_wrap_v2_failure='Preserved; v3 only corrected no-reset pre-FIRST counter expectation; all compiled SV/header bytes exact.'),
        final_promotion=dict(new1000_incremental_independent_review_pending=True,own_physical_clock_pending=True,
            advisor_acceptance_pending=True,promotion_allowed=False,no_board_or_measured_full_sample_PRP_claim=True))
    with out.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    return dict(index=str(out),sha256=sha(out),own_jobs=len(jobs),status=value['status'])
if __name__=='__main__':print(json.dumps(prepare(),indent=2))
