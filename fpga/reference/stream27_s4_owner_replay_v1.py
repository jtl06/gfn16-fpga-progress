"""Read-only S4 owner evidence replay; no HDL or numeric recomputation."""
import gzip
import hashlib
import json
from pathlib import Path
import tarfile
from fpga.tools import native_gate_receipt_v1 as gate

ROOT=Path(__file__).resolve().parents[1]


def replay(qid):
    done=json.loads((ROOT/'queue/done'/f'{qid}.json').read_text())
    package=done['package'];result=done['result'];worker=Path(result['evidence'])/'output/native'
    props=result['properties']
    gate.need(result['status']=='needs_independent_review' and props['ExecMainStatus']=='0' and props['MainPID']=='0','S4_ACTUAL_TERMINAL')
    packet=Path(package['archive']).parent;manifest=packet/'manifest.json'
    gate.need(gate.sha(manifest)==package['manifest_sha256'] and gate.sha(packet/'package.tar.gz')==package['sha256'],'S4_SELECTED_PACKAGE')
    fresh=gate.validate_result(gate.make_contract(qid,manifest),worker/'report.json',id=qid)
    saved=ROOT/'queue/evidence'/qid/'gate-receipt.json'
    gate.need(fresh==json.loads(saved.read_text()),'S4_MACHINE_RECEIPT_REPLAY')
    report=json.loads((worker/'report.json').read_text());generated={}
    with tarfile.open(worker/'generated-sources.tar.gz','r:gz') as archive:
        for member in archive:
            gate.need(member.isfile() and member.name not in generated,'S4_GENERATED_REGULAR_UNIQUE')
            generated[member.name]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    gate.need(generated==report['generated_source_sha256'],'S4_GENERATED_CLOSURE')
    with gzip.open(worker/'model.gz','rb') as stream:
        raw=stream.read();gate.need(raw[:4]==b'\x7fELF' and hashlib.sha256(raw).hexdigest()==report['executable_sha256'],'S4_ACTUAL_NATIVE_ELF')
    for key in ('lint_admission','build_admission'):
        gate.need(not report[key]['fatal_class_counts'] and not report[key]['unknown_class_counts'] and not report[key]['error_streams'],'S4_DEFECT_CLASSES')
    return dict(id=qid,status='PASS_owner_exploration_replay',report_sha256=gate.sha(worker/'report.json'),
        gate_sha256=gate.sha(saved),candidate_source_sha256=fresh['candidate_source_sha256'],
        archive_sha256=result['archive_sha256'],sources=len(report['sources']),generated=len(generated),artifacts=len(report['artifacts']),
        properties=props,limits=report['limits'],tool_sha256=report['tool_sha256'],style_counts=report['lint_admission']['style_class_counts'],
        steps=[dict(name=row['name'],returncode=row['returncode'],seconds=row['seconds'],
            stdout=(worker/row['log']).read_text() if row['name'] not in ('lint','build') else None) for row in report['steps'][5:]],
        promotion_allowed=False,scope='Source-bound dependency and owner replay only; independent promotion review remains required')


if __name__=='__main__':
    import sys
    print(json.dumps([replay(qid) for qid in sys.argv[1:]],indent=2))
