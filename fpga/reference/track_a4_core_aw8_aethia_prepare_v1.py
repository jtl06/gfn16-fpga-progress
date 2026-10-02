"""Capture the exact core-v3 author ticket for one exploratory AW8 native gate."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
TICKET='docs/briefs/replies/2026-10-01-B20260930A-A4-core-exploratory-ticket-v3.json'
TICKET_SHA='8c0286d905e844dc6e6939263e0d37147d437a0efcd7a2f2dc51bf99267e79b4'
SELF='reference/track_a4_core_aw8_aethia_prepare_v1.py'
TEST='tests/test_track_a4_core_aw8_aethia_prepare_v1.py'
PARSER='reference/track_a4_core_output_v2.py'
PARSER_BASE='reference/track_a4_core_aw5_output_v1.py'
PARSER_TEST='tests/test_track_a4_core_output_v2.py'
CAPTURE='tools/snapshot_native_sources_v1.py'
LAUNCHER='tools/native_source_gate_v1.py'
LAUNCHER_SHA='5205f587313a1403fddabff58bbcf4565d27c8219aa2e0c3f4aaa3af2901c2cd'
NATIVE='/home/jtl/gfn-fpga-lab/agent-work/track-a4-core-v3-aw8-aethia-v1'
VECTOR='vectors-aw8.txt'


def need(ok,why):
    if not ok:raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def pins(root=ROOT):
    need(sha(root/TICKET)==TICKET_SHA,'exact author core-v3 ticket')
    ticket=json.loads((root/TICKET).read_text())
    need(ticket['status']=='exploratory_whole_square_source_ticket_not_qualification' and ticket['native_top']=='genefer_track_a4_core_v3','real whole-core-v3 scope')
    result=dict(ticket['source_sha256'],**{TICKET:TICKET_SHA})
    for name in (SELF,TEST,PARSER,PARSER_BASE,PARSER_TEST,CAPTURE):result[name]=sha(root/name)
    need(result[LAUNCHER]==LAUNCHER_SHA,'frozen native policy')
    for name,value in result.items():
        path=root/name
        need(not path.is_symlink() and path.is_file() and path.resolve().is_relative_to(root.resolve()) and sha(path)==value,'declared source drift: '+name)
    return result,ticket


def prepare(output,root=ROOT):
    root=Path(root).resolve();output=Path(output).resolve();need(not (root/'docs/briefs/PAUSE').exists(),'brief PAUSE')
    original,ticket=pins(root);need(not output.exists(),'fresh whole-core preparation')
    draft=output/'draft/fpga';draft.mkdir(parents=True)
    for name,value in original.items():
        target=draft/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,target);need(sha(target)==value,'exact frozen draft')
    code='''import hashlib,json,pathlib,sys
from fpga.reference.track_a4_core_vectors_v1 import corpus
from fpga.reference.track_a4_core_source_v3 import verify
root=pathlib.Path(sys.argv[1]).resolve();text,metadata=corpus(8);guard=verify(root)
imports={}
for name,module in tuple(sys.modules.items()):
    path=getattr(module,'__file__',None)
    if path and (name=='fpga' or name.startswith('fpga.')):
        path=pathlib.Path(path).resolve();assert path.is_relative_to(root)
        imports[str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
print(json.dumps(dict(text=text,metadata=metadata,guard=guard,imports=imports)))
'''
    env=dict(PATH=os.environ.get('PATH','/usr/bin:/bin'),PYTHONPATH=str(draft.parent),PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1')
    result=subprocess.run([sys.executable,'-B','-c',code,str(draft)],cwd=output,env=env,capture_output=True,text=True,timeout=30)
    (output/'corpus.stdout').write_text(result.stdout);(output/'corpus.stderr').write_text(result.stderr)
    need(result.returncode==0,'isolated frozen AW8 corpus/edge-delta guard')
    generated=json.loads(result.stdout);metadata=next(row for row in ticket['corpora'] if row['aw']==8)
    need(generated['metadata']==metadata and generated['guard']==ticket['guard_result'] and
         all(original.get(name)==value for name,value in generated['imports'].items()),'author corpus/guard/import identities')
    (draft/VECTOR).write_text(generated['text']);need(sha(draft/VECTOR)==metadata['sha256'],'exact AW8 integer vector')
    sources=dict(original,**{VECTOR:metadata['sha256']})
    manifest=dict(schema='native-source-gate-v1',status='prepared_not_executed',host='aethia',source_root=NATIVE+'/snapshot-v1/fpga',output_parent=NATIVE,
        sources=sources,build=dict(top=ticket['native_top'],sv_sources=[name for name in ticket['native_sources'] if name.endswith('.sv')],
            cpp_source='rtl/tb/track_a4_core_v3.cpp',parameters=dict(AW=8),cflags=['-std=c++17','-Werror=return-type','-DA4_CORE_AW=8']),
        probe=dict(argv=['{exe}','--runtime-probe'],expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='aw8-whole-core',argv=['{exe}','{root}/'+VECTOR],expected_returncode=0,expected_stderr='')],
        stdout_review=dict(parser=PARSER,parser_sha256=sources[PARSER],vector_sha256=metadata['sha256'],
            contract='14 exact vector-bound measured rows plus complete fixed coverage footer; strict schedule/root assertions, ticks/max_latency remain measurements.',
            schedule_discrepancies='strict parser rejects mismatch; separate --report-schedule-mismatch diagnostic preserves measured values'))
    path=output/'aw8-manifest.json';path.write_text(json.dumps(manifest,indent=2)+'\n')
    spec=importlib.util.spec_from_file_location('_snapshot_core_v3',draft/CAPTURE);capture=importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)
    captured=capture.capture(path,draft,output/'snapshot');need(pins(root)[0]==original,'author/source drift after capture')
    report=dict(status='prepared_not_executed',author_ticket_sha256=TICKET_SHA,manifest_sha256=sha(path),source_members=len(sources),
        snapshot_archive_sha256=captured['archive_sha256'],snapshot_capture_sha256=sha(output/'snapshot/capture.json'),corpus=metadata,
        exact_successor_guard=generated['guard'],imported_snapshot_sources=generated['imports'],
        audit_only_provenance_inputs=['results/throughput-20260929/track-a4-core-v2-aw5-aethia-v1/build.stderr.log'],
        host='aethia',cpus=[4,6],memory_max_bytes=4*(1<<30),
        cpu_quota_percent=200,model_threads=1,compile_workers=2,native_root=NATIVE,
        command=['taskset','-c','4,6','/usr/bin/python3.14','-B',NATIVE+'/snapshot-v1/fpga/'+LAUNCHER,'--manifest',NATIVE+'/aw8-manifest.json',
            '--manifest-sha256',sha(path),'--output',NATIVE+'/aw8-native-v1'],
        required_output_replay=['env','PYTHONPATH='+NATIVE+'/snapshot-v1','/usr/bin/python3.14','-B',NATIVE+'/snapshot-v1/fpga/'+PARSER,'--output-log',NATIVE+'/aw8-native-v1/aw8-whole-core.log',
            '--vectors',NATIVE+'/snapshot-v1/fpga/'+VECTOR],
        dispatch_owner='main_only_after_explicit_slot_admission',
        limitations=['Exploratory AW8 real complete core: normal/readback/response hold and one in-flight reset only.',
            'Full fault matrix, full-N and fit excluded; no local HDL or full-N numeric NTT.',
            'Frozen policy returns native command evidence only; strict stdout replay and independent review remain mandatory.',
            'Generic finite queue v1 exact-stdout schema does not admit these measured phase rows; use this separately bounded standalone manifest.'])
    (output/'preparation.json').write_text(json.dumps(report,indent=2)+'\n');return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(prepare(parser.parse_args().output),indent=2))
