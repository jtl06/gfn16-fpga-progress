"""Read-only point-launch component owner replay, never reruns native HDL."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tarfile
from fpga.reference import a10_point_launch_prepare_v3 as prep
from fpga.tools import native_gate_receipt_v1 as gate


def replay(aw,field):
    qid=f'a10-point-aw{aw}-f{field}-q1-v3';done=json.loads((prep.ROOT/'queue/done'/f'{qid}.json').read_text())
    package=done['package'];result=done['result'];root=Path(result['evidence']);worker=root/'output/native';packet=Path(package['archive']).parent
    prep.gen.parent.need(result['status']=='needs_independent_review' and result['properties']['ExecMainStatus']=='0' and result['properties']['MainPID']=='0','A10_POINT_NATIVE_TERMINAL')
    manifest=packet/'manifest.json';prep.gen.parent.need(gate.sha(manifest)==package['manifest_sha256'] and gate.sha(packet/'package.tar.gz')==package['sha256'],'A10_POINT_NATIVE_PACKAGE')
    contract=gate.make_contract(qid,manifest);fresh=gate.validate_result(contract,worker/'report.json',id=qid)
    saved=json.loads((prep.ROOT/'queue/evidence'/qid/'gate-receipt.json').read_text());prep.gen.parent.need(fresh==saved,'A10_POINT_GATE_REPLAY')
    report=json.loads((worker/'report.json').read_text());m=json.loads(manifest.read_text());expected,_=prep.role(aw,field)
    prep.gen.parent.need(all(m['build'][key]==expected['build'][key] for key in ('top','sv_sources','cpp_source','parameters','cflags')) and m['steps']==expected['steps'],'A10_POINT_EXACT_NATIVE_ROLE')
    for name,pin in prep.PINS.items():prep.gen.parent.need(report['sources'][name]==pin,'A10_POINT_NATIVE_SOURCE_PIN')
    generated={}
    with tarfile.open(worker/'generated-sources.tar.gz','r:gz') as archive:
        for member in archive:
            if member.isfile():
                prep.gen.parent.need(member.name not in generated,'A10_POINT_DUP_GENERATED')
                generated[member.name]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    prep.gen.parent.need(generated==report['generated_source_sha256'],'A10_POINT_GENERATED_CLOSURE')
    with gzip.open(worker/'model.gz','rb') as stream:raw=stream.read()
    prep.gen.parent.need(raw[:4]==b'\x7fELF' and hashlib.sha256(raw).hexdigest()==report['executable_sha256'],'A10_POINT_NATIVE_ELF')
    for key in ('lint_admission','build_admission'):
        prep.gen.parent.need(not report[key]['fatal_class_counts'] and not report[key]['unknown_class_counts'] and not report[key]['error_streams'],'A10_POINT_NATIVE_CLASSES')
    return dict(id=qid,status='PASS_owner_component_replay',report_sha256=gate.sha(worker/'report.json'),
        gate_sha256=gate.sha(prep.ROOT/'queue/evidence'/qid/'gate-receipt.json'),archive_sha256=result['archive_sha256'],
        sources=len(report['sources']),generated=len(generated),artifacts=len(report['artifacts']),
        invocation=result['properties']['InvocationID'],properties=result['properties'],
        ledger=prep.gen.ledger(aw),native_seconds=report['seconds'],
        steps=[dict(name=x['name'],seconds=x['seconds'],returncode=x['returncode']) for x in report['steps']],
        limits=report['limits'],tools=report['tool_sha256'],style_counts=report['lint_admission']['style_class_counts'],
        promotion_allowed=False,scope='Pointwise-only A10 launch component: no whole A-next/fullN/physical clock promotion')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--aw',type=int,choices=(5,8),required=True)
    parser.add_argument('--field',type=int,choices=(0,1,2),required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=replay(args.aw,args.field)
    with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))
