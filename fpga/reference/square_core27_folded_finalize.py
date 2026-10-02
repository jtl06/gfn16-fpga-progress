"""Consolidate completed routing-only gates and compare immutable baseline metrics."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
from .square_core27_folded_report import normalize


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if socket.gethostname()!='aethia': raise RuntimeError('aethia only')
    evidence=[]; metrics=[]; source_identities=None; faults=set(); comparison_count=0
    for label,lanes in [('small16-v1',16),('full16-v1',16),('full64-v1',64)]:
        path=args.artifacts/label/'report.json'; raw=json.loads(path.read_bytes())
        view=normalize(raw)
        if raw['profiles']!=[[lanes,16]]: raise ValueError('wrong gate profile')
        if source_identities is None: source_identities=raw['sources']
        if raw['sources']!=source_identities: raise ValueError('source identities differ between gates')
        for build in raw['builds']:
            if sha(Path(build['executable']))!=build['executable_sha256']:
                raise ValueError('executable changed after gate')
        baseline_path=args.baseline/f'core27-{lanes}-16-report.json'
        baseline=json.loads(baseline_path.read_bytes())
        if baseline['status']!='passed': raise ValueError('unpassed baseline')
        index={(item['aw'],item['case']):item for item in baseline['metrics']}
        for item in raw['metrics']:
            previous=index[(item['aw'],item['case'])]
            for key in ('conversion','roots','crt','carry','passes','base','cache_before','root_loads','root_hits','readback'):
                if item[key]!=previous[key]: raise ValueError('nonrouting counter changed: '+key)
            delta=2*item['aw']+3
            if item['ntt']!=previous['ntt']+delta or item['cycles']!=previous['cycles']+delta:
                raise ValueError('unexpected routing latency')
            comparison_count+=1
        rejected={step['name'].removeprefix('reject-') for step in raw['steps'] if step['name'].startswith('reject-')}
        faults.update(rejected)
        evidence.append(dict(report=str(path.resolve()),sha256=sha(path),status=raw['status'],
                             steps=len(raw['steps']),metrics=len(raw['metrics']),
                             baseline=str(baseline_path.resolve()),baseline_sha256=sha(baseline_path)))
        metrics.extend(view['metrics'])
    required={'raw-truncate','convert-radix','conversion-word','root-order','inverse-phase',
              'double','coefficient-row','digit-base','cache-reset','cache-reload','immediate-start',
              'reducer-error','wrong-r2','old-crt','host-quarter','fold-base','fold-direction','fold-mask'}
    if faults!=required: raise ValueError('incomplete or unexpected fault coverage')
    if comparison_count!=2168: raise ValueError('incomplete exact baseline matrix')
    for item in source_identities:
        if sha(Path(__file__).resolve().parents[1]/item)!=source_identities[item]:
            raise ValueError('source changed since tests: '+item)
    output=dict(status='passed',experiment='atomic27 cached folded routing only',
                evidence=evidence,sources=source_identities,metrics=metrics,
                baseline_comparisons=comparison_count,faults=sorted(faults),
                finalizer_sha256=sha(Path(__file__)),
                note='Every non-NTT counter equals the frozen baseline; NTT and total add exactly 2*AW+3. No FPGA fit or MHz claim.')
    with args.output.open('x') as handle:
        json.dump(output,handle,indent=2);handle.write('\n')
    print('PASS',comparison_count,'baseline comparisons;',len(faults),'rejected faults;',args.output)


if __name__=='__main__': main()
