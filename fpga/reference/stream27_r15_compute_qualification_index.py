"""Read-only author index of CURRENT60 actual finite contracts; no native replay.

Own separate fixed/all-OFF/protected twins and component watchdogs are scoped
explicitly. Source variants DIRECT/application/AGE are not current60 credit.
"""
import json
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_compute_qualification_index.py'
LEDGER='results/throughput-20260929/trackS-r15-compute-ledger-v1/publication-ledger-native2-100-1000-v3.json'
LEDGER_PIN='1f2778688fb0a9dfa181f1cd9c98d71089196e3f8170aff3588d7f3a3d1082f7'
OUT=ROOT/'results/throughput-20260929/trackS-r15-compute-promotion-v1/numerical-index-v1.json'
JOBS={
 'fixed_aw8':('s4-p16-c2-r15-fixed-aw8-normal-q1-v1','separate protected fixed-only58'),
 'fixed_full':('s4-p16-c2-r15-fixed-full-normal-q1-v1','separate protected fixed-only58'),
 'alloff_aw8':('s4-p16-c2-r15-alloff-aw8-normal-q1-v1','fresh literal all-OFF58 outputs/cycles, not inherited FIELD100 outcome'),
 'alloff_full':('s4-p16-c2-r15-alloff-full-normal-q1-v1','fresh literal all-OFF58 outputs/cycles, not inherited FIELD100 outcome'),
 'compute_aw8':('s4-p16-c2-r15-compute-aw8-normal-q1-v1','own CURRENT60 healthy dense3/14'),
 'compute_full':('s4-p16-c2-r15-compute-full-normal-q1-v1','own CURRENT60 full context-alone/joint+independent reference'),
 'compute_100':('s4-p16-c2-r15-compute-own100-serial-q1-v1','own CURRENT60 Azure serial100 percontext'),
 'compute_1000':('s4-p16-c2-r15-compute-continuous1000-q1-v1','own CURRENT60 Azure serial1000 percontext; original6dcb'),
 'protected_twin_aw8':('s4-p16-c2-r15-compute-protected-twin-aw8-normal-q1-v1','separate60 LEAN0/FIXED+STORAGE+WATCH1 verification twin'),
 'protected_twin_full':('s4-p16-c2-r15-compute-protected-twin-full-normal-q1-v1','separate60 LEAN0/FIXED+STORAGE+WATCH1 verification twin'),
 'watch_normal':('s4-r15-watchdog-normal-q1-v1','component percontext watchdog only; old falseabort proxy reconstruction, not oldNTT replay'),
 'watch_faults':('s4-r15-watchdog-fault-q1-v1','component six live cases/peer-reset sensitivity only, not whole NTT fault immunity'),
 'lean_prp':('s4-r15-compute-lean-prp-normal-q1-v1','own60 N25641091sq/full-exponent8+2sentinels, all signed96 words, no primality/fullsample'),
 'protected_prp':('s4-r15-compute-protected-prp-normal-q1-v1','separate protected60 same finite exponent/reference corpus'),
 'lean_prp_controls':('s4-r15-compute-lean-prp-controls-q1-v2','genuine no-model-quota successor; two host comparator/schedule rc1 sensitivities, not RTL protection'),
 'protected_prp_controls':('s4-r15-compute-protected-prp-controls-q1-v1','separate protected60 host comparator/schedule rc1 sensitivities'),
 'lean_framing_normal':('s4-r15-compute-lean-framing-normal-q1-v1','own60 healthy baseline for external descriptor faults'),
 'lean_framing_faults':('s4-r15-compute-lean-framing-faults-q1-v1','functional external framing/underflow/public masks/sticky/reset only; not removed optional detector immunity'),
 'protected_framing_normal':('s4-r15-compute-protected-framing-normal-q1-v1','separate protected60 healthy framing baseline'),
 'protected_framing_faults':('s4-r15-compute-protected-framing-faults-q1-v1','representative external framing/underflow/public masks/sticky/reset, not arbitrary fault protection'),
 'full_host_wrap':('s4-p16-c2-r15-compute-full-wrap-normal-q1-v2','own60 HOST64 timestamp-only three aliases; real datapath/protocol/watch ticks unchanged, no billions/protocol counter-wrap claim'),
}
FAILURES=('s4-r15-compute-lean-prp-controls-q1-v1','s4-p16-c2-r15-compute-full-wrap-normal-q1-v1')


def actual(identifier,scope):
    dp=ROOT/'queue/done'/(identifier+'.json');d=json.loads(dp.read_bytes());e=ROOT/'queue/evidence'/identifier
    gate=e/'gate-receipt.json';native=e/'attempt-0/collected/output/native'
    report=native/'report.json';manifest=native/'approved-manifest.json'
    g,r,m=[json.loads(p.read_bytes()) for p in (gate,report,manifest)]
    need(d['result']['status']=='PASS_expected_contracts' and g['status']=='PASS_expected_contracts' and
         g['report_sha256']==sha(report.read_bytes()) and g['manifest_sha256']==sha(manifest.read_bytes())==r['manifest_sha256'],
         'R15_INDEX_ACTUAL_OWN_TYPED_IDENTITY:'+identifier)
    archive=e/'attempt-0/evidence.tar.gz';need(sha(archive.read_bytes())==d['result']['archive_sha256'],
                                            'R15_INDEX_ACTUAL_RETAINED_ARCHIVE:'+identifier)
    need(m['build']['runtime_threads']==1 and all(m['sources'][p]==r['sources'][p] for p in m['build']['sv_sources']),
         'R15_INDEX_ACTUAL_COMPILED_SOURCE:'+identifier)
    return dict(id=identifier,scope=scope,gate=dict(path=str(gate.relative_to(ROOT)),sha256=sha(gate.read_bytes())),
      report=dict(path=str(report.relative_to(ROOT)),sha256=sha(report.read_bytes())),
      approved_manifest=dict(path=str(manifest.relative_to(ROOT)),sha256=sha(manifest.read_bytes())),
      archive=dict(path=str(archive.relative_to(ROOT)),sha256=sha(archive.read_bytes())),
      done=dict(path=str(dp.relative_to(ROOT)),sha256=sha(dp.read_bytes())),
      actual_invocation=d['result']['properties']['InvocationID'],
      actual_start_utc=d['result']['properties']['ExecMainStartTimestamp'],
      actual_exit_utc=d['result']['properties']['ExecMainExitTimestamp'],
      compiled_sv_count=len(m['build']['sv_sources']),compiled_parameters=m['build']['parameters'],
      compiled_sv_sha256={p:m['sources'][p] for p in m['build']['sv_sources']},
      cpp_source=m['build']['cpp_source'],cpp_sha256=m['sources'][m['build']['cpp_source']],
      steps=g['steps'],report_artifacts=r['artifacts'],numerical_replay_performed=False)


def index():
    raw=(ROOT/LEDGER).read_bytes();need(sha(raw)==LEDGER_PIN,'R15_INDEX_COMPLETED_OWN_LEDGER')
    l=json.loads(raw);need(l['sample']['pair_completion_cycles']==16177181485 and
       l['selected_period_ns'] is None and not l['native1000_pending'],'R15_INDEX_SAMPLE_LIMITS')
    failures={}
    for id in FAILURES:
        p=ROOT/'queue/done'/(id+'.json');d=json.loads(p.read_bytes())
        need(d['result']['status']=='terminal_failure','R15_INDEX_FAILURE_PRESERVED')
        failures[id]=dict(path=str(p.relative_to(ROOT)),sha256=sha(p.read_bytes()),result=d['result'],
          scope='No-model quota infrastructure only; originals retained, no arithmetic PASS/waiver.')
    return dict(schema='r15-current60-author-numerical-qualification-index-v1',
      status='AUTHOR_OWN_FINITE_NUMERICAL_CONTRACTS_CLOSED_NOT_PROMOTION',
      producer=dict(path=SELF,sha256=sha((ROOT/SELF).read_bytes())),
      production=l['production'],ledger=dict(path=LEDGER,sha256=LEDGER_PIN),
      sample=l['sample'],selected_period_ns=None,projected_pair_seconds=None,projected_amortized_seconds=None,
      promotion_allowed=False,nonauthor_review_pending=True,advisor_pending=True,
      jobs={key:actual(id,scope) for key,(id,scope) in JOBS.items()},preserved_failures=failures,
      scopes=['CURRENT60 lean build; host GL assumed (unimplemented); protected twin is a separately executed source graph.',
        'Own source/captured artifact/compiled parameters/typed raw finite contracts indexed without native numerical replay.',
        'Conditional equalK1911814 healthy timely-feed internal pair16177181485 cycles, model-only sample flags unchanged; not measured fullsample.',
        'Own physical11.728/11.726 and independent source/numerical/physical associations/advisor remain separately required.',
        'No global fault immunity, missing optional detector/hostGL recovery, full-sample PRP, individual latency, real hardware/PrimeGrid or causal isolated gain.',
        'DIRECT65/application70/protocol-AGE60/canonical-FOLD future cohorts have distinct source gates and are not evidence for CURRENT60.'])


if __name__=='__main__':
    need(not OUT.exists(),'R15_INDEX_FRESH_IMMUTABLE_OUTPUT');value=index();OUT.parent.mkdir(parents=True,exist_ok=True);dump(OUT,value)
    print(json.dumps(dict(path=str(OUT),sha256=sha(OUT.read_bytes()),jobs=len(value['jobs']),status=value['status'],period_ns=None)))
