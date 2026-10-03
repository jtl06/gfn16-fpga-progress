"""Exact operator-verified no-model quota successors; no source/expectation edit.

Original failed DONE invocations/archives stay unchanged. This uses only the
existing public infra_retry_of seam, current two admitted Azure profiles and
fresh worker roots; there is one successor per preserved proof.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump
from fpga.reference import stream27_r15_application_packet_v3 as operator

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929'
ROLES={
 'lean-controls':dict(role='trackS-r15-compute-prp-native-v1/lean-controls',
   parent='s4-r15-compute-lean-prp-controls-q1-v1',id='s4-r15-compute-lean-prp-controls-q1-v2',
   after='s4-r15-compute-lean-prp-normal-q1-v1'),
 'full-wrap':dict(role='trackS-r15-compute-wrap-native-v1/full-normal',
   parent='s4-p16-c2-r15-compute-full-wrap-normal-q1-v1',id='s4-p16-c2-r15-compute-full-wrap-normal-q1-v2',
   after='s4-p16-c2-r15-compute-full-normal-q1-v1'),
}


def prepare(mode):
    from fpga.tools import native_class_package_v4 as package
    from fpga.cloud import host_hours_azure_signed_v1 as meter
    need(mode in ROLES,'R15_QUOTA_RETRY_LITERAL_PROOF');r=ROLES[mode]
    need(sha((ROOT/operator.RUNNER).read_bytes())==operator.RUNNER_PIN and
         sha((ROOT/operator.STAGER).read_bytes())==operator.STAGER_PIN and
         package.ACTIVE_PROFILES==operator.PROFILES,'R15_QUOTA_RETRY_ACTUAL_CURRENT_PINS')
    old=json.loads((ROOT/'queue/done'/(r['parent']+'.json')).read_bytes())
    need(old['result']['status']=='terminal_failure' and 'QuotaError' in old['result']['queue_report']['error'],
         'R15_QUOTA_RETRY_PRESERVED_ACTUAL_INFRA_FAILURE')
    role=BASE/r['role'];manifest=role/'manifest.json';m=json.loads(manifest.read_bytes());source=role/'source/fpga'
    need(all(sha((source/n).read_bytes())==h for n,h in m['sources'].items()),'R15_QUOTA_RETRY_SAME_SOURCE_ROLE')
    need(m['build']['runtime_threads']==1,'R15_QUOTA_RETRY_SAME_ONE_THREAD')
    out=role/'quota-retry-packet-v2';need(not out.exists(),'R15_QUOTA_RETRY_ONE_FRESH_PACKET');out.mkdir()
    budget=out/'budget.json';dump(budget,meter.make_budget('gfn16-azure-f16',3715,operator.PROVIDER,
      operator.PROVIDER_PIN,package.source_identity(m),profile_sha256=package.F16_PROFILE_SHA))
    variants=[]
    for profile in operator.PROFILES:
        pair=profile.split('static',1)[1].split('-',1)[0];worker=r['id'].removesuffix('-q1-v2')+'-'+pair+'-v2'
        packet=out/('packet-'+pair);result=package.prepare(manifest,source,profile,worker,'run',packet,budget)
        native=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
          ticket_sha256=result['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),
          worker_id=worker,profile=profile,native_root=native['native_root'],runner=operator.RUNNER,
          runner_sha256=operator.RUNNER_PIN,stager=str(ROOT/operator.STAGER),stager_sha256=operator.STAGER_PIN,
          stager_dependencies=[dict(path=str(ROOT/p),sha256=sha((ROOT/p).read_bytes())) for p in
            ('tools/native_package_v5.py','tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    need(sha((ROOT/operator.RUNNER).read_bytes())==operator.RUNNER_PIN and
         sha((ROOT/operator.STAGER).read_bytes())==operator.STAGER_PIN,'R15_QUOTA_RETRY_PINS_STABLE_AFTER_CAPTURE')
    ticket=dict(schema='gfn16-global-ticket-v1',id=r['id'],owner='merged-ntt-model',
      created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P0',kind='sim',needs='verilator',
      tool_identity='azure-f16-verilator5032-gcc13-python312-v1',allowed_hosts=['gfn16-azure-f16'],
      resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8,est_minutes=25,
      promotion_bound=False,test_role=m['test_role'],rtl_readiness=m['rtl_readiness'],packages=variants,
      after=[r['after']],on='PASS_expected_contracts',infra_retry_of=r['parent'])
    dump(out/'global-ticket.json',ticket)
    return dict(id=r['id'],ticket=str(out/'global-ticket.json'),variants=2,status='PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=tuple(ROLES),required=True);a=p.parse_args()
    print(json.dumps(prepare(a.mode),indent=2))
