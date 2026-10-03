"""Unaccepted application FULL recapture on the operator's admitted two pairs.

No RTL/role/header/expectation/resource authority; historical one-pair package
is retained and the one logical FULL normal still depends on own AW8-v3.
"""
from datetime import datetime,timezone
import json
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump

ROOT=Path(__file__).resolve().parents[1]
ID='s4-p16-c2-r15-shell-application-full-normal-q1-v5'
AW8='s4-p16-c2-r15-shell-application-aw8-normal-q1-v3'
ROLE=ROOT/'results/throughput-20260929/trackS-r15-shell-application-native-v2/full-normal-v5'
RUNNER='tools/native_class_package_v4.py'
STAGER='tools/native_package_v6.py'
RUNNER_PIN='c2eb7148d89db89caec767ae876d399ef3f367562f1f1e177a100acf753d6e8c'
STAGER_PIN='878138db412a83482b7959ae48fbd4e3199aad4a5edae77e79cd08c6a4bc8209'
PROVIDER='queue/provider-cost-status/azure-inputs-60581bfa5349c90a15179e93baa18fa7bbc2914b850b6b74d206cd92dc8faf89.json'
PROVIDER_PIN='60581bfa5349c90a15179e93baa18fa7bbc2914b850b6b74d206cd92dc8faf89'
PROFILES=('azure-f16-static1213-v1','azure-f16-static1415-v1')


def prepare():
    from fpga.tools import native_class_package_v4 as package
    from fpga.cloud import host_hours_azure_signed_v1 as meter
    need(sha((ROOT/RUNNER).read_bytes())==RUNNER_PIN and sha((ROOT/STAGER).read_bytes())==STAGER_PIN and
         package.ACTIVE_PROFILES==PROFILES,'R15_APPLICATION_ACTUAL_OPERATOR_TWO_PAIR_PINS')
    manifest=ROLE/'manifest.json';m=json.loads(manifest.read_bytes());source=ROLE/'source/fpga'
    need(sha(manifest.read_bytes())=='08bbe0aa038d117fd86a30ce72e54749ef129323417173dfde8e7d1e2838edc0' and
         m['build']['parameters']['EPOCH_SEED0']==m['build']['parameters']['EPOCH_SEED1']==0 and
         len(m['build']['sv_sources'])==71,'R15_APPLICATION_UNCHANGED_FULL70_PHYSICAL_EPOCHS')
    need(sha((ROOT/PROVIDER).read_bytes())==PROVIDER_PIN,'R15_APPLICATION_AUTHENTIC_PROVIDER_CAPTURE')
    out=ROLE/'azure-packet-v2';need(not out.exists(),'R15_APPLICATION_ADDITIVE_CURRENT_PACKAGE');out.mkdir()
    budget=out/'budget.json';dump(budget,meter.make_budget('gfn16-azure-f16',3715,PROVIDER,PROVIDER_PIN,
      package.source_identity(m),profile_sha256=package.F16_PROFILE_SHA))
    variants=[]
    for profile in PROFILES:
        pair=profile.split('static',1)[1].split('-',1)[0]
        worker='s4-p16-c2-r15-shell-application-full-normal-'+pair+'-v5';packet=out/('packet-'+pair)
        result=package.prepare(manifest,source,profile,worker,'run',packet,budget)
        native=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
          ticket_sha256=result['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),
          worker_id=worker,profile=profile,native_root=native['native_root'],runner=RUNNER,runner_sha256=RUNNER_PIN,
          stager=str(ROOT/STAGER),stager_sha256=STAGER_PIN,
          stager_dependencies=[dict(path=str(ROOT/p),sha256=sha((ROOT/p).read_bytes())) for p in
            ('tools/native_package_v5.py','tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    need(sha((ROOT/RUNNER).read_bytes())==RUNNER_PIN and sha((ROOT/STAGER).read_bytes())==STAGER_PIN,
         'R15_APPLICATION_CURRENT_PINS_STABLE_AFTER_CAPTURE')
    ticket=dict(schema='gfn16-global-ticket-v1',id=ID,owner='merged-ntt-model',
      created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P0',kind='sim',needs='verilator',
      tool_identity='azure-f16-verilator5032-gcc13-python312-v1',allowed_hosts=['gfn16-azure-f16'],
      resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8,est_minutes=35,
      promotion_bound=False,test_role='normal',rtl_readiness=m['rtl_readiness'],packages=variants,
      after=[AW8],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',ticket)
    return dict(id=ID,ticket=str(out/'global-ticket.json'),variants=2,status='PREPARED_NOT_SUBMITTED')


if __name__=='__main__':print(json.dumps(prepare(),indent=2))
