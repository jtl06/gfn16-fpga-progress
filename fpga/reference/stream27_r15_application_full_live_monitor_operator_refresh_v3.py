"""Current operator refresh only of the same unsubmitted corrected monitor."""
import json
from pathlib import Path
from fpga.reference.stream27_context_storage_combo_registerederror_native import sha,need,dump
from fpga.reference import stream27_r15_application_full_live_monitor_closure_v2 as own

ROOT=Path(__file__).resolve().parents[1]
RUNNER='tools/native_class_package_v4.py'
RUNNER_PIN='84c314a3b45665bb2a1552991be2b31b1b99adda5b1db3579595ea1bb78a34a5'
STAGER='tools/native_package_v6.py'
STAGER_PIN='f7d6bd0ce894a2e724ba6d8e6c455c4fb87891cd4b8d3f2f6ca20a99fc82e948'


def prepare():
    from fpga.tools import global_queue_v1 as queue,native_azure_variant_refresh_v5 as refresh
    need(not any((ROOT/'queue'/state/(own.ID+'.json')).exists() for state in ('pending','running','done')),
         'R15_APP_V9_MONITOR_STILL_UNSUBMITTED')
    path=own.OUT/'azure-packet-v1/global-ticket.json';original_raw=path.read_bytes();before=json.loads(original_raw)
    need(before['id']==own.ID and sha((ROOT/RUNNER).read_bytes())==RUNNER_PIN and
         sha((ROOT/STAGER).read_bytes())==STAGER_PIN,'R15_APP_V9_FINAL_OPERATOR_AND_SAME_ID')
    target=own.OUT/'operator-refresh-packet-v3';need(not target.exists(),'R15_APP_V9_FRESH_OPERATOR_CAPTURE');target.mkdir()
    provider=queue.provider_capture_ref();variants=[]
    for p in before['packages']:
        pair=p['profile'].split('static',1)[1].split('-',1)[0]
        worker=p['worker_id']+'-op3';out=target/('variant-'+pair)
        result=refresh.repackage_variant(Path(p['archive']).parent,p['profile'],worker,
          Path(provider['path']),provider['sha256'],out)
        packet=out/'packet';native=json.loads((packet/'ticket.json').read_bytes());v=dict(p)
        v.update(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
          ticket_sha256=result['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),
          worker_id=worker,native_root=native['native_root'],runner=RUNNER,runner_sha256=RUNNER_PIN,
          stager=str(ROOT/STAGER),stager_sha256=STAGER_PIN)
        variants.append(v)
    current=dict(before,packages=variants)
    need(queue.expected_identity(current)==queue.expected_identity(before) and path.read_bytes()==original_raw and
         all(current.get(k)==before.get(k) for k in ('id','created','after','on','resources','rtl_readiness')),
         'R15_APP_V9_BODY_CONFIG_DEPENDENCY_OLD_INPUT_LITERAL')
    queue.validate(current)
    dump(target/'global-ticket.json',current)
    dump(target/'refresh-receipt.json',dict(original_input_sha256=sha(original_raw),old_inputs_preserved=True,
       functional_identity=queue.expected_identity(current),submitted=False,
       source_header_reference_parameters_monitor_validator_unchanged=True,provider=provider))
    return dict(id=own.ID,ticket=str(target/'global-ticket.json'),sha256=sha((target/'global-ticket.json').read_bytes()),
                status='PREPARED_HOLD_UNTIL_ACTUAL_FINAL_CONSUMER_READY')


if __name__=='__main__':print(json.dumps(prepare(),indent=2))
