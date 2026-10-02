"""Source-only bounded S-M1 FIFO pilot packet. Main dispatches after lint."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from .stream27_sm1_source_v1 import verify,pilot_counts

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
LAUNCHER='tools/native_source_gate_v1.py'
CAPTURE='tools/snapshot_native_sources_v1.py'
FILES=('rtl/kernel/genefer_stream27_mdc_commutator_sync.sv',
    'rtl/kernel/genefer_stream27_mdc_commutator_slots_v2.sv','rtl/kernel/genefer_stream27_mdc_commutator_slots_sm1_v1.sv',
    'rtl/kernel/genefer_stream27_mdc_fifo_smallreg_v1.sv','rtl/tb/stream27_sm1_fifo_probe_v1.sv','rtl/tb/stream27_sm1_fifo_v1.cpp',
    'reference/stream27_sm1_source_v1.py','reference/stream27_sm1_pilot_prepare_v1.py','tests/test_stream27_sm1_source_v1.py',
    LAUNCHER,CAPTURE)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(output):
    if (ROOT/'docs/briefs/PAUSE').exists():raise ValueError('brief PAUSE')
    output=Path(output).resolve()
    if output.exists():raise ValueError('fresh pilot stage')
    guard=verify();counts=pilot_counts();pins={name:sha(ROOT/name) for name in FILES}
    if pins[LAUNCHER]!='5205f587313a1403fddabff58bbcf4565d27c8219aa2e0c3f4aaa3af2901c2cd':raise ValueError('frozen native launcher')
    if pins[CAPTURE]!='c49c5810e53cd981bde947d5dd9ab0f032d8f835403bb1c4a47971e89b62da1c':raise ValueError('frozen capture')
    native='/home/jtl/gfn-fpga-lab/agent-work/stream27-sm1-fifo-pilot-v1'
    sv=[FILES[0],FILES[3],FILES[4]]
    footer='SM1_FIFO_PASS '+' '.join(f'{key}={value}' for key,value in counts.items())+'\n'
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='aethia',source_root=native+'/snapshot-v1/fpga',
        output_parent=native,sources=pins,build=dict(top='stream27_sm1_fifo_probe_v1',sv_sources=sv,
            cpp_source='rtl/tb/stream27_sm1_fifo_v1.cpp',parameters={},cflags=['-std=c++17','-Werror=return-type']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='fifo-pilot',argv=['{exe}','--pilot'],expected_returncode=0,expected_stdout=footer,expected_stderr='')],
        lint_prerequisite='Main must capture warning-fatal lint-only with matching source/top/flags before native build; frozen launcher does not add this step.',
        scope='FIFO exact reference and independent queue only. No whole-field, fault successor, RTL timing or physical memory inference qualification.')
    draft=output/'draft/fpga';draft.mkdir(parents=True)
    for name,pin in pins.items():
        target=draft/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
        if sha(target)!=pin:raise ValueError('captured source drift')
    path=output/'pilot-manifest.json';path.write_text(json.dumps(manifest,indent=2)+'\n')
    spec=importlib.util.spec_from_file_location('_sm1_capture',draft/CAPTURE);capture=importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)
    captured=capture.capture(path,draft,output/'snapshot')
    report=dict(status='prepared_source_only',manifest_sha256=sha(path),archive_sha256=captured['archive_sha256'],
        sources=pins,counts=counts,exact_delta=guard,top='stream27_sm1_fifo_probe_v1',
        native_root=native,cpus=[4,6],cpu_quota_percent=200,memory_max_bytes=4*(1<<30),compile_workers=2,model_threads=1,
        dispatch_owner='main only; no execution by preparer',lint_before_build=True,
        command=['taskset','-c','4,6','/usr/bin/python3.14','-B',native+'/snapshot-v1/fpga/'+LAUNCHER,
            '--manifest',native+'/pilot-manifest.json','--manifest-sha256',sha(path),'--output',native+'/pilot-native-v1'])
    (output/'preparation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(prepare(parser.parse_args().output),indent=2))
