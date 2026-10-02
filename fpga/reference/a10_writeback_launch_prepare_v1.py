"""Finite F3 AW5→AW8→AW16 field chains; shared dispatcher owns execution."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from fpga.reference import a10_writeback_launch_generate_v1 as gen
from fpga.reference import a10_upper_sum_engine_prepare_v2 as parent

ROOT = gen.ROOT
SELF = 'reference/a10_writeback_launch_prepare_v1.py'
TEST = 'tests/test_a10_writeback_launch_prepare_v1.py'
PINS = {gen.TARGET:'f200303571a01042c17e5c8a5b4070bd94d810503bc05285523cec370cda2ace',
        gen.NATIVE_HOST:'6e35df0a9816a04163afac904b1262a0927ffd29ecfe39e9e37eacfe6f302f88',
        gen.CPP:'b2f675ca9ea0375343f851187592d6d90434513f647c4ba368ae321edd2a5739',
        'reference/a10_writeback_launch_generate_v1.py':'fc3760529ddcc12044a531f9a39d89faf5e26dc0f7a3c7b611d1ea5f628d1f03'}


def verify():
    for name,pin in PINS.items():
        gen.upper.need(gen.sha((ROOT/name).read_bytes()) == pin, 'A10_F3_FROZEN_PIN '+name)
    gen.upper.need((ROOT/gen.TARGET).read_text() == gen.source() and
                   (ROOT/gen.NATIVE_HOST).read_text() == gen.native_host_source() and
                   (ROOT/gen.CPP).read_text() == gen.cpp_source(), 'A10_F3_EXACT_SOURCE_GENERATION')


def role(aw, field, *, allow_full_constants=False):
    gen.upper.need(type(aw) is int and aw in (5,8,16) and type(field) is int and field in (0,1,2),
                   'A10_F3_FINITE_ROLE')
    verify()
    m,files = parent.role(aw,field,allow_full_constants=allow_full_constants)
    for name in (*PINS,SELF,TEST,'tests/test_a10_writeback_launch_generate_v1.py',gen.MEASURED,gen.RECEIPT):
        files[name] = (ROOT/name).read_bytes()
    m['build']['sv_sources'] = [gen.TARGET if name == gen.PARENT else gen.NATIVE_HOST if name == gen.HOST else name
                               for name in m['build']['sv_sources']]
    m['build']['cpp_source'] = gen.CPP
    f = parent.small.batch.old.math.FIELDS[field]; counts = gen.ledger(aw)
    normal = (f'A10_WRITEBACK_ENGINE_PASS aw={aw} field={f.p} cases=5 operations=15 residues={counts["residues"]} '
        f'cycles={counts["engine_work_cycles"]} profile_words=4 pending_cancels=4 recovery_operations=4 '
        f'recovery_residues={4*(1<<aw)} recovery_cycles={4*counts["transform_cycles"]}\n')
    m['steps'] = [dict(name='writeback-normal-math-and-pending-cancel',argv=['{exe}'],expected_returncode=0,
                      expected_stdout=normal,expected_stderr=''),
                  dict(name='writeback-negative-parent-counter',argv=['{exe}','--negative-counter'],
                       expected_returncode=1,expected_stdout='',expected_stderr='A10_WRITEBACK_COUNTER_NEGATIVE_REJECT\n')]
    m['sources'] = {name:gen.sha(raw) for name,raw in files.items()}
    m['source_root'] = '/not-a-dispatch-path/a10-writeback/fpga'
    m['output_parent'] = '/not-a-dispatch-path/a10-writeback/output'
    m['scope'] = 'F3 internal bank-local write launch with actual physicalcommit/drain+1 per phase; exact upper arithmetic/root/profile/idlehost parent; component only, no hold/whole/clock promotion.'
    m.pop('point_launch',None); m.pop('upper_sum_launch',None)
    m['writeback_launch'] = dict(source_pins=PINS,measured_parent_path_ledger_sha256=gen.MEASURED_SHA,
        measured_parent_receipt_sha256=gen.RECEIPT_SHA,source_only_ledger=counts,
        raw_BF_cell_k_plus=5,internal_RAM_read_to_write_edges=9,
        native_only_observability='Unchanged parent host routing exports reduction of actual bank pendingvalid; this probe is not the physical wrapper.',
        pending_cancel_cases='Forward/point × profile_abort/reset at observed firstpending/pre-firstcommit; full RAM equality+12quietedges+reload/forward recovery.',
        independent_math='Original direct small polynomial/schoolbook, fullN ordinary twist/cyclicDIFDIT retained. Four recoverytransforms explicitly separate from main15phase counters.',
        current_whole_sources_unchanged=True,integer_post_CRT_doubling_unchanged=True,
        numeric_full_N_locally_performed=False,hold_repair_claim=False)
    gen.upper.need(set(m['build']['sv_sources']+[gen.CPP]) <= files.keys() and
        gen.PARENT not in m['build']['sv_sources'] and gen.HOST not in m['build']['sv_sources'],
        'A10_F3_SINGLE_COMPILED_ENGINE_HOST_AND_CLOSURE')
    return m,files


def prepare(output, aw, field, budget, *, allow_full_constants=False):
    gen.upper.need(not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')), 'A10_F3_PAUSE')
    output = Path(output).resolve(); gen.upper.need(not output.exists(), 'A10_F3_FRESH_OUTPUT')
    m,files = role(aw,field,allow_full_constants=allow_full_constants)
    source = output/'input/source/fpga'; source.mkdir(parents=True)
    for name,raw in files.items():
        path = source/name; path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream: stream.write(raw)
    def dump(path,value):
        with path.open('x') as stream: json.dump(value,stream,indent=2); stream.write('\n')
    manifest = output/'input/manifest.json'; dump(manifest,m); variants = []
    for pair in ('01','23'):
        profile = f'gcp-c4d-static{pair}-v1'; worker = f'a10-writeback-aw{aw}-f{field}-{pair}-v1'
        packet = output/('packet-'+pair)
        result = parent.small.batch.package.prepare(manifest,source,profile,worker,'run',packet,Path(budget).resolve())
        variants.append(dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],
            ticket_sha256=result['ticket_sha256'],manifest_sha256=gen.sha((packet/'manifest.json').read_bytes()),
            native_root=result['native_root'],runner='tools/native_class_package_v2.py',runner_sha256=parent.small.batch.PACKAGE_SHA,
            stager=str(ROOT/'tools/native_package_v3.py'),stager_sha256='5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9',
            stager_dependencies=[dict(path=str(ROOT/'tools/native_package_v2.py'),sha256='3f2186fa5aac8129ac1ad5a161de39cf221925ee95d5de6364a941b199e7279a')],max_seconds=3700))
    predecessor = f'a10-upper-engine-aw16-f{field}-q1-v2' if aw == 5 else f'a10-writeback-aw{5 if aw == 8 else 8}-f{field}-q1-v1'
    qid = f'a10-writeback-aw{aw}-f{field}-q1-v1'
    ticket = dict(schema='gfn16-global-ticket-v1',id=qid,owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P2',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=8 if aw == 16 else 4,
        minimum_ram_rationale='AW16 preserves observedpassed8GiB upper profile; AW5/8 4GiB is explicit bounded exploration, desired8. No measured4GiB promise/noautomaticretry.',
        est_minutes=5,promotion_bound=False,packages=variants,after=[predecessor],on='PASS_expected_contracts')
    dump(output/'global-ticket-v1.json',ticket)
    summary = dict(schema='a10-writeback-preparation-v1',status='source_ready_not_dispatched',aw=aw,field=field,
        source_pins=PINS,source_files=len(files),variants=variants,predecessor=predecessor,
        source_only_ledger=gen.ledger(aw),HDL_or_native_executed=False,promotion_allowed=False)
    dump(output/'preparation.json',summary); return summary


if __name__ == '__main__':
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument('--aw',type=int,choices=(5,8,16),required=True); args.add_argument('--field',type=int,choices=(0,1,2),required=True)
    args.add_argument('--output',type=Path,required=True); args.add_argument('--budget',type=Path,required=True)
    args.add_argument('--allow-full-constants',action='store_true'); parsed=args.parse_args()
    result=prepare(parsed.output,parsed.aw,parsed.field,parsed.budget,allow_full_constants=parsed.allow_full_constants)
    print(json.dumps(dict(aw=result['aw'],field=result['field'],source_files=result['source_files'],predecessor=result['predecessor'],
        variants=[dict(profile=x['profile'],sha256=x['sha256'],ticket_sha256=x['ticket_sha256']) for x in result['variants']]),indent=2))
