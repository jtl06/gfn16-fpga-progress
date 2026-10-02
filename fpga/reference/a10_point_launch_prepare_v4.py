"""Full-size component qualification of unchanged point-launch RTL.

Only the frozen native C++ geometry admission comment/static_assert extends.
Numeric full-N ordinary NTT oracle executes only on admitted Linux workers.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from fpga.reference import a10_point_launch_prepare_v3 as parent

ROOT = parent.ROOT
SELF = 'reference/a10_point_launch_prepare_v4.py'
TEST = 'tests/test_a10_point_launch_prepare_v4.py'
CPP = 'rtl/tb/a10_point_launch_geometry_v4.cpp'
CPP_SHA = '277b224d6e1dde7718d47d2338d0ec7f48a0f4bc92790dffa37319b2cb361dd9'
PARENT_SHA = 'aa914876a9ebfc466696337f08a36096978eca30aa94e002bb9efbaf7e25e44a'
LOOKUP = 'rtl/kernel/a10_packed_lookup_aw16_lint_bound_v2.sv'
LOOKUP_SOURCE = 'results/throughput-20260929/a10-point-field-probe-v3/project-workers6/rtl/a10_packed_lookup_aw16_lint_bound_v2.sv'
LOOKUP_SHA = '7b433bba2501b84694e1f47a31595333365ea4ae659d14faafe4f40a67e76c73'


def cpp_source():
    parent.verify()
    text = (ROOT/parent.CPP).read_text()
    changes = (
        ('// Additive AW5/8 point launch-register geometry harness; independent ordinary oracle.',
         '// Additive AW5/8/16 point launch-register geometry harness; independent ordinary oracle.'),
        ('static_assert(AW==5 || AW==8,"separately admitted small geometry only");',
         'static_assert(AW==5 || AW==8 || AW==16,"separately admitted geometry only");'))
    result = text
    for old, new in changes:
        parent.gen.parent.need(result.count(old) == 1, 'A10_POINT_FULL_CPP_EXACT_SITE')
        result = result.replace(old, new)
    restored = result
    for old, new in reversed(changes):
        restored = restored.replace(new, old)
    parent.gen.parent.need(restored == text and parent.gen.sha(result.encode()) == CPP_SHA,
                           'A10_POINT_FULL_NO_ORACLE_OR_COUNTER_CHANGE')
    return result


def role(aw, field, *, allow_full_constants=False):
    need = parent.gen.parent.need
    need(type(aw) is int and aw == 16 and type(field) is int and field in (0, 1, 2),
         'A10_POINT_FULL_ROLE')
    need(allow_full_constants is True, 'A10_POINT_FULL_CONSTANTS_EXPLICIT')
    need(parent.gen.sha((ROOT/'reference/a10_point_launch_prepare_v3.py').read_bytes()) == PARENT_SHA,
         'A10_POINT_SMALL_PREPARER_FROZEN')
    need((ROOT/CPP).read_text() == cpp_source(), 'A10_POINT_FULL_CPP_SOURCE')
    raw = (ROOT/LOOKUP_SOURCE).read_bytes()
    need(parent.gen.sha(raw) == LOOKUP_SHA, 'A10_POINT_FULL_MATCHED_LOOKUP_PIN')
    m, files = parent.role(8, field)
    files[LOOKUP] = raw
    for name in (CPP, SELF, TEST):
        files[name] = (ROOT/name).read_bytes()
    m['build']['sv_sources'] = [LOOKUP if name.endswith('/a10_packed_lookup_aw8_lint_bound_v2.sv') else name
                               for name in m['build']['sv_sources']]
    m['build']['parameters']['AW'] = aw
    m['build']['cpp_source'] = CPP
    m['build']['cflags'] = ['-DA10_AW=16' if flag == '-DA10_AW=8' else flag for flag in m['build']['cflags']]
    field_value = parent.batch.old.math.FIELDS[field].p
    ledger = parent.gen.ledger(aw)
    m['steps'][0]['expected_stdout'] = (f'A10_POINT_ENGINE_PASS aw=16 field={field_value} '
        f'cases=5 operations=15 residues={ledger["residues"]} cycles={ledger["engine_work_cycles"]} profile_words=4\n')
    m['sources'] = {name: parent.gen.sha(content) for name, content in files.items()}
    m['point_launch'].update(source_only_ledger=ledger, full_geometry_CPP_SHA256=CPP_SHA,
        full_geometry_CPP_delta='Comment and geometry static_assert only; all arithmetic/oracle/counters/profile/reset drivers unchanged.',
        independent_oracle='Ordinary twist + conventional cyclic DIF/DIT, not merged roots/group schedule.',
        matched_lookup_SHA256=LOOKUP_SHA, full_N_numeric_locally_performed=False)
    need(set(m['build']['sv_sources']+[CPP]) <= files.keys(), 'A10_POINT_FULL_COMPILED_CLOSURE')
    return m, files


def prepare(output, aw, field, budget, *, allow_full_constants=False):
    need = parent.gen.parent.need
    need(not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE', 'queue/PAUSE')), 'A10_POINT_FULL_PAUSE')
    output = Path(output).resolve(); need(not output.exists(), 'A10_POINT_FULL_FRESH_OUTPUT')
    m, files = role(aw, field, allow_full_constants=allow_full_constants)
    source = output/'input/source/fpga'; source.mkdir(parents=True)
    for name, raw in files.items():
        path = source/name; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    def dump(path, value):
        with path.open('x') as stream:
            json.dump(value, stream, indent=2); stream.write('\n')
    manifest = output/'input/manifest.json'; dump(manifest, m); variants = []
    for pair in ('01', '23'):
        profile = f'gcp-c4d-static{pair}-v1'; worker = f'a10-point-aw16-f{field}-{pair}-v4'
        packet = output/('packet-'+pair)
        result = parent.batch.package.prepare(manifest, source, profile, worker, 'run', packet, Path(budget).resolve())
        variants.append(dict(profile=profile, worker_id=worker, archive=str(packet/'package.tar.gz'),
            sha256=result['archive_sha256'], ticket_sha256=result['ticket_sha256'],
            manifest_sha256=parent.gen.sha((packet/'manifest.json').read_bytes()), native_root=result['native_root'],
            runner='tools/native_class_package_v2.py', runner_sha256=parent.batch.PACKAGE_SHA,
            stager=str(ROOT/'tools/native_package_v3.py'),
            stager_sha256='5ce285d2a880d4b739c02d0daec5a4e15b6ab23b4b570fafed46ebbe5d8239b9',
            stager_dependencies=[dict(path=str(ROOT/'tools/native_package_v2.py'),
                sha256='3f2186fa5aac8129ac1ad5a161de39cf221925ee95d5de6364a941b199e7279a')], max_seconds=3700))
    qid = f'a10-point-aw16-f{field}-q1-v4'
    ticket = dict(schema='gfn16-global-ticket-v1', id=qid, owner='merged-ntt-model',
        created=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), priority='P1', kind='sim', needs='verilator',
        tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
        resources=dict(cores=2, threads=1, ram_gib=8, scratch_gib=4),
        minimum_ram_gib=8, minimum_ram_rationale='Preserve actual passed parent AW16 8GiB profile. Its~3.43GiB child RSS is not proof of4GiB cgroup headroom; no silent cap downgrade.',
        est_minutes=5, promotion_bound=False, packages=variants,
        after=[f'a10-point-aw8-f{field}-q1-v3'], on='PASS_expected_contracts')
    dump(output/'global-ticket-v4.json', ticket)
    summary = dict(schema='a10-point-full-geometry-preparation-v4', status='source_ready_not_dispatched',
        aw=aw, field=field, source_files=len(files), variants=variants,
        unchanged_engine_SHA256=parent.PINS[parent.gen.TARGET], CPP_SHA256=CPP_SHA,
        lookup_SHA256=LOOKUP_SHA, source_only_ledger=parent.gen.ledger(16),
        HDL_or_native_executed=False, full_N_numeric_locally_performed=False, promotion_allowed=False)
    dump(output/'preparation.json', summary); return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aw', type=int, choices=(16,), default=16)
    parser.add_argument('--field', type=int, choices=(0,1,2), required=True)
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--budget', type=Path, required=True)
    parser.add_argument('--allow-full-constants', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.aw, args.field, args.budget,
                           allow_full_constants=args.allow_full_constants), indent=2))
