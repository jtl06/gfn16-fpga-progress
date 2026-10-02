"""Collected connected-engine evidence only; no coordinator HDL/numeric rerun."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tarfile
from fpga.reference import a10_upper_sum_engine_prepare_v2 as prep
from fpga.tools import native_gate_receipt_v1 as gate


def replay(aw, field):
    prep.gen.need(type(aw) is int and aw in (5,8,16) and type(field) is int and field in (0,1,2),
                  'A10_UPPER_NATIVE_ROLE')
    qid=f'a10-upper-engine-aw{aw}-f{field}-q1-v2'
    done=json.loads((prep.ROOT/'queue/done'/f'{qid}.json').read_text()); package=done['package']; result=done['result']
    need=prep.gen.need
    need(result['status']=='needs_independent_review' and result['properties']['ExecMainStatus']=='0' and
         result['properties']['MainPID']=='0','A10_UPPER_ACTUAL_TERMINAL')
    packet=Path(package['archive']).parent; manifest=packet/'manifest.json'; worker=Path(result['evidence'])/'output/native'
    need(gate.sha(manifest)==package['manifest_sha256'] and gate.sha(packet/'package.tar.gz')==package['sha256'],
         'A10_UPPER_NATIVE_PACKAGE')
    gate_path=prep.ROOT/'queue/evidence'/qid/'gate-receipt.json'
    fresh=gate.validate_result(gate.make_contract(qid,manifest),worker/'report.json',id=qid)
    need(fresh==json.loads(gate_path.read_text()),'A10_UPPER_NATIVE_GATE_REPLAY')
    report=json.loads((worker/'report.json').read_text()); m=json.loads(manifest.read_text())
    expected,_=prep.role(aw,field,allow_full_constants=True)
    need(all(m['build'][key]==expected['build'][key] for key in ('top','sv_sources','cpp_source','parameters','cflags')) and
         m['steps']==expected['steps'],'A10_UPPER_NATIVE_EXACT_ROLE')
    need(all(report['sources'][name]==pin for name,pin in prep.PINS.items()),'A10_UPPER_NATIVE_SOURCE_PINS')
    generated={}
    with tarfile.open(worker/'generated-sources.tar.gz','r:gz') as archive:
        for member in archive:
            if member.isfile():
                need(member.name not in generated,'A10_UPPER_DUP_GENERATED')
                generated[member.name]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    need(generated==report['generated_source_sha256'],'A10_UPPER_NATIVE_GENERATED_CLOSURE')
    with gzip.open(worker/'model.gz','rb') as stream:
        raw=stream.read()
    need(raw[:4]==b'\x7fELF' and hashlib.sha256(raw).hexdigest()==report['executable_sha256'],'A10_UPPER_NATIVE_ELF')
    for key in ('lint_admission','build_admission'):
        need(not report[key]['fatal_class_counts'] and not report[key]['unknown_class_counts'] and
             not report[key]['error_streams'],'A10_UPPER_NATIVE_CLASSES')
    return dict(id=qid,status='PASS_owner_connected_component_replay',report_sha256=gate.sha(worker/'report.json'),
        gate_sha256=gate.sha(gate_path),archive_sha256=result['archive_sha256'],sources=len(report['sources']),
        generated=len(generated),artifacts=len(report['artifacts']),invocation=result['properties']['InvocationID'],
        properties=result['properties'],native_seconds=report['seconds'],normal_stdout=m['steps'][0]['expected_stdout'],
        typed_counter_negative=m['steps'][1],source_pins=prep.PINS,
        steps=[dict(name=x['name'],seconds=x['seconds'],returncode=x['returncode']) for x in report['steps']],
        limits=report['limits'],tools=report['tool_sha256'],style_counts=report['lint_admission']['style_class_counts'],
        native_standalone_phase_ledger=prep.small.gen.ledger(aw),cell_input_to_output=5,
        engine_cycle_delta=0,whole_controller_cycles_still_derived=True,
        promotion_allowed=False,scope='Connected single-field A10 upper normalization register successor; no whole/physical/clock/PRP promotion.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--aw',type=int,choices=(5,8,16),required=True)
    parser.add_argument('--field',type=int,choices=(0,1,2),required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=replay(args.aw,args.field)
    with args.output.open('x') as stream:
        json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))
