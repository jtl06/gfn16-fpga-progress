"""Read-only controller-dossier adapter; writes only a fresh owner receipt.

Reuse pinned v1 native data-cone parsing and qualified A1 fanout/congestion
tables. No remote/native operation or mutation of immutable controller evidence.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
V1_PIN = '79a82a183e8fb683eca94f8acae35fb0a7fb3fe7f744bd0e9348ad3b56226ad6'
A1_PIN = '8bd932e1c41c986b30217f941ad378227888cec093dfe8dec1aeb0e2345789c8'


def need(ok,why):
    if not ok: raise ValueError(why)


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


need(sha(HERE/'plain_fit_path_ledger_v1.py') == V1_PIN,'frozen ledger v1 before import')
module_spec = importlib.util.spec_from_file_location('_plain_ledger_v1',HERE/'plain_fit_path_ledger_v1.py')
v1 = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(v1)
need(sha(HERE.parent/'cloud/aws_postfit_crtmont_a1_v1.py') == A1_PIN,'qualified native table parser before import')
sys.path.insert(0,str(HERE.parent))
from cloud import aws_postfit_crtmont_a1_v1 as tables


def family(node):
    if '.engine|child|generated|' in node: return 'NTT root recurrence/update'
    if '.crt|' in node: return 'CRT'
    if '.engine|child|' in node and 'bf_in_valid' in node: return 'NTT admission/valid control'
    if '.engine|child|' in node: return 'NTT engine'
    if node.startswith('field_lane['): return 'field-lane control'
    return v1.family(node)


def classify(result):
    counts = {}
    for row in result['paths']:
        row['source_family'] = family(row['source']); row['destination_family'] = family(row['destination'])
        for value in row['observed_data_cone']: value['family'] = family(value['element'])
        row['observed_data_cone_families'] = list(dict.fromkeys(value['family'] for value in row['observed_data_cone']))
        label = row['source_family']+' -> '+row['destination_family']; counts[label] = counts.get(label,0)+1
    result['endpoint_family_counts'] = counts
    return result


def collect(dossier,receipt_pin):
    dossier = dossier.resolve(); receipt_path = dossier/'receipt.json'
    need(sha(receipt_path) == receipt_pin,'exact immutable controller terminal receipt')
    receipt = json.loads(receipt_path.read_text()); root = dossier/'evidence'
    need(receipt['native_job_succeeded'] and receipt['collection_completed'] and receipt['terminal_proven'] and not receipt['findings'],
         'actual successful source-bound terminal native fit (not timing pass)')
    inventory = root/'collection/collection-inventory-v1.json'
    need(sha(inventory) == receipt['inventory_sha256'] and sha(dossier/'native-reports.tar.gz') == receipt['archive']['sha256'],
         'immutable native inventory/archive identity')
    files = json.loads(inventory.read_text())['files']
    names = ['project/manifest.json','project/output_files/probe.sta.rpt','project/output_files/probe.fit.rpt',
             'project/output_files/probe.fit.route.rpt','project/output_files/probe.fit.place.rpt','project/probe.sdc']
    for name in names: need(sha(root/name) == files[name]['sha256'],'selected actual report/control identity: '+name)
    manifest = json.loads((root/'project/manifest.json').read_text()); sta = (root/'project/output_files/probe.sta.rpt').read_text()
    return dict(schema='plain-fit-path-ledger-v2',scope=receipt['scope'],top=manifest['top'],
        target_period_ns=manifest['clock_period_ns'],seed=manifest['seed'],native_collection_receipt_sha256=receipt_pin,
        original_invocation_id=receipt['invocation_id'],source_manifest_sha256=files['project/manifest.json']['sha256'],
        selected_report_sha256={name:files[name]['sha256'] for name in names},parser_sha256=sha(Path(__file__).resolve()),
        dependency_helper_sha256={'plain_fit_path_ledger_v1.py':V1_PIN,'aws_postfit_crtmont_a1_v1.py':A1_PIN},
        setup=classify(v1.parse(sta,'setup',manifest['clock_period_ns'])),hold=classify(v1.parse(sta,'hold',manifest['clock_period_ns'])),
        native_high_fanout=tables.fanout((root/'project/output_files/probe.fit.rpt').read_text()),
        native_wire_demand=tables.congestion((root/'project/output_files/probe.fit.route.rpt').read_text()),
        native_resources=tables.resources((root/'project/output_files/probe.fit.place.rpt').read_text()),
        generated_at_utc=datetime.now(timezone.utc).isoformat(),promotion_allowed=False,exhaustive_graph_coverage=False,
        registered_stage_count_proof=False,audited_clock=False,
        limitation='Read-only source-bound final MCMM finite samples and native fanout/demand tables. Regional demand is not wire occupancy. Coarse cone labels are triage, not missing-register proof. Printed percentages omit negative delays. Virtual I/O/reset-release/full-size PRP remain outside sign-off; no fit rerun or independent promotion review.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dossier',type=Path); parser.add_argument('--receipt-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True); args = parser.parse_args()
    need(args.output.is_absolute() and args.output.resolve() == args.output and not args.output.exists() and
         not args.output.is_relative_to(args.dossier.resolve()),'fresh owner output outside immutable dossier')
    result = collect(args.dossier,args.receipt_sha256); args.output.mkdir(parents=True)
    with (args.output/'path-ledger-v2.json').open('x') as stream:
        json.dump(result,stream,indent=2,allow_nan=False); stream.write('\n')
    print(json.dumps(dict(setup=result['setup']['endpoint_family_counts'],high_fanout=result['native_high_fanout']['top20'][:3],
        wire_demand=result['native_wire_demand']['regional_peaks']),indent=2))
