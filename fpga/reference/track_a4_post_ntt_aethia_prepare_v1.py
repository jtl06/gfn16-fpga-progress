"""Freeze the author's exact unretimed AW5 post-NTT baseline for aethia.

Only pure Python AW5 corpus preparation; no HDL, dispatch, fit or promotion.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
TICKET = 'docs/briefs/replies/2026-10-01-B20260930A-A4-post-ntt-exploratory-ticket-v1.json'
TICKET_SHA = '8399ad7219751d2bacc3640f6db25e0998628e47eac3011904a3b628742c2778'
SELF = 'reference/track_a4_post_ntt_aethia_prepare_v1.py'
TEST = 'tests/test_track_a4_post_ntt_aethia_prepare_v1.py'
LAUNCHER = 'tools/native_source_gate_v1.py'
CAPTURE = 'tools/snapshot_native_sources_v1.py'
FIXED = {TICKET:TICKET_SHA,
    'reference/__init__.py':'1c6df6d638965f2bc1c163f4e66f7f9038ebedc21e2139988aa5962c0ed47efb',
    LAUNCHER:'5205f587313a1403fddabff58bbcf4565d27c8219aa2e0c3f4aaa3af2901c2cd'}
NATIVE = '/home/jtl/gfn-fpga-lab/agent-work/track-a4-post-ntt-aw5-aethia-v1'
BENCH = 'rtl/tb/track_a4_post_ntt_v1.cpp'
VECTOR = 'vectors-aw5.txt'


def need(ok, why):
    if not ok: raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def pins(root=ROOT):
    need(sha(root/TICKET) == TICKET_SHA, 'author ticket identity')
    ticket = json.loads((root/TICKET).read_text())
    need(ticket['status'] == 'exploratory_source_snapshot_ticket_not_qualification' and
         ticket['native_top'] == 'track_a4_post_ntt_probe_v1' and ticket['native_aw'] == [5,8], 'author scope')
    result = dict(ticket['source_sha256'], **FIXED)
    for name in (SELF, TEST, CAPTURE): result[name] = sha(root/name)
    for name, digest in result.items():
        path = root/name
        need(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root.resolve()) and sha(path) == digest,
             'ticket source drift: '+name)
    return result, ticket


def expected_footer(metadata):
    need(metadata['aw'] == 5 and metadata['cases'] == 20 and metadata['post_clocks'] == 60 and
         metadata['field_words'] == 1920 and metadata['image_words'] == 640, 'bounded AW5 post-service corpus')
    return 'A4_POST_NTT_PASS '+' '.join(f'{key}={metadata[key]}' for key in ('aw','cases','post_clocks','field_words','image_words'))+'\n'


def prepare(output, root=ROOT):
    root = Path(root).resolve(); output = Path(output).resolve()
    need(not (root/'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    original, ticket = pins(root)
    need(not output.exists(), 'fresh standalone post preparation')
    draft = output/'draft/fpga'; draft.mkdir(parents=True)
    for name, digest in original.items():
        target = draft/name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(root/name, target)
        need(sha(target) == digest, 'frozen draft copy identity')
    # The corpus imports ONLY the copied ticket closure in a clean interpreter;
    # no evolving live module or existing fpga import namespace is consulted.
    code = '''import hashlib,json,pathlib,sys
from fpga.reference.track_a4_post_ntt_vectors_v1 import corpus
root=pathlib.Path(sys.argv[1]).resolve()
text,metadata=corpus(5)
imports={}
for name,module in tuple(sys.modules.items()):
    path=getattr(module,'__file__',None)
    if path and (name=='fpga' or name.startswith('fpga.')):
        path=pathlib.Path(path).resolve();assert path.is_relative_to(root)
        imports[str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
print(json.dumps(dict(text=text,metadata=metadata,imports=imports)))
'''
    env = dict(PATH=os.environ.get('PATH','/usr/bin:/bin'), PYTHONPATH=str(draft.parent), PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1')
    process = subprocess.run([sys.executable, '-B', '-c', code, str(draft)], cwd=output, env=env, text=True, capture_output=True, timeout=30)
    (output/'corpus.stdout').write_text(process.stdout); (output/'corpus.stderr').write_text(process.stderr)
    need(process.returncode == 0, 'snapshot-only AW5 Python corpus')
    corpus = json.loads(process.stdout); metadata = next(row for row in ticket['corpora'] if row['aw'] == 5)
    need(corpus['metadata'] == metadata and all(original.get(name) == value for name,value in corpus['imports'].items()), 'exact author corpus/import closure')
    (draft/VECTOR).write_text(corpus['text']); need(sha(draft/VECTOR) == metadata['sha256'], 'exact AW5 vector bytes')
    all_pins = dict(original, **{VECTOR:metadata['sha256']})
    manifest = dict(schema='native-source-gate-v1', status='prepared_not_executed', host='aethia',
        source_root=NATIVE+'/snapshot-v1/fpga', output_parent=NATIVE, sources=all_pins,
        build=dict(top=ticket['native_top'], sv_sources=[name for name in ticket['native_sources'] if name.endswith('.sv')],
            cpp_source=BENCH, parameters=dict(AW=5), cflags=['-std=c++17','-Werror=return-type','-DA4_POST_AW=5']),
        probe=dict(argv=['{exe}','--runtime-probe'], expected_json=dict(context_threads=1,model_threads=1,expected_threads=1)),
        steps=[dict(name='aw5-post-corpus', argv=['{exe}','{root}/'+VECTOR], expected_returncode=0,
            expected_stdout=expected_footer(metadata), expected_stderr='')])
    path = output/'aw5-manifest.json'; path.write_text(json.dumps(manifest,indent=2)+'\n')
    import importlib.util
    spec = importlib.util.spec_from_file_location('_pinned_native_snapshot', draft/CAPTURE)
    capture = importlib.util.module_from_spec(spec); spec.loader.exec_module(capture)
    captured = capture.capture(path, draft, output/'snapshot')
    need(pins(root)[0] == original, 'author/live input drift after frozen capture')
    report = dict(status='prepared_not_executed', author_ticket_sha256=TICKET_SHA, source_members=len(all_pins),
        manifest_sha256=sha(path), snapshot_archive_sha256=captured['archive_sha256'], snapshot_capture_sha256=sha(output/'snapshot/capture.json'),
        corpus=metadata, imported_snapshot_sources=corpus['imports'], native_root=NATIVE, host='aethia', cpus=[4,6],
        memory_max_bytes=4*(1<<30), cpu_quota_percent=200, model_threads=1, compile_workers=2,
        run_command=['taskset','-c','4,6','/usr/bin/python3.14','-B',NATIVE+'/snapshot-v1/fpga/'+LAUNCHER,
            '--manifest',NATIVE+'/aw5-manifest.json','--manifest-sha256',sha(path),'--output',NATIVE+'/aw5-native-v1'],
        dispatch_owner='main_after_sequencer_releases_4_6',
        scope='Unretimed normal CRT/carry/prefill/patch functional and edge baseline, AW5 only; NTT transforms excluded.',
        limitations=['No HDL, native execution, fit, clock or whole-core promotion performed.',
            'This is not the retimed physical-fit candidate. Fault matrix and AW8 are separate gates.',
            'A native cycle/output mismatch is failed evidence, never relabeled to match the estimate.'])
    (output/'preparation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(prepare(parser.parse_args().output),indent=2))
