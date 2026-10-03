"""Private source-own packet capture on the existing single AzureFIT pair.

No dispatch/resource/money authority. Historical two-pair inputs remain intact;
the queue owner alone refreshes their unstarted packages through its normal API.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump

ROOT=Path(__file__).resolve().parents[1]
RUNNER='tools/native_class_package_v4.py'
STAGER='tools/native_package_v6.py'
HOST='gfn16-azure-f16'
PROFILE='azure-f16-static1213-v1'
RUNNER_PIN='4e44c36d74d1fa11b0ebf3d256e64b9cd0704a82d0f01c036f7669c3c92ae0d5'
STAGER_PIN='07d6c526e36f26c6fae6536af66ca67d86bcf1191ef7d25965bd9e6d3f243747'
ROLES={
 's4-p16-c2-r15-shell-application-full-normal-q1-v5':('trackS-r15-shell-application-native-v2/full-normal-v5','s4-p16-c2-r15-shell-application-aw8-normal-q1-v3'),
 's4-p16-c2-r15-shell-application-full-normal-q1-v4':('trackS-r15-shell-application-native-v2/full-normal-v4','s4-p16-c2-r15-shell-application-aw8-normal-q1-v3'),
 's4-p16-c2-r15-shell-application-full-normal-q1-v3':('trackS-r15-shell-application-native-v2/full-normal-v3','s4-p16-c2-r15-shell-application-aw8-normal-q1-v3'),
 's4-p16-c2-r15-shell-application-aw8-normal-q1-v3':('trackS-r15-shell-application-native-v2/aw8-normal-v3',None),
 's4-p16-c2-r15-direct-compute-aw8-normal-q1-v2':('trackS-r15-direct-compute-native-v1/aw8-normal-v2',None),
 's4-p16-c2-r15-direct-compute-full-normal-q1-v2':('trackS-r15-direct-compute-native-v1/full-normal-v2','s4-p16-c2-r15-direct-compute-aw8-normal-q1-v2'),
 's4-p16-c2-r15-shell-application-aw8-normal-q1-v2':('trackS-r15-shell-application-native-v2/aw8-normal',None),
 's4-p16-c2-r15-direct-compute-aw8-normal-q1-v1':('trackS-r15-direct-compute-native-v1/aw8-normal',None),
 's4-p16-c2-r15-direct-compute-full-normal-q1-v1':('trackS-r15-direct-compute-native-v1/full-normal','s4-p16-c2-r15-direct-compute-aw8-normal-q1-v1'),
 's4-p16-c2-r15-compute-protected-twin-aw8-normal-q1-v1':('trackS-r15-compute-protected-twin-native-v1/aw8-normal',None),
 's4-p16-c2-r15-compute-protected-twin-full-normal-q1-v1':('trackS-r15-compute-protected-twin-native-v1/full-normal','s4-p16-c2-r15-compute-protected-twin-aw8-normal-q1-v1'),
 's4-r15-compute-lean-prp-normal-q1-v1':('trackS-r15-compute-prp-native-v1/lean-normal','s4-p16-c2-r15-compute-aw8-normal-q1-v1'),
 's4-r15-compute-lean-prp-controls-q1-v1':('trackS-r15-compute-prp-native-v1/lean-controls','s4-r15-compute-lean-prp-normal-q1-v1'),
 's4-r15-compute-protected-prp-normal-q1-v1':('trackS-r15-compute-prp-native-v1/protected-normal','s4-p16-c2-r15-compute-protected-twin-aw8-normal-q1-v1'),
 's4-r15-compute-protected-prp-controls-q1-v1':('trackS-r15-compute-prp-native-v1/protected-controls','s4-r15-compute-protected-prp-normal-q1-v1'),
 's4-p16-c2-r15-compute-full-wrap-normal-q1-v1':('trackS-r15-compute-wrap-native-v1/full-normal','s4-p16-c2-r15-compute-full-normal-q1-v1'),
 's4-r15-compute-lean-framing-normal-q1-v1':('trackS-r15-compute-framing-native-v1/lean-normal','s4-p16-c2-r15-compute-aw8-normal-q1-v1'),
 's4-r15-compute-lean-framing-faults-q1-v1':('trackS-r15-compute-framing-native-v1/lean-faults','s4-r15-compute-lean-framing-normal-q1-v1'),
 's4-r15-compute-protected-framing-normal-q1-v1':('trackS-r15-compute-framing-native-v1/protected-normal','s4-p16-c2-r15-compute-protected-twin-aw8-normal-q1-v1'),
 's4-r15-compute-protected-framing-faults-q1-v1':('trackS-r15-compute-framing-native-v1/protected-faults','s4-r15-compute-protected-framing-normal-q1-v1'),
}


def prepare(id,output,provider_input):
    from fpga.tools import native_class_package_v4 as package
    from fpga.cloud import host_hours_azure_signed_v1 as meter
    need(id in ROLES,'R15_AZURE_V2_LITERAL_SOURCE_ROLE')
    need(sha((ROOT/RUNNER).read_bytes())==RUNNER_PIN and sha((ROOT/STAGER).read_bytes())==STAGER_PIN,
         'R15_AZURE_V2_ACTUAL_OPERATOR_PINS')
    need(package.ACTIVE_PROFILES==(PROFILE,),'R15_AZURE_V2_ONE_ACTIVE_PAIR')
    role=ROOT/'results/throughput-20260929'/ROLES[id][0]
    manifest_path=role/'manifest.json';manifest=json.loads(manifest_path.read_bytes())
    source=Path(manifest['source_root'])
    need(source==role/'source/fpga' and manifest['build']['runtime_threads']==1 and
         manifest['test_role'] in ('normal','deliberate_fault'),'R15_AZURE_V2_CLOSED_SERIAL_ROLE')
    out=Path(output).resolve();provider=Path(provider_input).resolve()
    need(out.is_relative_to(role) and not out.exists(),'R15_AZURE_V2_FRESH_OUTPUT')
    need(provider.is_relative_to(ROOT) and provider.is_file(),'R15_AZURE_V2_EXISTING_PROVIDER_REF')
    inputs=json.loads(provider.read_bytes())
    need(inputs.get('schema')=='azure-host-hours-provider-inputs-v2' and
         inputs.get('status')=='authenticated_read_only_provider_inputs','R15_AZURE_V2_AUTHENTIC_SNAPSHOT')
    out.mkdir(parents=True)
    budget=meter.make_budget(HOST,3715,str(provider.relative_to(ROOT)),sha(provider.read_bytes()),
                            package.source_identity(manifest),profile_sha256=package.F16_PROFILE_SHA)
    dump(out/'budget.json',budget)
    worker=id.removesuffix('-q1-v1')+'-1213-v1';packet=out/'packet-1213'
    result=package.prepare(manifest_path,source,PROFILE,worker,'run',packet,out/'budget.json')
    native=json.loads((packet/'ticket.json').read_bytes())
    variant=dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
      ticket_sha256=result['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),
      worker_id=worker,profile=PROFILE,native_root=native['native_root'],runner=RUNNER,runner_sha256=RUNNER_PIN,
      stager=str(ROOT/STAGER),stager_sha256=STAGER_PIN,
      stager_dependencies=[dict(path=str(ROOT/p),sha256=sha((ROOT/p).read_bytes())) for p in
        ('tools/native_package_v5.py','tools/native_package_v3.py','tools/native_package_v2.py')],max_seconds=3700)
    need(sha((ROOT/RUNNER).read_bytes())==RUNNER_PIN and sha((ROOT/STAGER).read_bytes())==STAGER_PIN,
         'R15_AZURE_V2_PIN_STABLE_AFTER_CAPTURE')
    ticket=dict(schema='gfn16-global-ticket-v1',id=id,owner='merged-ntt-model',
      created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P0',kind='sim',needs='verilator',
      tool_identity='azure-f16-verilator5032-gcc13-python312-v1',allowed_hosts=[HOST],
      resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),minimum_ram_gib=8,
      est_minutes=25,promotion_bound=False,test_role=manifest['test_role'],rtl_readiness=manifest['rtl_readiness'],
      packages=[variant])
    if ROLES[id][1]:ticket.update(after=[ROLES[id][1]],on='PASS_expected_contracts')
    dump(out/'global-ticket.json',ticket)
    return dict(id=id,ticket=str(out/'global-ticket.json'),status='PREPARED_NOT_SUBMITTED',variants=1,
                role_manifest_sha256=sha(manifest_path.read_bytes()),allowed_hosts=[HOST])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--id',choices=tuple(ROLES),required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--provider-input',type=Path,required=True)
    args=p.parse_args();print(json.dumps(prepare(args.id,args.output,args.provider_input),indent=2))
