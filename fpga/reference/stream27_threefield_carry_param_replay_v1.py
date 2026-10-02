"""Read-only owner replay; all underlying source/ELF artifacts remain retained."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path,PurePosixPath
import tarfile
from . import stream27_threefield_carry_param_native_v1 as native
from . import stream27_threefield_carry_param_prepare_v1 as prepare
from fpga.tools import native_gate_receipt_v1 as gate

def archive_closure(path,expected):
    seen=set()
    with tarfile.open(path,'r:gz') as archive:
        for member in archive:
            relative=PurePosixPath(member.name)
            native.need(member.isfile() and not relative.is_absolute() and '..' not in relative.parts and member.name not in seen and member.name in expected,'S4_PARAM_ARCHIVE_MEMBER')
            seen.add(member.name)
            native.need(hashlib.sha256(archive.extractfile(member).read()).hexdigest()==expected[member.name],'S4_PARAM_ARCHIVE_SHA')
    native.need(seen==set(expected),'S4_PARAM_ARCHIVE_CLOSURE');return len(seen)

def replay(aw,p):
    native.verify();identifier=prepare.identifier(aw,p)
    done=json.loads((native.ROOT/'queue/done'/f'{identifier}.json').read_text());package=done['package'];result=done['result'];worker=Path(result['evidence'])/'output/native'
    native.need(result['status']=='needs_independent_review' and result['properties']['ExecMainStatus']=='0' and result['properties']['MainPID']=='0','S4_PARAM_ACTUAL_TERMINAL')
    packet=Path(package['archive']).parent;manifest_path=packet/'manifest.json'
    native.need(gate.sha(manifest_path)==package['manifest_sha256'] and gate.sha(packet/'package.tar.gz')==package['sha256'],'S4_PARAM_SELECTED_PACKAGE')
    manifest=json.loads(manifest_path.read_text());profile=manifest['carry_param']
    native.need(profile['aw']==aw and profile['p']==p and manifest['build']['parameters']==dict(AW=aw,P=p,CONTEXTS=1),'S4_PARAM_ACTUAL_CONFIGURATION')
    fresh=gate.validate_result(gate.make_contract(identifier,manifest_path),worker/'report.json',id=identifier)
    native.need(fresh==json.loads((native.ROOT/'queue/evidence'/identifier/'gate-receipt.json').read_text()),'S4_PARAM_MACHINE_REPLAY')
    expected,files=prepare.role(aw,p)
    native.need(manifest['sources']==expected['sources'] and manifest['carry_param']==expected['carry_param'],'S4_PARAM_FROZEN_SOURCE_REEMIT')
    report=json.loads((worker/'report.json').read_text())
    for name,pin in profile['generated_sha256'].items():native.need(report['sources']['rtl/'+name]==pin,'S4_PARAM_RTL_PIN '+name)
    for mode in ('normal','minimum','oracle','owner'):
        row=next(s for s in report['steps'] if s['name']=='param-carry-'+mode)
        native.validate((worker/row['log']).read_text(),(worker/row['stderr_log']).read_text(),row['returncode'],dict(aw=aw,p=p,mode=mode),{})
    sources=archive_closure(worker/'sources.tar.gz',report['sources']);generated=archive_closure(worker/'generated-sources.tar.gz',report['generated_source_sha256'])
    with gzip.open(worker/'model.gz','rb') as stream:
        raw=stream.read();native.need(raw[:4]==b'\x7fELF' and hashlib.sha256(raw).hexdigest()==report['executable_sha256'],'S4_PARAM_ELF_IDENTITY')
    for key in ('lint_admission','build_admission'):
        native.need(not report[key]['fatal_class_counts'] and not report[key]['unknown_class_counts'] and not report[key]['error_streams'],'S4_PARAM_DEFECT_CLASSES')
    return dict(id=identifier,status='PASS_owner_exploration_replay',aw=aw,p=p,report_sha256=gate.sha(worker/'report.json'),
        gate_sha256=gate.sha(native.ROOT/'queue/evidence'/identifier/'gate-receipt.json'),sources=sources,generated=generated,
        artifacts=len(report['artifacts']),invocation=result['properties']['InvocationID'],properties=result['properties'],counts=native.counts(aw,p),
        geometry=profile['geometry'],source_sha256=profile['source_sha256'],generated_sha256=profile['generated_sha256'],
        native_seconds=report['seconds'],limits=report['limits'],tool_sha256=report['tool_sha256'],style_counts=report['lint_admission']['style_class_counts'],
        steps=[dict(name=s['name'],seconds=s['seconds'],returncode=s['returncode']) for s in report['steps']],
        promotion_allowed=False,scope=profile['scope'])

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--aw',type=int,choices=(5,8),required=True);parser.add_argument('--p',type=int,choices=(8,16),required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();value=replay(args.aw,args.p)
    with args.output.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    print(json.dumps(value,indent=2))
