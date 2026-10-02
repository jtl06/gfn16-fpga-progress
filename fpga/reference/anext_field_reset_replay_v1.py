"""Read-only reset component archive/typedgate consumption, not execution."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path,PurePosixPath
import tarfile
from fpga.reference import anext_field_reset_native_v1 as native
from fpga.tools import native_gate_receipt_v1 as gate


def replay(aw):
    native.verify();r=native.probe.role_config(aw);identifier=f'anext-field-reset-aw{aw}-q1-v1'
    done=json.loads((native.ROOT/'queue/done'/f'{identifier}.json').read_text());package=done['package'];result=done['result']
    worker=Path(result['evidence'])/'output/native'
    native.model.need(result['status']=='needs_independent_review' and result['properties']['ExecMainStatus']=='0' and
        result['properties']['MainPID']=='0','ANEXT_RESET_ACTUAL_TERMINAL')
    packet=Path(package['archive']).parent;manifest=packet/'manifest.json'
    native.model.need(gate.sha(manifest)==package['manifest_sha256'] and gate.sha(packet/'package.tar.gz')==package['sha256'],
                     'ANEXT_RESET_SELECTED_IMMUTABLE_PACKAGE')
    fresh=gate.validate_result(gate.make_contract(identifier,manifest),worker/'report.json',id=identifier)
    native.model.need(fresh==json.loads((native.ROOT/'queue/evidence'/identifier/'gate-receipt.json').read_text()),'ANEXT_RESET_MACHINE_GATE_REPLAY')
    report=json.loads((worker/'report.json').read_text())
    for name,pin in native.PINS.items():native.model.need(report['sources'][name]==pin,'ANEXT_RESET_NATIVE_SOURCE '+name)
    for case in r['cases']:
        row=next(x for x in report['steps'] if x['name']=='reset-'+case['name'])
        native.validate((worker/row['log']).read_text(),(worker/row['stderr_log']).read_text(),row['returncode'],dict(aw=aw,case=case['name']),{})
    expected=report['generated_source_sha256'];seen=set()
    with tarfile.open(worker/'generated-sources.tar.gz','r:gz') as archive:
        for member in archive:
            p=PurePosixPath(member.name)
            native.model.need(member.isfile() and not member.issparse() and not p.is_absolute() and '..' not in p.parts and
                member.name not in seen and member.name in expected,'ANEXT_RESET_GENERATED_REGULAR_MEMBER')
            seen.add(member.name);native.model.need(hashlib.sha256(archive.extractfile(member).read()).hexdigest()==expected[member.name],
                'ANEXT_RESET_GENERATED_SOURCE_HASH')
    native.model.need(seen==set(expected),'ANEXT_RESET_GENERATED_EXACT_CLOSURE')
    with gzip.open(worker/'model.gz','rb') as stream:
        raw=stream.read();native.model.need(raw[:4]==b'\x7fELF' and hashlib.sha256(raw).hexdigest()==report['executable_sha256'],
            'ANEXT_RESET_ELF_HASH_NOT_LOCAL_EXECUTION')
    for key in ('lint_admission','build_admission'):
        native.model.need(not report[key]['fatal_class_counts'] and not report[key]['unknown_class_counts'] and not report[key]['error_streams'],
                         'ANEXT_RESET_NATIVE_DEFECT_CLASSES')
    return dict(id=identifier,status='PASS_owner_exploration_replay',report_sha256=gate.sha(worker/'report.json'),
        gate_sha256=gate.sha(native.ROOT/'queue/evidence'/identifier/'gate-receipt.json'),archive_sha256=result['archive_sha256'],
        sources=len(report['sources']),generated=len(seen),artifacts=len(report['artifacts']),invocation=result['properties']['InvocationID'],
        calendar=r['calendar'],geometry=r['geometry'],native_seconds=report['seconds'],limits=report['limits'],tool_sha256=report['tool_sha256'],
        style_counts=report['lint_admission']['style_class_counts'],promotion_allowed=False,whole_integration_requested=False,fit_requested=False,
        scope='Actual three-field transfer/blockroute/RAM/Mont/ROM reset helper only; no realengineheader/cache/internalBFwrite or whole/physical clock claim.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--aw',type=int,choices=(5,8),required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();result=replay(args.aw)
    with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))
