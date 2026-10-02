"""Connected A10 geometry sequence for the latency-neutral upper launch cell.

Fresh source packages only. Cell paired gates → AW5 → AW8 → AW16 per field;
all numerical full-size work remains inside the native C++ Linux executable.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from fpga.reference import a10_upper_sum_generate_v2 as gen
from fpga.reference import a10_point_launch_prepare_v3 as small
from fpga.reference import a10_point_launch_prepare_v4 as full

ROOT = gen.ROOT
SELF = 'reference/a10_upper_sum_engine_prepare_v2.py'
TEST = 'tests/test_a10_upper_sum_engine_prepare_v2.py'
PINS = {gen.TARGET:'6e6688e37df413b2506c03bd27a3c8eb7962ae45a94d9935150d2175afad6f8b',
        gen.ENGINE:'03f3e395cccac6e17979f7990bc12095675e264afa08a884a77100aa3f3cb273',
        'reference/a10_upper_sum_generate_v2.py':'9e36bc24e947637b070395621fb83ace275dd8c95684960f7815770490769d74'}


def verify():
    gen.need((ROOT/gen.TARGET).read_text() == gen.cell_source() and
             (ROOT/gen.ENGINE).read_text() == gen.engine_source(), 'A10_UPPER_CONNECTED_EXACT_GENERATION')
    gen.need(all(gen.sha((ROOT/name).read_bytes()) == pin for name,pin in PINS.items()),
             'A10_UPPER_CONNECTED_FROZEN_PINS')


def role(aw, field, *, allow_full_constants=False):
    gen.need(type(aw) is int and aw in (5,8,16) and type(field) is int and field in (0,1,2),
             'A10_UPPER_CONNECTED_GEOMETRY')
    verify()
    m, files = full.role(16, field, allow_full_constants=allow_full_constants) if aw == 16 else small.role(aw, field)
    for name in (*PINS, SELF, TEST, 'tests/test_a10_upper_sum_generate_v2.py', gen.PATH_LEDGER):
        files[name] = (ROOT/name).read_bytes()
    m['build']['sv_sources'] = [gen.TARGET if name == gen.PARENT else
                               gen.ENGINE if name == gen.POINT else name for name in m['build']['sv_sources']]
    gen.need(gen.TARGET in m['build']['sv_sources'] and gen.ENGINE in m['build']['sv_sources'] and
             gen.PARENT not in m['build']['sv_sources'] and gen.POINT not in m['build']['sv_sources'],
             'A10_UPPER_CONNECTED_SINGLE_CELL_AND_ENGINE')
    m['sources'] = {name:gen.sha(raw) for name,raw in files.items()}
    m['source_root'] = '/not-a-dispatch-path/a10-upper-sum/fpga'
    m['output_parent'] = '/not-a-dispatch-path/a10-upper-sum/output'
    m['scope'] = 'Canonical A10 point+latency-neutral upper normalization launch component; unchanged independent oracle/counters/profile; not whole A-next/physical/promotion.'
    m['upper_sum_launch'] = dict(source_pins=PINS, cell_ledger=gen.ledger(),
        source_only_engine_ledger=small.gen.ledger(aw), paired_cell_gate_required=True,
        numeric_full_N_locally_performed=False,
        preserved='Qualified point-only engine differs by exactly one cell binding; old/new BF outputs and k+5 contract must pass independently before connected gates.',
        no_engine_cycle_or_control_delta=True, integer_post_CRT_doubling_unchanged=True)
    return m, files


def prepare(output, aw, field, budget, *, allow_full_constants=False):
    gen.need(not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE','queue/PAUSE')), 'A10_UPPER_CONNECTED_PAUSE')
    output = Path(output).resolve(); gen.need(not output.exists(), 'A10_UPPER_CONNECTED_FRESH_OUTPUT')
    m, files = role(aw, field, allow_full_constants=allow_full_constants)
    source = output/'input/source/fpga'; source.mkdir(parents=True)
    for name, raw in files.items():
        path = source/name; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    def dump(path, value):
        with path.open('x') as stream:
            json.dump(value, stream, indent=2); stream.write('\n')
    manifest = output/'input/manifest.json'; dump(manifest,m); variants=[]
    for pair in ('01','23'):
        profile = f'gcp-c4d-static{pair}-v1'; worker = f'a10-upper-engine-aw{aw}-f{field}-{pair}-v2'
        packet = output/('packet-'+pair)
        result = small.batch.package.prepare(manifest, source, profile, worker, 'run', packet, Path(budget).resolve())
        variants.append(dict(profile=profile,worker_id=worker,archive=str(packet/'package.tar.gz'),
            sha256=result['archive_sha256'],ticket_sha256=result['ticket_sha256'],
            manifest_sha256=gen.sha((packet/'manifest.json').read_bytes()),native_root=result['native_root'],
            runner='tools/native_class_package_v2.py',runner_sha256=small.batch.PACKAGE_SHA,
            stager=str(ROOT/'tools/native_package_v3.py'),stager_sha256='5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9',
            stager_dependencies=[dict(path=str(ROOT/'tools/native_package_v2.py'),sha256='3f2186fa5aac8129ac1ad5a161de39cf221925ee95d5de6364a941b199e7279a')],max_seconds=3700))
    predecessor = f'a10-upper-sum-f{field}-q1-v2' if aw == 5 else f'a10-upper-engine-aw{5 if aw == 8 else 8}-f{field}-q1-v2'
    qid = f'a10-upper-engine-aw{aw}-f{field}-q1-v2'
    ticket=dict(schema='gfn16-global-ticket-v1',id=qid,owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),priority='P1',kind='sim',needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),
        minimum_ram_gib=8 if aw == 16 else 4,
        minimum_ram_rationale='FullN preserves passed8GiB cap; smallN4GiB is bounded exploratory for samepassedpoint engine+latencyneutralcell. No downgrade offullN/no automaticretry.',
        est_minutes=5,promotion_bound=False,packages=variants,after=[predecessor],on='PASS_expected_contracts')
    dump(output/'global-ticket-v2.json',ticket)
    summary=dict(schema='a10-upper-connected-preparation-v2',status='source_ready_not_dispatched',aw=aw,field=field,
        source_pins=PINS,source_files=len(files),variants=variants,predecessor=predecessor,
        engine_cycle_delta=0,HDL_or_native_executed=False,full_N_numeric_locally_performed=False,promotion_allowed=False)
    dump(output/'preparation.json',summary); return summary


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aw',type=int,choices=(5,8,16),required=True);parser.add_argument('--field',type=int,choices=(0,1,2),required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--budget',type=Path,required=True)
    parser.add_argument('--allow-full-constants',action='store_true');args=parser.parse_args()
    print(json.dumps(prepare(args.output,args.aw,args.field,args.budget,allow_full_constants=args.allow_full_constants),indent=2))
