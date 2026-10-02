"""Owner replay of collected F3 field evidence, no HDL/full-N rerun here."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
from fpga.reference import a10_writeback_launch_prepare_v1 as prep
from fpga.tools import native_gate_receipt_v1 as gate


def replay(aw, field):
    prep.gen.upper.need(type(aw) is int and aw in (5,8,16) and type(field) is int and field in (0,1,2), 'A10_F3_REPLAY_ROLE')
    qid=f'a10-writeback-aw{aw}-f{field}-q1-v1'; need=prep.gen.upper.need
    path=prep.ROOT/'queue/done'/f'{qid}.json'; need(path.is_file(), 'A10_F3_ACTUAL_TERMINAL_REQUIRED')
    done=json.loads(path.read_text()); package=done['package']; result=done['result']
    need(result['status']=='needs_independent_review' and result['properties']['ExecMainStatus']=='0' and
         result['properties']['MainPID']=='0', 'A10_F3_NATIVE_TERMINAL_PASS')
    packet=Path(package['archive']).parent; manifest=packet/'manifest.json'; worker=Path(result['evidence'])/'output/native'
    need(gate.sha(manifest)==package['manifest_sha256'] and gate.sha(packet/'package.tar.gz')==package['sha256'],
         'A10_F3_NATIVE_PACKAGE_IDENTITY')
    gate_path=prep.ROOT/'queue/evidence'/qid/'gate-receipt.json'
    fresh=gate.validate_result(gate.make_contract(qid,manifest),worker/'report.json',id=qid)
    need(fresh==json.loads(gate_path.read_text()) and fresh['status']=='PASS_expected_contracts', 'A10_F3_TYPED_NATIVE_GATE')
    report=json.loads((worker/'report.json').read_text()); m=json.loads(manifest.read_text())
    expected,_=prep.role(aw,field,allow_full_constants=True)
    need(all(m['build'][key]==expected['build'][key] for key in ('top','sv_sources','cpp_source','parameters','cflags')) and
         m['steps']==expected['steps'], 'A10_F3_EXACT_COMPILED_ROLE')
    need(all(report['sources'][name]==pin for name,pin in prep.PINS.items()), 'A10_F3_NATIVE_FROZEN_SOURCE_PINS')
    generated={}
    with tarfile.open(worker/'generated-sources.tar.gz','r:gz') as archive:
        for member in archive:
            if member.isfile():
                need(member.name not in generated and not member.issparse() and not PurePosixPath(member.name).is_absolute() and
                     '..' not in PurePosixPath(member.name).parts, 'A10_F3_REGULAR_GENERATED_SOURCE')
                generated[member.name]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
            else: need(member.isdir(), 'A10_F3_NO_GENERATED_LINKS')
    need(generated==report['generated_source_sha256'], 'A10_F3_EXACT_GENERATED_CLOSURE')
    with gzip.open(worker/'model.gz','rb') as stream: raw=stream.read()
    need(raw[:4]==b'\x7fELF' and hashlib.sha256(raw).hexdigest()==report['executable_sha256'], 'A10_F3_NATIVE_ELF_IDENTITY_ONLY')
    for key in ('lint_admission','build_admission'):
        need(not report[key]['fatal_class_counts'] and not report[key]['unknown_class_counts'] and not report[key]['error_streams'],
             'A10_F3_FATAL_CLASSES_REJECTED')
    return dict(schema='a10-writeback-owner-native-v1',id=qid,status='PASS_owner_component_replay',
        report_sha256=gate.sha(worker/'report.json'),gate_sha256=gate.sha(gate_path),archive_sha256=result['archive_sha256'],
        sources=len(report['sources']),generated=len(generated),artifacts=len(report['artifacts']),
        invocation=result['properties']['InvocationID'],properties=result['properties'],source_pins=prep.PINS,
        normal_stdout=m['steps'][0]['expected_stdout'],typed_parent_counter_negative=m['steps'][1],
        steps=[dict(name=x['name'],seconds=x['seconds'],returncode=x['returncode']) for x in report['steps']],
        limits=report['limits'],tools=report['tool_sha256'],native_seconds=report['seconds'],
        style_counts=report['lint_admission']['style_class_counts'],
        native_standalone_phase_ledger=prep.gen.ledger(aw),pending_cancel_and_recovery_cases=4,
        whole_controller_cycle_value_still_derived=True,promotion_allowed=False,hold_repair_claim=False,
        scope='Single-field internal write launch; unchanged arithmetic/root/profile/idlehost with actualcommit counter and pendingreset/abort RAMchecks. No whole/clock/physical/PRP promotion.')


if __name__=='__main__':
    args=argparse.ArgumentParser(description=__doc__);args.add_argument('--aw',type=int,choices=(5,8,16),required=True)
    args.add_argument('--field',type=int,choices=(0,1,2),required=True);args.add_argument('--output',type=Path,required=True)
    parsed=args.parse_args();result=replay(parsed.aw,parsed.field)
    with parsed.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(id=result['id'],status=result['status'],report_sha256=result['report_sha256'],normal_stdout=result['normal_stdout']),indent=2))
