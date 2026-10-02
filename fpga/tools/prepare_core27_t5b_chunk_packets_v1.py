"""Source-only full batch packaging; never admit or launch a long command.

Creates20 immutable static GCP packet variants for ten exact100-square chunks.
No continuous packet is silently squeezed into the short runner. Draft global
tickets have NO runnable package until a measured short/runtime gate is bound.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PACKAGE='tools/native_class_package_v2.py'
PACKAGE_SHA='03b6a81aa7d465487da97f854a79e9e43a19c9c637db6178587cfac02476f604'


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def dump(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')


def prepare(manifests,budget_file,output):
    if sha(ROOT/PACKAGE)!=PACKAGE_SHA:raise ValueError('pinned shared class packager')
    spec=importlib.util.spec_from_file_location('_soak_chunk_packager',ROOT/PACKAGE)
    worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
    output=Path(output).resolve()
    if output.exists():raise ValueError('fresh chunk batch output')
    manifests=Path(manifests).resolve();budget_file=Path(budget_file).resolve()
    original=json.loads((manifests/'chunk-00/serial-manifest.json').read_text())
    wanted=original['soak']['case_id']
    if wanted!='2730e05de298ecbf5d7125acb7d6859b581b21ed8c84fb1bbfd7d3aaccd007ba':
        raise ValueError('exact full T5b reference case')
    output.mkdir(parents=True);prepared=[]
    for index in range(10):
        segment=f'chunk-{index:02d}';component=output/segment;component.mkdir()
        manifest_file=manifests/segment/'serial-manifest.json'
        manifest=json.loads(manifest_file.read_text())
        if manifest['soak']['case_id']!=wanted or len(manifest['steps'])!=1 \
            or manifest['steps'][0]['validator']['config']!={'negative':'none'}:
            raise ValueError('normal-only exact T5b chunk contract')
        packages=[]
        logical=f'soak-t5b-aw16-{segment}-q3-v1'
        for pair in ('01','23'):
            profile=f'gcp-c4d-static{pair}-v1';job=logical+'-p'+pair;packet=component/('p'+pair)
            result=worker.prepare(manifest_file,manifests/segment/'source/fpga',profile,job,'run',packet,budget_file)
            packages.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
                ticket_sha256=result['ticket_sha256'],manifest_sha256=sha(packet/'manifest.json'),
                worker_id=job,profile=profile,native_root=result['native_root'],runner=PACKAGE,
                runner_sha256=PACKAGE_SHA,stager=str(ROOT/'tools/native_package_v4.py'),
                stager_sha256=sha(ROOT/'tools/native_package_v4.py'),
                stager_dependencies=[dict(path=str(ROOT/'tools'/name),sha256=sha(ROOT/'tools'/name))
                                     for name in ('native_package_v3.py','native_package_v2.py')],max_seconds=3700))
        draft=dict(schema='gfn16-global-ticket-v1',id=logical,owner='soak-chunks',
            created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
            tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
            resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),est_minutes=30,promotion_bound=True,
            after=['soak-t5b-aw16-short-native-q3-v1'],on='PASS_expected_contracts',
            blocked_reason='Needs actual T5b short PASS and source-bound measured100-square duration admission; drafts contain no runnable package.',
            candidate_packages=packages,scope='Independent exact100-square arithmetic chunk; never uninterrupted1000 coverage.')
        dump(component/'draft-ticket.json',draft)
        prepared.append(dict(segment=segment,draft_ticket=str(component/'draft-ticket.json'),
            draft_ticket_sha256=sha(component/'draft-ticket.json'),packages=packages))
    result=dict(status='prepared20_immutable_chunk_variants_not_admitted_or_dispatched',case_id=wanted,
        budget_sha256=sha(budget_file),chunks=prepared,continuous_packet_prepared=False,
        arithmetic_executed=False,HDL_executed=False)
    dump(output/'prepare-receipt.json',result);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('manifests','budget-file','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();result=prepare(args.manifests,args.budget_file,args.output)
    print(json.dumps({k:v for k,v in result.items() if k!='chunks'},indent=2))
