"""Offline positive-only archive audit; never executes a native binary."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

from .crt27_mont_regression import PROFILE, ORDER, check_normal, check_probe


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def verify(root, stage):
    report=json.loads((root/'report.json').read_text())
    manifest=json.loads((stage/'manifest.json').read_text())
    assert report['status']=='passed_positive_only_mutations_pending'
    assert report['manifest_sha256']==sha(stage/'manifest.json')==sha(root/'approved-manifest.json')
    assert report['sources']==manifest['sources'] and report['profile']==manifest['profile']==PROFILE
    assert report['compiled_source_order']==manifest['compiled_source_order']==list(ORDER)
    assert report['vectors']==manifest['vectors']
    assert sha(root/'vectors.txt')==sha(stage/'vectors.txt')==manifest['vectors']['sha256']
    for name,value in report['artifacts'].items():
        assert (root/name).resolve().is_relative_to(root.resolve())
        assert sha(root/name)==value,name
    with tarfile.open(root/'sources.tar.gz','r:gz') as archive:
        members=archive.getmembers()
        assert len(members)==len(report['sources']) and {m.name for m in members}==set(report['sources'])
        for member in members:
            assert member.isfile() and hashlib.sha256(archive.extractfile(member).read()).hexdigest()==report['sources'][member.name]
    with tarfile.open(root/'generated-sources.tar.gz','r:gz') as archive:
        members=archive.getmembers()
        assert len(members)==len(report['generated_source_sha256'])
        assert {m.name for m in members}==set(report['generated_source_sha256'])
        for member in members:
            assert member.isfile() and hashlib.sha256(archive.extractfile(member).read()).hexdigest()==report['generated_source_sha256'][member.name]
    assert [s['name'] for s in report['steps']]==['verilator-version','g++-version','g1-oracle','build','probe','normal']
    for step in report['steps']:
        assert step['returncode']==0 and step['error'] is None
        assert sha(root/step['log'])==step['sha256']
    build=next(s['command'] for s in report['steps'] if s['name']=='build')
    assert build[:10]==['verilator','--cc','--exe','--build','-j','2','--threads','1','--assert','--top-module']
    assert build[10]=='crt3_27_mont_pair'
    assert '-DCRT27_CANDIDATE_DELAY=15 -DCRT27_FROZEN_DELAY=60' in build[14]
    assert report['limits']['affinity']==[0,2]
    assert len(set(tuple(c) for c in report['limits']['physical_cores']))==2
    assert report['limits']['memory_max_bytes']==6*(1<<30)
    assert report['normal_counts']==check_normal((root/'normal.log').read_text(),manifest['vectors'])
    assert report['probe']==check_probe((root/'probe.log').read_text())
    return dict(status='verified_positive_only_mutations_pending',report_sha256=sha(root/'report.json'),
                manifest_sha256=report['manifest_sha256'],sources_checked=len(report['sources']),
                generated_sources_checked=len(report['generated_source_sha256']),artifacts_checked=len(report['artifacts']),
                normal_counts=report['normal_counts'],latency_edge_offsets=dict(candidate=15,frozen=60),
                complete_g2=False,physical_or_whole_core_qualification=False,
                native_unit='gfn-crt27-mont-positive-v1.service',invocation_id='acabc9cef505496a9789f90e65985bf0',
                externally_observed=dict(runtime_seconds=15.341,cpu_seconds=13.747,memory_peak_mib=524.4,swap_bytes=0),
                helper_sha256_before_and_after={
                    '/usr/bin/make':'27c9f6d806aee15882b01c2c61848f7aa75caa14bc7b6f608ba422f9e46a7d49',
                    '/home/jtl/gfn-fpga-lab/tools/verilator/usr/bin/verilator_bin':'90fe12f3b2c752b607690cb05a566646398d1e07f38e83f5f7a7f35c20560247'})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path);parser.add_argument('stage',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();receipt=verify(args.archive,args.stage)
    with args.output.open('x') as stream:json.dump(receipt,stream,indent=2);stream.write('\n')
    print(json.dumps(receipt,indent=2))
