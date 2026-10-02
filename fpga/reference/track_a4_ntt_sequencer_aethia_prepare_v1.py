"""Additive exact AW5 aethia preparation, frozen GCP package untouched.

Only host/source/output placement changes. Same guarded RTL, harness, flags,
thread probe, original smoke and typed negative. Native dispatch is external.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT=Path(__file__).resolve().parents[1]
PARENT='reference/track_a4_ntt_sequencer_prepare_v1.py'
PARENT_SHA='650b27822380ef5df1cf1cd2c92d46ff7b44200bf27f237cec8321eb858f1c9e'
GCP='results/throughput-20260929/track-a4-ntt-sequencer-portable-gcp-stage-v1/aw5-manifest.json'
GCP_SHA='3a4334334dd6b918fc204c9d1cdc46f10861011bf21a37cdb0cb34cc7b66731c'
SELF='reference/track_a4_ntt_sequencer_aethia_prepare_v1.py'
TEST='tests/test_track_a4_ntt_sequencer_aethia_prepare_v1.py'
BASE='/home/jtl/gfn-fpga-lab/agent-work/track-a4-ntt-sequencer'
SOURCE=BASE+'/snapshot-aethia-v1/fpga'


def require(ok,why):
    if not ok:raise ValueError(why)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def parent_module():
    require(sha(ROOT/PARENT)==PARENT_SHA,'frozen GCP preparation source')
    require(sha(ROOT/GCP)==GCP_SHA,'frozen GCP manifest')
    from fpga.reference import track_a4_ntt_sequencer_prepare_v1 as parent
    return parent


def source_pins():
    parent=parent_module();pins,guard=parent.source_pins()
    require(json.loads((ROOT/GCP).read_text())==parent.manifest(pins),'exact frozen GCP identity')
    pins={**pins,GCP:GCP_SHA,SELF:sha(ROOT/SELF),TEST:sha(ROOT/TEST)}
    return pins,guard


def manifest(pins):
    parent=parent_module();result=parent.manifest(pins)
    result.update(host='aethia',source_root=SOURCE,output_parent=BASE)
    return result


def prepare(output):
    require(not (ROOT/'docs/briefs/PAUSE').exists(),'brief PAUSE')
    output=Path(output).resolve();require(not output.exists(),'fresh aethia preparation')
    pins,guard=source_pins();source=output/'source/fpga';source.mkdir(parents=True)
    for name in sorted(pins):
        destination=source/name;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,destination)
    require(all(sha(source/name)==digest for name,digest in pins.items()),'aethia staged source SHA')
    path=output/'aw5-manifest.json';path.write_text(json.dumps(manifest(pins),indent=2)+'\n')
    with tarfile.open(output/'source.tar.gz','x:gz') as archive:
        for name in sorted(pins):archive.add(source/name,arcname='fpga/'+name,recursive=False)
    require(source_pins()[0]==pins,'live source drift after aethia package')
    result=dict(status='prepared_aethia_original_aw5_sequencer_not_executed',sources=pins,
                manifest_sha256=sha(path),source_archive_sha256=sha(output/'source.tar.gz'),
                source_root=SOURCE,output_parent=BASE,host='aethia',source_guard=guard,
                frozen_gcp_manifest_sha256=GCP_SHA,host_delta_only=True,
                scope='Existing frozen native_source_gate_v1 aethia profile,CPU4/6,200%/4GiB/noSwap; original smoke and typed negative only.',
                native_execution=False,promotion_allowed=False)
    (output/'preparation.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.output),indent=2))
