"""Prepare native representative AW5/AW8/AW16 gate without executing HDL.

Only scalar geometry is evaluated locally at AW16. Full word recipes exist in
the pinned C++ executable and execute solely on the explicitly admitted host.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
from fpga.reference.track_a4_representative_recipe_v1 import geometry
from fpga.reference.track_a4_representative_source_v1 import verify

ROOT=Path(__file__).resolve().parents[1]
TICKET='docs/briefs/replies/2026-10-01-B20260930A-A4-core-exploratory-ticket-v3.json'
TICKET_SHA='8c0286d905e844dc6e6939263e0d37147d437a0efcd7a2f2dc51bf99267e79b4'
LAUNCHER='tools/native_source_gate_v1.py'
LAUNCHER_SHA='5205f587313a1403fddabff58bbcf4565d27c8219aa2e0c3f4aaa3af2901c2cd'
CAPTURE='tools/snapshot_native_sources_v1.py'
CAPTURE_SHA='c49c5810e53cd981bde947d5dd9ab0f032d8f835403bb1c4a47971e89b62da1c'
CPP='rtl/tb/track_a4_core_representative_v1.cpp'
PARSER='reference/track_a4_representative_output_v1.py'
EXTRA=(CPP,'rtl/tb/track_a4_representative_recipe_v1.hpp',
    'reference/track_a4_representative_recipe_v1.py','reference/track_a4_representative_source_v1.py',PARSER,
    'reference/track_a4_representative_prepare_v1.py','reference/track_a4_core_aw5_output_v1.py',
    'tests/test_track_a4_representative_recipe_v1.py','tests/test_track_a4_representative_source_v1.py',
    'tests/test_track_a4_representative_prepare_v1.py',CAPTURE)


def need(ok,why):
    if not ok:raise ValueError(why)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pins(root=ROOT):
    need(sha(root/TICKET)==TICKET_SHA,'frozen v3 author ticket')
    ticket=json.loads((root/TICKET).read_text());result=dict(ticket['source_sha256'],**{TICKET:TICKET_SHA})
    for name in EXTRA:result[name]=sha(root/name)
    need(result[LAUNCHER]==LAUNCHER_SHA and result[CAPTURE]==CAPTURE_SHA,'frozen policy/capture')
    for name,value in result.items():
        path=root/name
        need(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root.resolve()) and sha(path)==value,'source pin drift: '+name)
    return result,ticket


def prepare(output,aw=16,root=ROOT):
    g=geometry(aw);root=Path(root).resolve();output=Path(output).resolve()
    need(not (root/'docs/briefs/PAUSE').exists(),'brief PAUSE')
    need(not output.exists(),'fresh representative preparation')
    source,ticket=pins(root);guard=verify(root)
    native=f'/home/jtl/gfn-fpga-lab/agent-work/track-a4-core-v3-representative-aw{aw}-aethia-v1'
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='aethia',
        source_root=native+'/snapshot-v1/fpga',output_parent=native,sources=source,
        build=dict(top='genefer_track_a4_core_v3',sv_sources=[p for p in ticket['native_sources'] if p.endswith('.sv')],
            cpp_source=CPP,parameters=dict(AW=aw),cflags=['-std=c++17','-Werror=return-type',f'-DA4_CORE_AW={aw}']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name=f'aw{aw}-representative',argv=['{exe}','--representative'],expected_returncode=0,expected_stderr='')],
        stdout_review=dict(parser=PARSER,parser_sha256=source[PARSER],geometry=g,
            contract='16 ordered scalar-recipe-bound measured rows and complete footer; strict budget checks, no substituted measurements'))
    output.mkdir(parents=True);draft=output/'draft/fpga';draft.mkdir(parents=True)
    for name,value in source.items():
        target=draft/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,target)
        need(sha(target)==value,'captured source drift')
    path=output/f'aw{aw}-manifest.json';path.write_text(json.dumps(manifest,indent=2)+'\n')
    spec=importlib.util.spec_from_file_location('_a4_representative_capture',draft/CAPTURE)
    capture=importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)
    captured=capture.capture(path,draft,output/'snapshot')
    need(pins(root)[0]==source,'live source drift after capture')
    report=dict(status='prepared_source_only_not_executed',aw=aw,rtl_lineage='exact genefer_track_a4_core_v3',
        author_ticket_sha256=TICKET_SHA,manifest_sha256=sha(path),source_members=len(source),
        snapshot_archive_sha256=captured['archive_sha256'],harness_delta_guard=guard,geometry=g,
        local_full_n_numeric_executed=False,full_n_materialization='native executable only; no numeric NTT oracle',
        cpus=[4,6],cpu_quota_percent=200,memory_max_bytes=4*(1<<30),compile_workers=2,model_threads=1,
        command=['taskset','-c','4,6','/usr/bin/python3.14','-B',native+'/snapshot-v1/fpga/'+LAUNCHER,
            '--manifest',native+f'/aw{aw}-manifest.json','--manifest-sha256',sha(path),'--output',native+f'/aw{aw}-native-v1'],
        output_replay=['/usr/bin/python3.14','-B',native+'/snapshot-v1/fpga/'+PARSER,'--aw',str(aw),
            '--output-log',native+f'/aw{aw}-native-v1/aw{aw}-representative.log'],
        dispatch_owner='main_only_after_explicit_slot_admission',promotion_allowed=False,
        limitations=['Representative deterministic arithmetic, not random/exhaustive faults/PRP/1000-square soak.',
            'AW16 latency remains a source hypothesis until this actual native run and independent review.',
            'No fit or usable-clock claim; no dispatch performed by preparer.'])
    (output/'preparation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--aw',type=int,choices=(5,8,16),default=16);args=parser.parse_args()
    print(json.dumps(prepare(args.output,args.aw),indent=2))
