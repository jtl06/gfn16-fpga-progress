"""Read-only matched component fit consumption, no native/tool rerun."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
from fpga.reference import a10_upper_sum_generate_v2 as gen

ROOT = gen.ROOT


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def consume():
    gen.measured_guard()
    dossier = ROOT/gen.DOSSIER; evidence = dossier/'evidence'
    receipt = json.loads((dossier/'receipt.json').read_text())
    inventory_path = evidence/'collection/collection-inventory-v1.json'
    gen.need(file_sha(inventory_path) == receipt['inventory_sha256'] and
             file_sha(dossier/'native-reports.tar.gz') == receipt['archive']['sha256'] and
             receipt['native_job_succeeded'] and receipt['terminal_proven'] and not receipt['findings'],
             'A10_POINT_FIT_TERMINAL_ARCHIVE')
    inventory = json.loads(inventory_path.read_text()); archived = {}
    for name, record in inventory['files'].items():
        path = evidence/name
        gen.need(path.is_file() and not path.is_symlink() and path.stat().st_size == record['size'] and
                 file_sha(path) == record['sha256'], 'A10_POINT_FIT_CLOSED_FILE '+name)
    with tarfile.open(dossier/'native-reports.tar.gz', 'r:gz') as archive:
        for member in archive:
            gen.need(member.isfile() and not member.issparse() and member.name not in archived and
                     not PurePosixPath(member.name).is_absolute() and '..' not in PurePosixPath(member.name).parts,
                     'A10_POINT_FIT_REGULAR_ARCHIVE')
            archived[member.name] = hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    expected = {name: record['sha256'] for name,record in inventory['files'].items()}
    expected['collection/collection-inventory-v1.json'] = receipt['inventory_sha256']
    gen.need(archived == expected and inventory['count'] == 40, 'A10_POINT_FIT_EXACT_41_MEMBER_CLOSURE')
    project = evidence/'project'; m = json.loads((project/'manifest.json').read_text())
    context = json.loads((project/'execution-context.json').read_text())
    gen.need(file_sha(project/'manifest.json') == context['manifest_sha256'] and
             context['source_sha256'] == m['source_sha256'], 'A10_POINT_FIT_NATIVE_SOURCE_CONTEXT')
    for name, pin in m['source_sha256'].items():
        gen.need(file_sha(project/'rtl'/name) == pin, 'A10_POINT_FIT_ALL_RTL_PINS')
    for name in ('probe.sdc', 'probe.qpf', 'run.tcl'):
        gen.need(file_sha(project/name) == m['control_sha256'][name] == context['control_sha256'][name],
                 'A10_POINT_FIT_UNCHANGED_CONTROLS')
    prepared = ROOT/'results/throughput-20260929/a10-point-field-probe-v3/project-workers6'
    gen.need((project/'probe.qsf').read_text() == (prepared/'probe.qsf').read_text()+
             'set_global_assignment -name LAST_QUARTUS_VERSION "26.1.0 Pro Edition"\n',
             'A10_POINT_FIT_ONLY_VENDOR_VERSION_APPEND')
    gen.need(file_sha(prepared/'probe.qsf') == m['control_sha256']['probe.qsf'], 'A10_POINT_FIT_ORIGINAL_QSF_PIN')
    ledger = json.loads((ROOT/gen.PATH_LEDGER).read_text())
    final = (project/'output_files/probe.fit.summary').read_text()
    registers = int(re.findall(r'^Total registers : (\d+)$', final, re.M)[0])
    gen.need(registers == 59357, 'A10_POINT_FIT_FINAL_REGISTER_COUNT')
    old = json.loads((ROOT/'results/throughput-20260929/a10-aw16-registered-aws-plain-v1/path-ledger-v1.json').read_text())
    return dict(schema='a10-point-fit-consumption-v3', scope='matched_one_field_component_only',
        status='SOURCE_BOUND_NATIVE_COMPLETE_TIMING_FAIL', source_manifest_sha256=file_sha(project/'manifest.json'),
        raw_STA_sha256=gen.STA_SHA, native_receipt_sha256=gen.RECEIPT_SHA,
        raw_archive_sha256=receipt['archive']['sha256'], source_files=len(m['source_sha256']),
        collected_files=40, archived_regular_files=41, QDB_local=False,
        QDB_scope='Native final inventory retained; no local private DB or independent DB timing replay.',
        invocation=receipt['invocation_id'], native_manager=receipt['native_journal_proof'],
        slacks=dict(setup=-2.522, hold=0.017, minimum_pulse_width=3.337),
        parent_slacks=dict(setup=old['setup']['paths'][0]['slack_ns'], hold=old['hold']['paths'][0]['slack_ns']),
        setup_delta_ns=1.184,
        resources=dict(needed_ALM=88494, raw_placed_ALM=96503, LAB=11809,
                       final_registers=registers, place_registers=ledger['native_resources']['registers'],
                       M20K=322, DSP=128, RAM_bits=5635988),
        matched_delta=dict(needed_ALM=-1012, raw_placed_ALM=-866, LAB=166,
                           final_registers=2033, M20K=0, DSP=0, RAM_bits=0),
        observed_setup_sources=[row['source'] for row in ledger['setup']['paths']],
        observed_setup_destinations=[row['destination'] for row in ledger['setup']['paths']],
        worst=ledger['setup']['paths'][0], source_only_next_ledger=gen.ledger(),
        next='Isolated upper canonical sum/rhs prereg replacing one output alignmentFF; require actual k+5/II1/math/bubble/reset gates before newfit.',
        reported_Fmax_MHz=95.04, audited_clock=False, whole_core_clock_claim=False, promotion_allowed=False,
        limitation='Finite final MCMM path samples, not exhaustive crossings. Matched component constraints/seed/libs preserved; placement changed. Needed/placed ALM and directLAB differ; no blanket resource improvement or causal host-runtime claim.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); result = consume()
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps(result, indent=2))
