"""Separate real FIRST-cohort mutant of the already-qualified root retiming.

The unchanged native independent NTT comparator must observe wrong hardware
data. Unknown faults/build failures are not accepted as this typed outcome.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from . import stream27_root_outputreg_bind as binding

ROOT = binding.ROOT
SELF = 'reference/stream27_root_outputreg_fault_native.py'
NORMAL = 's4-root-outreg-aw8-p16-f0-normal-q1-v1'
IDENTIFIER = 's4-root-outreg-first-mutant-q1-v2'
MARKER = 'S4_ROOT_OUTPUTREG_FIRST_MUTANT_DETECTED\n'
STEP = 'actual-root-first-hardware-mutant'

SHIM = r'''#include <sstream>
#define main qualified_normal_main
#include "root_outputreg_field.cpp"
#undef main
int main(int argc,char** argv){
    if(argc==2)return qualified_normal_main(argc,argv);
    std::ostringstream captured_out,captured_error;
    auto* old_out=std::cout.rdbuf(captured_out.rdbuf());
    auto* old_error=std::cerr.rdbuf(captured_error.rdbuf());
    const int rc=qualified_normal_main(argc,argv);
    std::cout.rdbuf(old_out);std::cerr.rdbuf(old_error);
    if(rc==1 && captured_out.str().empty() &&
       captured_error.str().rfind("S4_DATA case=1 ",0)==0){
        std::cout<<"S4_ROOT_OUTPUTREG_FIRST_MUTANT_DETECTED\n";return 41;
    }
    std::cerr<<"S4_ROOT_FIRST_MUTANT_NOT_THE_EXPECTED_DATA_REJECTION rc="<<rc
             <<" actual="<<captured_error.str();return 90;
}
'''


def prepare(output, budget):
    output = Path(output).resolve()
    binding.need(not output.exists(), 'S4_ROOTREG_MUTANT_FRESH_OUTPUT')
    binding.need(not (ROOT / 'docs/briefs/PAUSE').exists() and not (ROOT / 'queue/PAUSE').exists(), 'S4_ROOTREG_PAUSE')
    normal = ROOT / 'results/throughput-20260929/trackS-p16-root-outputreg-v1/aw8-f0-normal-v1'
    gate = json.loads((ROOT / f'queue/evidence/{NORMAL}/gate-receipt.json').read_text())
    binding.need(gate['status'] == 'PASS_expected_contracts', 'S4_ROOTREG_MUTANT_ACTUAL_NORMAL_PREREQUISITE')
    manifest = json.loads((normal / 'manifest.json').read_text())
    files = {name: (normal / 'source/fpga' / name).read_bytes() for name in manifest['sources']}
    binding.need(all(hashlib.sha256(raw).hexdigest() == manifest['sources'][name]
                     for name, raw in files.items()), 'S4_ROOTREG_MUTANT_CAPTURED_SOURCE_IDENTITY')
    library = 'rtl/merged_stream27_root_library_aw8_p16_f0_v1.sv'
    old = files[library].decode()
    anchor = 'first_q<=frame_start;'
    binding.need(old.count(anchor) == 15, 'S4_ROOTREG_MUTANT_EXACT_TRANSFORM_COHORTS')
    # Invert FIRST on both first/nonfirst tokens. Merely suppressing FIRST
    # can be masked by the prior complete frame's row0 prefetch, so that
    # weaker mutant is not a meaningful complete-frame numerical witness.
    new = old.replace(anchor, 'first_q<=!frame_start;')
    binding.need(new.replace('first_q<=!frame_start;', anchor) == old, 'S4_ROOTREG_MUTANT_ONLY_FIRST_SELECTION')
    files[library] = new.encode()
    cpp = 'rtl/tb/root_outputreg_first_mutant.cpp'
    files[cpp] = SHIM.encode()
    files['lineage/' + SELF] = (ROOT / SELF).read_bytes()
    source = output / 'source/fpga'
    for name, raw in files.items():
        path = source / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    stamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    manifest.update(source_root=str(source), output_parent=str(output / 'UNBOUND_OUTPUT'),
        sources={name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()},
        steps=[dict(name=STEP, argv=['{exe}'], expected_returncode=41,
                    expected_stdout=MARKER, expected_stderr='')],
        scope='Separate diagnostic mutant inverts15 transform FIRST flags. Already-PASS normal is machine prerequisite; unchanged independent NTT must detect case1 hardware data mismatch, exactrc41. No unknown errors accepted; not physical candidate RTL.', promotion_allowed=False)
    manifest['build']['cpp_source'] = cpp
    binding.need(all(re.fullmatch('[a-z][a-z0-9-]*', step['name']) for step in manifest['steps']),
                 'S4_ROOTREG_MUTANT_STEP_NAME_CONTRACT')
    path = output / 'manifest.json'; path.write_text(json.dumps(manifest, indent=2) + '\n')
    sys.path.insert(0, str(ROOT))
    from tools import native_class_package_v2 as package
    packet = output / 'packet-01'; worker = 's4-root-outreg-first-mutant-01-v2'
    package.prepare(path, source, 'gcp-c4d-static01-v1', worker, 'run', packet, Path(budget).resolve())
    native = json.loads((packet / 'ticket.json').read_text())
    ticket = json.loads((normal / 'global-ticket-v1.json').read_text())
    ticket['packages'][0].update(archive=str(packet / 'package.tar.gz'),
        sha256=hashlib.sha256((packet / 'package.tar.gz').read_bytes()).hexdigest(),
        ticket_sha256=hashlib.sha256((packet / 'ticket.json').read_bytes()).hexdigest(),
        manifest_sha256=native['manifest_sha256'], worker_id=worker, native_root=native['native_root'])
    candidate = 's4-root-outreg-first-mutant-v2'
    ticket.update(id=IDENTIFIER, candidate_id=candidate, created=stamp, test_role='deliberate_fault',
        after=[NORMAL], est_minutes=5, source_gate=dict(scope=manifest['scope'], promotion_allowed=False))
    snapshot = {name: pin for name, pin in manifest['sources'].items() if name.endswith('.sv')}
    ticket['rtl_readiness'] = dict(schema='gfn16-candidate-rtl-ready-v1', candidate_id=candidate,
        source_snapshot=snapshot, candidate_source_sha256=binding.sha(json.dumps(snapshot, sort_keys=True, separators=(',', ':'))),
        rtl_ready_at_utc=stamp)
    path = output / 'global-ticket-v1.json'; path.write_text(json.dumps(ticket, indent=2) + '\n')
    return dict(id=IDENTIFIER, input=str(path), rtl_ready_at_utc=stamp, expected_rc=41)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--output', required=True); p.add_argument('--budget', required=True)
    args = p.parse_args(); print(json.dumps(prepare(args.output, args.budget), indent=2))
