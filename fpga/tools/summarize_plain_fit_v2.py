"""Add native LAB occupancy to frozen scoped fit interpretation, not ALM proxy."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re

PARENT = Path(__file__).resolve().with_name('summarize_plain_fit_v1.py')
PARENT_SHA = '95869cfe75c7f3f24f257d8b9ceeefbf80cff1118f08d9ae6aede9e342f0b6c1'


def labs(text):
    rows = re.findall(r'^;\s*Total LABs:\s*partially or completely used\s*;\s*([0-9,]+)\s*/\s*([0-9,]+)\s*;\s*([^;]+?)\s*;', text, re.M)
    if not rows:
        return dict(available=False, partially_or_completely_used=None, device_total=None,
            native_reported_occupancy_percent=None, basis='Native LAB row unavailable; no inference from ALM counts.')
    if len(rows) != 1: raise ValueError('one native top-level LAB usage row required')
    used, total, percent = rows[0]
    used, total = int(used.replace(',','')), int(total.replace(',',''))
    if not 0 <= used <= total or total <= 0: raise ValueError('native LAB usage/capacity range')
    return dict(available=True, partially_or_completely_used=used, device_total=total,
        native_reported_occupancy_percent=percent.strip(), measured_count_fraction=used/total,
        basis='Explicit native Total LABs: partially or completely used row in the retained after-Place resource report. Not inferred from ALMs.')


def summarize(root, receipt_pin):
    if hashlib.sha256(PARENT.read_bytes()).hexdigest() != PARENT_SHA: raise ValueError('frozen parent interpretation source drift')
    spec = importlib.util.spec_from_file_location('plain_summary_parent',PARENT)
    parent = importlib.util.module_from_spec(spec); spec.loader.exec_module(parent)
    result = parent.summarize(root,receipt_pin)
    result['schema'] = 'plain-fit-scoped-summary-v2'
    result['resources']['labs'] = labs((Path(root)/'project/output_files/probe.fit.place.rpt').read_text())
    result['parser_sha256'] = parent.sha(Path(__file__))
    result['dependency_helper_sha256'] = {'summarize_plain_fit_v1.py':PARENT_SHA}
    manifest = json.loads((Path(root)/'project/manifest.json').read_text())
    result['core_parameters'] = manifest.get('core_parameters')
    if result['scope'] == 'whole_core':
        result['limitation'] = 'Exploratory integrated compute-core interpretation of its own source-bound fit and constrained internal clock. Not board-I/O/reset-release sign-off, an audited production clock, full-size numerical PRP result or promotion review. Unconstrained paths and source exceptions remain explicit.'
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('root',type=Path)
    parser.add_argument('--receipt-sha256',required=True); args = parser.parse_args()
    result = summarize(args.root,args.receipt_sha256)
    with (args.root/'scoped-summary-v2.json').open('x') as stream: json.dump(result,stream,indent=2,allow_nan=False); stream.write('\n')
    print(json.dumps(dict(path=str(args.root/'scoped-summary-v2.json'), scope=result['scope'], resources=result['resources'],
        setup_slack_ns=result['timing']['setup_slack_ns'],hold_slack_ns=result['timing']['hold_slack_ns']),indent=2))
