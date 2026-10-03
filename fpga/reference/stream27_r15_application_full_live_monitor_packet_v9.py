"""Existing finite Azure API, source-only capture of the corrected live monitor."""
import json
from datetime import datetime, timezone
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump
from fpga.reference import stream27_r15_application_full_live_monitor_v9 as own

ROOT=Path(__file__).resolve().parents[1]
RUNNER='tools/native_class_package_v4.py'
RUNNER_PIN='03ff2d89cb40d36a170ddb239500f611b76b069aa31cf1ae18ac65caf1c6c2c6'
STAGER='tools/native_package_v6.py'
STAGER_PIN='4112106d59052af6cd432356287577f147ff5964e21768bf53960fd52bbf6eed'


def prepare():
    from fpga.tools import native_class_package_v4 as package,global_queue_v1 as queue
    from fpga.cloud import host_hours_azure_signed_v1 as meter
    need(sha((ROOT/RUNNER).read_bytes())==RUNNER_PIN and sha((ROOT/STAGER).read_bytes())==STAGER_PIN,
         'R15_APP_V9_ACTUAL_OPERATOR_PINS')
    manifest=own.OUT/'manifest.json'; m=json.loads(manifest.read_bytes()); source=own.OUT/'source/fpga'
    need(m['build']['runtime_threads']==1 and len(m['build']['sv_sources'])==71 and
         all(sha((source/n).read_bytes())==h for n,h in m['sources'].items()),'R15_APP_V9_FROZEN_SOURCE')
    out=own.OUT/'azure-packet-v1'; need(not out.exists(),'R15_APP_V9_ONE_FRESH_PACKET'); out.mkdir()
    provider=queue.provider_capture_ref();budget=out/'budget.json'
    dump(budget,meter.make_budget('gfn16-azure-f16',3715,str(Path(provider['path']).relative_to(ROOT)),
         provider['sha256'],package.source_identity(m),profile_sha256=package.F16_PROFILE_SHA))
    variants=[]
    for profile in package.ACTIVE_PROFILES:
        pair=profile.split('static',1)[1].split('-',1)[0]
        worker=own.ID.removesuffix('-q1-v9')+'-'+pair+'-v9';packet=out/('packet-'+pair)
        result=package.prepare(manifest,source,profile,worker,'run',packet,budget)
        native=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
          ticket_sha256=result['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),
          worker_id=worker,profile=profile,native_root=native['native_root'],runner=RUNNER,runner_sha256=RUNNER_PIN,
          stager=str(ROOT/STAGER),stager_sha256=STAGER_PIN,stager_dependencies=[dict(path=str(ROOT/p),sha256=sha((ROOT/p).read_bytes()))
            for p in ('tools/native_package_v5.py','tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    ticket=dict(schema='gfn16-global-ticket-v1',id=own.ID,owner='merged-ntt-model',
      created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P0',kind='sim',needs='verilator',
      tool_identity='azure-f16-verilator5032-gcc13-python312-v1',allowed_hosts=['gfn16-azure-f16'],
      resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8,est_minutes=35,
      promotion_bound=False,test_role='normal',rtl_readiness=m['rtl_readiness'],packages=variants,
      after=['s4-p16-c2-r15-shell-application-aw8-normal-q1-v5'],on='PASS_expected_contracts')
    queue.validate(ticket);queue.require_consumer_adoption(ticket);dump(out/'global-ticket.json',ticket)
    return dict(id=own.ID,ticket=str(out/'global-ticket.json'),status='PREPARED_NOT_SUBMITTED')


if __name__=='__main__':print(json.dumps(prepare(),indent=2))
