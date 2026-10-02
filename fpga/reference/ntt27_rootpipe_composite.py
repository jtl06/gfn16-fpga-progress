"""Read-only qualification of exact failed-small + targeted-recovery evidence.

The original run remains FAILED. A separate composite qualifies its passing
normal checks and eight detected faults plus the four recovery detections.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

PINS={
 'root':'8b6ed1b3873dc4a0e2694dbf726f4ea9fa631994b8e22f3b7141105fe4e005c0',
 'lanes1':'052bd4b9c709eb642932d14ba016c3ce69f744f4929585d4e97182405cec6b75',
 'lanes64':'f6c37caf13cfca4eda23e7e87df5741961b456fdac27ca07d70183ab59935553',
 'recovery':'e1b8103d3c3a31d37528dd2247cd78c0205796e4767c6328f303abff0aa030d3'}
OLD={'upper-control','rotation','cut-word','data-delay','valid-delay','row-tag','orientation-tag','point-half-tag'}
NEW={'point-data','point-valid','clip-delay','pairing-delay'}


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def require(value,message):
    if not value:raise ValueError(message)


def pinned(path,key):
    require(digest(path)==PINS[key],'report pin mismatch '+key)
    return json.loads(Path(path).read_text())


def validate_composite(failed_report,recovery_report,source_root=None,check_executables=False):
    failed_report=Path(failed_report).resolve();recovery_report=Path(recovery_report).resolve()
    original=pinned(failed_report,'root')
    one_path=failed_report.parent/'lanes1/report.json';many_path=failed_report.parent/'lanes64/report.json'
    one=pinned(one_path,'lanes1');many=pinned(many_path,'lanes64');recovery=pinned(recovery_report,'recovery')
    require(original['status']=='failed' and original['requested_lanes']==[1,64] and original['quick'] is True,'original gate identity')
    require(one['status']=='passed' and all(x['passed'] is True for x in one['steps']),'L1 gate did not pass')
    require(many['status']=='failed','original L64 status was relabeled')
    require([x['name'] for x in many['steps'] if x['passed'] is not True]==['reject-mutation-point-data'],'unexpected original failure')
    escaped=next(x for x in many['steps'] if x['name']=='reject-mutation-point-data')
    require(len(escaped['attempts'])==2 and all(x['returncode']==0 and x['rejected'] is False for x in escaped['attempts']),'original escape not preserved')
    detected={x['name'].removeprefix('reject-mutation-') for x in many['steps'] if x['name'].startswith('reject-mutation-') and x['passed'] is True}
    require(detected==OLD,'original eight-fault coverage mismatch')
    require(recovery['status']=='passed' and all(x['passed'] is True for x in recovery['steps']),'recovery failed')
    require(recovery['profile']=='rootpipe-recovery-aw14-j4-runtime1-v1','recovery profile mismatch')
    require(recovery['ancestor']['status']=='failed' and recovery['ancestor']['root_sha256']==PINS['root'] and recovery['ancestor']['lane_sha256']==PINS['lanes64'],'recovery ancestry mismatch')
    require(set(recovery['logical_mutations'])==OLD|NEW and all(x['passed'] is True for x in recovery['logical_mutations'].values()),'incomplete twelve-fault qualification')
    for name in OLD:
        old_step=next(x for x in many['steps'] if x['name']=='reject-mutation-'+name)
        require(recovery['logical_mutations'][name]['step']==old_step,'borrowed prior fault evidence')
    require(recovery['logical_mutations']['point-data']['source_sha256']==escaped['source_sha256'],'escaped mutant changed')
    boundary=recovery['boundary_baseline']
    require(boundary['passed'] is True and boundary['aw']==14 and boundary['lanes']==64 and
            boundary['phases']==[0,3] and boundary['cycles']==[265,265] and boundary['checked_words']==32768,'missing directed boundary baseline')
    require('NTT mismatch index=8128' in (recovery_report.parent/'reject-point-data-0.log').read_text(),'missing actual folded-half counterexample')
    require(one['source_sha256']==many['source_sha256'],'small variants used different sources')
    for name,sha in many['source_sha256'].items():
        require(recovery['source_sha256'].get(name)==sha,'recovery changed old source '+name)
    checked_logs=0
    for path,report in ((one_path,one),(many_path,many),(recovery_report,recovery)):
        for name,sha in report['evidence_sha256'].items():
            require(digest(path.parent/name)==sha,'archived evidence mismatch '+name);checked_logs+=1
    for folder,report in ((failed_report.parent,many),(recovery_report.parent,recovery)):
        with tarfile.open(folder/'source-snapshot.tar.gz') as archive:
            require(set(archive.getnames())==set(report['source_sha256']),'source archive closure mismatch')
            for name,sha in report['source_sha256'].items():
                require(hashlib.sha256(archive.extractfile(name).read()).hexdigest()==sha,'source archive content mismatch')
                if source_root is not None:require(digest(Path(source_root)/name)==sha,'current source mismatch '+name)
        manifest=report['toolchain_manifest']
        require(digest(folder/'toolchain.json')==manifest['sha256'],'toolchain manifest mismatch')
    checked_exes=0
    if check_executables:
        for report in (one,many,recovery):
            for build in report['builds']:
                require(digest(build['executable'])==build['executable_sha256'],'executable mismatch');checked_exes+=1
    return dict(status='qualified',original_status='failed',recovery_status='passed',
        report_pins=PINS,logical_mutants=12,original_detected=8,recovery_detected=4,
        source_identity='unchanged RTL, bench and all old helpers; new recovery harness/profile only',
        archived_evidence_files_verified=checked_logs,executables_rehashed=checked_exes,
        source_root_checked=source_root is not None,
        structure_test_note='The parent added an independent seventh geometry test after small-v1. Neither archived gate replaces its frozen six-test file; the recovery owns a separately source-hashed boundary proof.',
        validator_sha256=digest(__file__))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('failed_report',type=Path);parser.add_argument('recovery_report',type=Path)
    parser.add_argument('--source-root',type=Path);parser.add_argument('--check-executables',action='store_true')
    args=parser.parse_args()
    print(json.dumps(validate_composite(args.failed_report,args.recovery_report,args.source_root,args.check_executables),indent=2))


if __name__=='__main__':main()
