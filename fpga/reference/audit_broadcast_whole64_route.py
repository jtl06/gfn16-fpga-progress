"""Offline audit of the first archived R2 broadcast whole64 route; no tool runs."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(root, gate_path):
    context = json.loads((root / 'execution-context.json').read_text())
    result = json.loads((root / 'execution-result.json').read_text())
    manifest = json.loads((root / 'manifest.json').read_text())
    summaries = list(root.glob('*-summary.json'))
    assert len(summaries) == 1, 'ambiguous summary'
    summary = next(iter(json.loads(summaries[0].read_text()).values()))
    gate = json.loads(gate_path.read_text())
    assert gate['status'] == 'passed' and gate['aw'] == 16
    assert result['quartus_returncode'] == result['summarize_returncode'] == 0
    assert result['context_sha256'] == digest(root / 'execution-context.json')
    assert context['manifest_sha256'] == digest(root / 'manifest.json')
    assert context['source_sha256'] == manifest['source_sha256'] == summary['manifest']['source_sha256']
    for name, expected in context['source_sha256'].items():
        assert digest(root / 'rtl' / name) == expected, name
        matches = [v for k, v in gate['sources'].items()
                   if k == 'rtl/kernel/' + name or k.endswith('/rtl/kernel/' + name)]
        assert matches == [expected], 'native simulation source mismatch: ' + name
    controls = {}
    for name, expected in context['control_sha256'].items():
        raw = (root / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() == expected:
            controls[name] = 'exact'
        else:
            suffix = b'set_global_assignment -name LAST_QUARTUS_VERSION "26.1.0 Pro Edition"\n'
            assert name == 'probe.qsf' and raw.endswith(suffix), name
            assert hashlib.sha256(raw[:-len(suffix)]).hexdigest() == expected, name
            controls[name] = 'exact vendor version append only'
    fit = (root / 'output_files/probe.fit.rpt').read_text()
    sta = (root / 'output_files/probe.sta.rpt').read_text()
    log = next(root.glob('*-fit.log')).read_text()
    assert 'Quartus Prime Fitter was successful. 0 errors' in log
    assert 'Timing requirements not met' in log
    assert summary['fit_success'] is True and summary['internal_timing_met'] is False
    assert summary['fmax_mhz'] == 78.08 and '78.08 MHz' in sta
    assert summary['setup_slack_ns'] == -2.807 and summary['hold_slack_ns'] == .015
    labs = re.search(r'Total LABs:.*?;\s*([\d,]+)\s*/\s*([\d,]+)', fit)
    assert labs, 'LAB metrics absent'
    used, total = (int(x.replace(',', '')) for x in labs.groups())
    assert (used, total) == (41446, 42720)
    assert 'coefficient_lane[13].crt|delta2[12]' in sta
    artifacts = {str(p.relative_to(root)): digest(p)
                 for p in sorted(root.rglob('*')) if p.is_file()}
    return dict(status='source_matched_whole64_route_not_timing_closure',
                scope='AW16 NTT64 carry16 virtual-I/O integrated core; no board or full PRP run',
                native_gate_sha256=digest(gate_path), source_files_checked=len(context['source_sha256']),
                control_checks=controls, source_match=True,
                finished_at=result['finished_at'], elapsed_seconds=8651,
                resources={k: summary[k] for k in ('alms_needed', 'alms_placed', 'registers',
                           'ram_blocks', 'dsp_blocks_needed', 'dsp_blocks_placed')},
                labs_used=used, labs_available=total, lab_percent=100 * used / total,
                timing=dict(target_mhz=100, reported_fmax_mhz=78.08, setup_ns=-2.807,
                            hold_ns=.015, target_met=False,
                            critical_family='NTT data RAM output to CRT input delta2',
                            first_path_data_ns=12.649, interconnect_ns=8.792,
                            cell_ns=1.687, ram_clock_to_output_ns=2.170),
                limitations=['No re-constrained lower-clock STA audit', 'Virtual I/O unconstrained',
                             'Reset false-pathed', 'No board sign-off or measured throughput',
                             'Critical-path family manually cross-checked against archived STA report'],
                artifacts=artifacts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('gate', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    receipt = audit(args.archive, args.gate)
    with args.output.open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'artifacts'}))


if __name__ == '__main__':
    main()
