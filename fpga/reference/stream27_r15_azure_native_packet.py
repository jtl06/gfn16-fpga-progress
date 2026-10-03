"""Private packet authoring for R15 AzureFIT normal-first inputs only.

Reuses existing finite class package/stager; no dispatch, cloud operations or
new financial authority. Execution admission stays with the hourly queue.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from .stream27_context_storage_combo_registerederror_native import sha,need,dump

ROOT=Path(__file__).resolve().parents[1]
RUNNER='tools/native_class_package_v4.py'
STAGER='tools/native_package_v6.py'
HOST='gfn16-azure-f16'
PROFILES=('azure-f16-static1213-v1','azure-f16-static1415-v1')
ROLES={
 's4-p16-c2-r15-fixed-aw8-normal-q1-v1':('trackS-r15-fixed-schedule-native-v1/aw8-normal-v2',None),
 's4-p16-c2-r15-fixed-full-normal-q1-v1':('trackS-r15-fixed-schedule-native-v1/full-normal-v2','s4-p16-c2-r15-fixed-aw8-normal-q1-v1'),
 's4-p16-c2-r15-compute-aw8-normal-q1-v1':('trackS-r15-compute-native-v1/aw8-normal-v2',None),
 's4-p16-c2-r15-compute-full-normal-q1-v1':('trackS-r15-compute-native-v1/full-normal-v2','s4-p16-c2-r15-compute-aw8-normal-q1-v1'),
 's4-r15-watchdog-normal-q1-v1':('trackS-r15-watchdog-native-v1/normal-v1',None),
 's4-r15-watchdog-fault-q1-v1':('trackS-r15-watchdog-native-v1/fault-v1','s4-r15-watchdog-normal-q1-v1'),
 's4-p16-c2-r15-alloff-aw8-normal-q1-v1':('trackS-r15-alloff-native-v1/aw8-normal',None),
 's4-p16-c2-r15-alloff-full-normal-q1-v1':('trackS-r15-alloff-native-v1/full-normal','s4-p16-c2-r15-alloff-aw8-normal-q1-v1'),
 's4-p16-c2-r15-compute-own100-serial-q1-v1':('trackS-r15-compute-ownlong-v1/own100-source-v1','s4-p16-c2-r15-compute-full-normal-q1-v1'),
}


def prepare(id,output,provider_input,*,runner_pin,stager_pin):
    from fpga.tools import native_class_package_v4 as package
    from fpga.cloud import host_hours_azure_signed_v1 as meter
    need(id in ROLES,'R15_AZURE_LITERAL_SOURCE_ROLE')
    need(sha((ROOT/RUNNER).read_bytes())==runner_pin and sha((ROOT/STAGER).read_bytes())==stager_pin,
         'R15_AZURE_ACTUAL_FINAL_OPERATOR_PINS')
    role=ROOT/'results/throughput-20260929'/ROLES[id][0]
    manifest_path=role/'manifest.json';manifest=json.loads(manifest_path.read_bytes())
    source=Path(manifest['source_root']);need(source==role/'source/fpga','R15_AZURE_CLOSED_SOURCE_ROOT')
    need(manifest['build'].get('runtime_threads')==1 and manifest['test_role'] in ('normal','deliberate_fault'),
         'R15_AZURE_SERIAL_EXPLICIT_ROLE')
    out=Path(output).resolve();provider=Path(provider_input).resolve()
    need(out.is_relative_to(role) and not out.exists(),'R15_AZURE_FRESH_PRIVATE_PACKET_OUTPUT')
    need(provider.is_relative_to(ROOT) and provider.is_file(),'R15_AZURE_EXISTING_PROVIDER_REF')
    inputs=json.loads(provider.read_bytes())
    need(inputs.get('schema')=='azure-host-hours-provider-inputs-v2' and
         inputs.get('status')=='authenticated_read_only_provider_inputs','R15_AZURE_AUTHENTIC_SNAPSHOT')
    out.mkdir(parents=True)
    budget=meter.make_budget(HOST,3715,str(provider.relative_to(ROOT)),sha(provider.read_bytes()),
                            package.source_identity(manifest),profile_sha256=package.F16_PROFILE_SHA)
    dump(out/'budget.json',budget)
    variants=[]
    for profile in PROFILES:
        suffix=profile.removeprefix('azure-f16-static').removesuffix('-v1')
        worker=id.removesuffix('-q1-v1')+'-'+suffix+'-v1';packet=out/('packet-'+suffix)
        result=package.prepare(manifest_path,source,profile,worker,'run',packet,out/'budget.json')
        native=json.loads((packet/'ticket.json').read_bytes())
        variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
          ticket_sha256=result['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),
          worker_id=worker,profile=profile,native_root=native['native_root'],runner=RUNNER,runner_sha256=runner_pin,
          stager=str(ROOT/STAGER),stager_sha256=stager_pin,
          stager_dependencies=[dict(path=str(ROOT/p),sha256=sha((ROOT/p).read_bytes())) for p in
            ('tools/native_package_v5.py','tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700))
    need(sha((ROOT/RUNNER).read_bytes())==runner_pin and sha((ROOT/STAGER).read_bytes())==stager_pin,
         'R15_AZURE_PIN_STABLE_AFTER_CAPTURE')
    ticket=dict(schema='gfn16-global-ticket-v1',id=id,owner='merged-ntt-model',
      created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P0',kind='sim',needs='verilator',
      tool_identity='azure-f16-verilator5032-gcc13-python312-v1',allowed_hosts=[HOST],
      resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8,
      est_minutes=25,promotion_bound=False,test_role=manifest['test_role'],rtl_readiness=manifest['rtl_readiness'],packages=variants)
    if ROLES[id][1]:ticket.update(after=[ROLES[id][1]],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',ticket)
    return dict(id=id,ticket=str(out/'global-ticket.json'),status='PREPARED_NOT_SUBMITTED',variants=2,
                role_manifest_sha256=sha(manifest_path.read_bytes()),allowed_hosts=[HOST])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--id',choices=tuple(ROLES),required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--provider-input',type=Path,required=True)
    p.add_argument('--runner-pin',required=True);p.add_argument('--stager-pin',required=True)
    args=p.parse_args();print(json.dumps(prepare(args.id,args.output,args.provider_input,
            runner_pin=args.runner_pin,stager_pin=args.stager_pin),indent=2))
