"""Package source-author's two frozen protocol-age normals on existing Azure.

No source/harness/expectation edits and no new runner or resource authority.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump
from fpga.reference import stream27_r15_application_packet_v3 as operator

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/trackS-r15-protocol-age-native-v1'
ROLES={
 'aw8':('fc9f50001da0de450c74a9e395b8efc5af187eb4b3827696366b247a8338a79c',60,'s4-p16-r15-protocol-age-aw8-normal-q1-v1'),
 'full':('ff28e7db0a1a347ca797317b69167ade0623e340d4d36f357d6d67a92b966128',61,'s4-p16-r15-protocol-age-full-normal-q1-v1'),
}


def prepare(stage):
    from fpga.tools import native_class_package_v4 as package
    from fpga.cloud import host_hours_azure_signed_v1 as meter
    need(stage in ROLES,'R15_AGE_LITERAL_SOURCE_ROLE');pin,count,id=ROLES[stage]
    need(sha((ROOT/operator.RUNNER).read_bytes())==operator.RUNNER_PIN and
         sha((ROOT/operator.STAGER).read_bytes())==operator.STAGER_PIN and
         package.ACTIVE_PROFILES==operator.PROFILES,'R15_AGE_CURRENT_OPERATOR_PINS')
    role=BASE/(stage+'-normal');manifest=role/'manifest.json';m=json.loads(manifest.read_bytes());source=role/'source/fpga'
    need(sha(manifest.read_bytes())==pin and len(m['build']['sv_sources'])==count and
         m['build']['parameters']['EPOCH_AGE_REG']==1 and m['build']['runtime_threads']==1,
         'R15_AGE_FROZEN_AUTHOR_COMPILED_FLAGS')
    need(all(sha((source/n).read_bytes())==h for n,h in m['sources'].items()),'R15_AGE_SOURCE_AUTHOR_CLOSURE')
    out=role/'azure-packet-v1';need(not out.exists(),'R15_AGE_FRESH_PACKET');out.mkdir()
    budget=out/'budget.json';dump(budget,meter.make_budget('gfn16-azure-f16',3715,
      operator.PROVIDER,operator.PROVIDER_PIN,package.source_identity(m),profile_sha256=package.F16_PROFILE_SHA))
    variants=[]
    for profile in operator.PROFILES:
        pair=profile.split('static',1)[1].split('-',1)[0];worker=id.removesuffix('-q1-v1')+'-'+pair+'-v1'
        packet=out/('packet-'+pair);result=package.prepare(manifest,source,profile,worker,'run',packet,budget)
        native=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
          ticket_sha256=result['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),
          worker_id=worker,profile=profile,native_root=native['native_root'],runner=operator.RUNNER,
          runner_sha256=operator.RUNNER_PIN,stager=str(ROOT/operator.STAGER),stager_sha256=operator.STAGER_PIN,
          stager_dependencies=[dict(path=str(ROOT/p),sha256=sha((ROOT/p).read_bytes())) for p in
            ('tools/native_package_v5.py','tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    need(sha((ROOT/operator.RUNNER).read_bytes())==operator.RUNNER_PIN and
         sha((ROOT/operator.STAGER).read_bytes())==operator.STAGER_PIN,'R15_AGE_OPERATOR_STABLE_AFTER_CAPTURE')
    ticket=dict(schema='gfn16-global-ticket-v1',id=id,owner='merged-ntt-model',
      created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P0',kind='sim',needs='verilator',
      tool_identity='azure-f16-verilator5032-gcc13-python312-v1',allowed_hosts=['gfn16-azure-f16'],
      resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8,est_minutes=25,
      promotion_bound=False,test_role='normal',rtl_readiness=m['rtl_readiness'],packages=variants)
    if stage=='full':ticket.update(after=[ROLES['aw8'][2]],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',ticket)
    return dict(id=id,ticket=str(out/'global-ticket.json'),variants=2,status='PREPARED_NOT_SUBMITTED')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=tuple(ROLES),required=True);a=p.parse_args()
    print(json.dumps(prepare(a.stage),indent=2))
