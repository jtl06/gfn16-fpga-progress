"""ONE source-measured R15 compute1000 on existing AzureFIT finite-long API."""
from datetime import datetime,timezone
import json
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/throughput-20260929/trackS-r15-compute-ownlong-v1'
ID='s4-p16-c2-r15-compute-continuous1000-q1-v1'
PILOT_ID='s4-p16-c2-r15-compute-own100-serial-q1-v1'
PACKAGE='tools/native_long_package_v3.py'
STAGER='tools/native_long_stage_v3.py'
PACKAGE_PIN='87b7692aae52c2db78bbfe534748f969851e5a8674c134ba6b0f2a988043e1fb'
STAGER_PIN='ae137c9dcecba74f762412de6a0ae0dfc34dcef53f79d9d9281198f43969fa9b'
HOST='gfn16-azure-f16'
PROFILE='azure-f16-static1213-v1'
PROVIDER='queue/provider-cost-status/azure-inputs-60581bfa5349c90a15179e93baa18fa7bbc2914b850b6b74d206cd92dc8faf89.json'
PROVIDER_PIN='60581bfa5349c90a15179e93baa18fa7bbc2914b850b6b74d206cd92dc8faf89'


def prepare():
    need(sha((ROOT/PACKAGE).read_bytes())==PACKAGE_PIN and sha((ROOT/STAGER).read_bytes())==STAGER_PIN,
         'R15_LONG_FINAL_TESTED_PINS')
    from fpga.tools import native_long_package_v3 as package
    from fpga.cloud import host_hours_azure_signed_v1 as meter
    raw=BASE/'continuous1000-measured-v1';bound=BASE/'continuous1000-bound-v1';out=BASE/'continuous1000-packet-v1'
    need(not bound.exists() and not out.exists(),'R15_LONG_FRESH_ONE_CAPTURE')
    evidence=ROOT/'queue/evidence'/PILOT_ID/'attempt-0/collected/output/native'
    paths=dict(forecast=raw/'forecast.json',pilot_manifest=evidence/'approved-manifest.json',
      pilot_report=evidence/'report.json',pilot_gate=ROOT/'queue/evidence'/PILOT_ID/'gate-receipt.json')
    package.bind_role(raw/'manifest.json',raw/'source/fpga',paths,bound,host=HOST)
    manifest=bound/'manifest.json';source=bound/'source/fpga';m=json.loads(manifest.read_bytes())
    need(len(m['build']['sv_sources'])==61 and m['build']['parameters'].get('LEAN_BUILD')==1 and
         m['build']['parameters'].get('FIXED_SCHEDULE')==1 and m['build']['parameters'].get('STORAGE_TO_RAM')==1 and
         m['build']['parameters'].get('PROGRESS_WATCHDOG')==1 and m['build']['parameters'].get('DIRECT_COLD')==0 and
         m['build']['parameters'].get('PCIE_SHELL')==0,'R15_LONG_OWN_COMPUTE_ONLY_FLAGS')
    need(sha((ROOT/PROVIDER).read_bytes())==PROVIDER_PIN,'R15_LONG_AUTHENTIC_PROVIDER_PIN')
    out.mkdir();budget=out/'host-hours.json'
    dump(budget,meter.make_budget(HOST,10815,PROVIDER,PROVIDER_PIN,package.source_identity(m),
                                profile_sha256=package.FIT_PROFILE_SHA))
    worker='s4-p16-c2-r15-compute-continuous1000-1213-v1';packet=out/'packet-1213'
    result=package.prepare(manifest,source,PROFILE,worker,'run',packet,budget,compile_workers=2)
    native=json.loads((packet/'ticket.json').read_bytes())
    variant=dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
      ticket_sha256=result['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),
      worker_id=worker,profile=PROFILE,native_root=native['native_root'],runner=PACKAGE,runner_sha256=PACKAGE_PIN,
      stager=str(ROOT/STAGER),stager_sha256=STAGER_PIN,
      stager_dependencies=[dict(path=str(ROOT/p),sha256=sha((ROOT/p).read_bytes())) for p in
        ('tools/native_long_stage_v1.py','tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=10800)
    need(sha((ROOT/PACKAGE).read_bytes())==PACKAGE_PIN and sha((ROOT/STAGER).read_bytes())==STAGER_PIN,
         'R15_LONG_PINS_STABLE_AFTER_CAPTURE')
    logical=dict(schema='gfn16-global-ticket-v1',id=ID,owner='merged-ntt-model',
      created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P0',kind='sim',needs='verilator',
      tool_identity='azure-f16-verilator5032-gcc13-python312-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
      minimum_ram_gib=8,allowed_hosts=[HOST],est_minutes=90,promotion_bound=False,test_role='normal',
      rtl_readiness=m['rtl_readiness'],packages=[variant],after=[PILOT_ID],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',logical)
    return dict(id=ID,ticket=str(out/'global-ticket.json'),ticket_sha256=sha((out/'global-ticket.json').read_bytes()),
      status='PREPARED_NOT_SUBMITTED',variants=1)


if __name__=='__main__':print(json.dumps(prepare(),indent=2))
