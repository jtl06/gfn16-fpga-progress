"""Read-only owner exploration replay; writes only a new requested receipt."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tarfile
from fpga.reference import stream27_canonical_image_native_v2 as native
from fpga.tools import native_gate_receipt_v1 as gate


def replay(aw,p):
    qid=f's4-canonical-aw{aw}-p{p}-q1-v2';done=json.loads((native.ROOT/'queue/done'/f'{qid}.json').read_text())
    package=done['package'];result=done['result'];root=Path(result['evidence']);worker=root/'output/native'
    native.model.need(result['status']=='needs_independent_review' and result['properties']['ExecMainStatus']=='0' and result['properties']['MainPID']=='0','CANON_ACTUAL_TERMINAL')
    packet=Path(package['archive']).parent;manifest=packet/'manifest.json'
    native.model.need(gate.sha(manifest)==package['manifest_sha256'] and gate.sha(packet/'package.tar.gz')==package['sha256'],'CANON_SELECTED_PACKAGE')
    contract=gate.make_contract(qid,manifest);fresh=gate.validate_result(contract,worker/'report.json',id=qid)
    saved=json.loads((native.ROOT/'queue/evidence'/qid/'gate-receipt.json').read_text())
    native.model.need(fresh==saved,'CANON_MACHINE_RECEIPT_REPLAY')
    m=json.loads(manifest.read_text());report=json.loads((worker/'report.json').read_text())
    for name,pin in native.PINS.items():native.model.need(report['sources'][name]==pin,'CANON_COMPONENT_SOURCE_PIN '+name)
    for negative in (False,True):
        name='canonical-negative-oracle' if negative else 'canonical-normal'
        row=next(x for x in report['steps'] if x['name']==name)
        native.validate((worker/row['log']).read_text(),(worker/row['stderr_log']).read_text(),row['returncode'],dict(aw=aw,p=p,negative=negative),{})
    generated=0
    with tarfile.open(worker/'generated-sources.tar.gz','r:gz') as archive:
        for member in archive:
            if member.isfile():
                generated+=1
                native.model.need(hashlib.sha256(archive.extractfile(member).read()).hexdigest()==report['generated_source_sha256'][member.name],'CANON_GENERATED_SHA')
    native.model.need(generated==len(report['generated_source_sha256']),'CANON_GENERATED_CLOSURE')
    with gzip.open(worker/'model.gz','rb') as stream:
        raw=stream.read();native.model.need(raw[:4]==b'\x7fELF' and hashlib.sha256(raw).hexdigest()==report['executable_sha256'],'CANON_ACTUAL_NATIVE_ELF_IDENTITY')
    for key in ('lint_admission','build_admission'):
        native.model.need(not report[key]['fatal_class_counts'] and not report[key]['unknown_class_counts'] and not report[key]['error_streams'],'CANON_DEFECT_CLASSES')
    return dict(id=qid,status='PASS_owner_exploration_replay',report_sha256=gate.sha(worker/'report.json'),
        gate_sha256=gate.sha(native.ROOT/'queue/evidence'/qid/'gate-receipt.json'),archive_sha256=result['archive_sha256'],
        sources=len(report['sources']),generated=generated,artifacts=len(report['artifacts']),
        invocation=result['properties']['InvocationID'],properties=result['properties'],
        counts=native.contracts(aw,p)['counts'],native_seconds=report['seconds'],
        steps=[dict(name=x['name'],seconds=x['seconds'],returncode=x['returncode']) for x in report['steps']],
        limits=report['limits'],tool_sha256=report['tool_sha256'],style_counts=report['lint_admission']['style_class_counts'],
        promotion_allowed=False,scope='Standalone AW5/AW8 materialized canonical-readback barrier only; no whole/core/fit/full-N promotion')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--aw',type=int,choices=(5,8),required=True)
    parser.add_argument('--p',type=int,choices=(8,16),required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=replay(args.aw,args.p)
    with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))
