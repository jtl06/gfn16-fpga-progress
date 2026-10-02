"""Owner read-only archive/math/edge typed gate consumption, no native rerun."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path,PurePosixPath
import tarfile
from fpga.reference import anext_cancel_native_v1 as native
from fpga.tools import native_gate_receipt_v1 as gate


def replay(aw):
    native.counts(aw);native.verify();identifier=f'anext-cancel-host-aw{aw}-q1-v1'
    done=json.loads((native.ROOT/'queue/done'/f'{identifier}.json').read_text())
    package=done['package'];result=done['result'];worker=Path(result['evidence'])/'output/native'
    native.gen.need(result['status']=='needs_independent_review' and result['properties']['ExecMainStatus']=='0' and
        result['properties']['MainPID']=='0','ANEXT_CANCEL_ACTUAL_TERMINAL')
    packet=Path(package['archive']).parent;manifest=packet/'manifest.json'
    native.gen.need(gate.sha(manifest)==package['manifest_sha256'] and gate.sha(packet/'package.tar.gz')==package['sha256'],
        'ANEXT_CANCEL_SELECTED_IMMUTABLE_PACKAGE')
    fresh=gate.validate_result(gate.make_contract(identifier,manifest),worker/'report.json',id=identifier)
    saved=json.loads((native.ROOT/'queue/evidence'/identifier/'gate-receipt.json').read_text())
    native.gen.need(fresh==saved,'ANEXT_CANCEL_MACHINE_GATE_REPLAY')
    report=json.loads((worker/'report.json').read_text())
    for name,pin in native.PINS.items():native.gen.need(report['sources'][name]==pin,'ANEXT_CANCEL_NATIVE_SOURCE '+name)
    for negative in (False,True):
        row=next(step for step in report['steps'] if step['name']==('cancel-negative-oracle' if negative else 'cancel-host-normal'))
        native.validate((worker/row['log']).read_text(),(worker/row['stderr_log']).read_text(),row['returncode'],dict(aw=aw,negative=negative),{})
    expected=report['generated_source_sha256'];seen=set()
    with tarfile.open(worker/'generated-sources.tar.gz','r:gz') as archive:
        for member in archive:
            p=PurePosixPath(member.name)
            native.gen.need(member.isfile() and not member.issparse() and not p.is_absolute() and '..' not in p.parts and
                member.name not in seen and member.name in expected,'ANEXT_CANCEL_GENERATED_REGULAR_MEMBER')
            seen.add(member.name)
            native.gen.need(hashlib.sha256(archive.extractfile(member).read()).hexdigest()==expected[member.name],
                'ANEXT_CANCEL_GENERATED_SOURCE_HASH')
    native.gen.need(seen==set(expected),'ANEXT_CANCEL_GENERATED_EXACT_CLOSURE')
    with gzip.open(worker/'model.gz','rb') as stream:
        raw=stream.read();native.gen.need(raw[:4]==b'\x7fELF' and hashlib.sha256(raw).hexdigest()==report['executable_sha256'],
            'ANEXT_CANCEL_ELF_HASH_NOT_LOCAL_EXECUTION')
    for key in ('lint_admission','build_admission'):
        native.gen.need(not report[key]['fatal_class_counts'] and not report[key]['unknown_class_counts'] and not report[key]['error_streams'],
            'ANEXT_CANCEL_NATIVE_DEFECT_CLASSES')
    return dict(id=identifier,status='PASS_owner_exploration_replay',report_sha256=gate.sha(worker/'report.json'),
        gate_sha256=gate.sha(native.ROOT/'queue/evidence'/identifier/'gate-receipt.json'),archive_sha256=result['archive_sha256'],
        sources=len(report['sources']),generated=len(seen),artifacts=len(report['artifacts']),invocation=result['properties']['InvocationID'],
        counts=native.counts(aw),native_seconds=report['seconds'],limits=report['limits'],tool_sha256=report['tool_sha256'],
        style_counts=report['lint_admission']['style_class_counts'],promotion_allowed=False,
        scope='Old/new real host/RAM pair with independent signed-image/base oracle; no square math, whole recovery or physical clock claim.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--aw',type=int,choices=(5,8),required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();result=replay(args.aw)
    with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))
