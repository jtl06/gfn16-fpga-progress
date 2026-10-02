"""Finite A10 normal/fault/integration/geometry batch, source preparation only.

No dispatch or queue mutation. Reuses the actually passed AW5 repaired design
and frozen independent C++ oracles. Faults are exact one-site successors of
that design. Two source-identical GCP profile envelopes belong to ONE role;
the dispatcher must select only one and validate declared predecessor gates.
Full-N work here is ROM constants / source generation, never a numeric NTT.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re

from fpga.reference import a10_banked_aw5_prepare_v1 as old
from fpga.reference import a10_engine_geometry_gates_v1 as geometry
from fpga.reference import a10_geometry_prepare_v1 as geometry_prep
from fpga.reference import a10_lint_repair_v2 as repair
from fpga.tools import native_class_package_v2 as package
from fpga.tools import native_class_v1 as executor

ROOT = old.ROOT
SELF = 'reference/a10_native_batch_prepare_v1.py'
TEST = 'tests/test_a10_native_batch_prepare_v1.py'
DONOR = 'results/throughput-20260929/a10-aw5-f0-native-class-packet-v1'
DONOR_MANIFEST = 'e70e04db598944eeaa3fd9f8754ae7c766ed2feab52b0a7d2fbd5e9ac4001f40'
PASSED_REPORT = '1ecdd60bebe3940b9c3853812366c44e9a297f8cf4eb191e3e4097fa82f8c016'
PACKAGE_SHA = '03b6a81aa7d465487da97f854a79e9e43a19c9c637db6178587cfac02476f604'
VALIDATOR = 'reference/a10_native_roles_v1.py'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def need(ok, why):
    if not ok:
        raise ValueError(why)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def donor():
    directory = ROOT / DONOR
    raw = (directory / 'manifest.json').read_bytes()
    need(sha(raw) == DONOR_MANIFEST, 'A10_BATCH_DONOR_IDENTITY')
    m = json.loads(raw)
    source = directory / 'capture/source/fpga'
    geometry_prep.closed(source, m['sources'])
    done = json.loads((ROOT / 'queue/done/a10-aw5-f0-native-class-v1.json').read_text())
    need(done['result']['status'] == 'needs_independent_review' and
         done['result']['queue_report']['report_sha256'] == PASSED_REPORT and
         done['result']['properties']['ExecMainStatus'] == '0', 'A10_BATCH_ACTUAL_F0_PREDECESSOR')
    need(sha((ROOT / 'tools/native_class_package_v2.py').read_bytes()) == PACKAGE_SHA,
         'A10_BATCH_SHARED_PACKAGE_PIN')
    files = {n: (source / n).read_bytes() for n in m['sources']}
    files[SELF] = (ROOT / SELF).read_bytes()
    files[TEST] = (ROOT / TEST).read_bytes()
    return m, files


def mutation(files, kind):
    files = dict(files)
    if kind == 'root':
        parent = 'rtl/kernel/a10_packed_lookup_aw5_lint_bound_v2.sv'
        successor = 'rtl/kernel/a10_packed_lookup_aw5_fault_root_v1.sv'
        text = files[parent].decode()
        matches = list(re.finditer(r"assign ct_s4_q=27'h([0-9a-f]+);", text))
        need(len(matches) == 3, 'A10_BATCH_ROOT_ONE_FIELD')
        hit = matches[0]
        before = hit[0]
        after = f"assign ct_s4_q=27'h{(int(hit[1],16)+1)%old.math.FIELDS[0].p:07x};"
        text = text[:hit.start()] + after + text[hit.end():]
        need(text.replace(after, before, 1) == files[parent].decode(), 'A10_BATCH_ROOT_ONLY')
    else:
        need(kind in ('normalization', 'form'), 'A10_BATCH_MUTATION_KIND')
        parent = repair.ENGINE_V2
        successor = f'rtl/kernel/genefer_a10_banked27_fault_{kind}_v1.sv'
        before, after = (
            ('.normalization(normalization),', ".normalization(normalization+32'd1),")
            if kind == 'normalization' else
            ('.gs(bf_in_valid[lane] && active_inverse),', '.gs(bf_in_valid[lane]),'))
        text = old.gen.once(files[parent].decode(), before, after)
        need(text.replace(after, before) == files[parent].decode(), 'A10_BATCH_ENGINE_ONE_SITE')
    files[successor] = text.encode()
    return files, dict(kind=kind, parent=parent, successor=successor, before=before, after=after,
                       parent_sha256=sha(files[parent]), successor_sha256=sha(files[successor]),
                       expected_stderr=old.predict_typed_negative(kind), intentional_fault=True)


def role(role_id, *, allow_full_constants=False):
    m, files = donor()
    delta = None
    if role_id == 'aw5-f2':
        field = old.math.FIELDS[2]
        m['build']['parameters'].update(P=field.p, Q=field.q)
        m['build']['cflags'] = ['-std=c++17', '-Werror=return-type',
                              f'-DA10_P={field.p}', f'-DA10_G={field.generator}']
        m['steps'] = [dict(name='engine-normal', argv=['{exe}'], expected_returncode=0,
            expected_stdout=f'A10_ENGINE_PASS aw=5 field={field.p} cases=5 operations=15 residues=480 cycles=540 profile_words=4\n',
            expected_stderr='')]
        dependencies = []  # f0 actual gate already proved by donor().
    elif role_id in ('aw5-root', 'aw5-normalization', 'aw5-form'):
        kind = role_id.removeprefix('aw5-')
        files, delta = mutation(files, kind)
        m['build']['sv_sources'] = [delta['successor'] if n == delta['parent'] else n
                                    for n in m['build']['sv_sources']]
        m['steps'] = [dict(name='typed-' + kind, argv=['{exe}', '--fault-' + kind],
            expected_returncode=1, expected_stdout='', expected_stderr=delta['expected_stderr'])]
        dependencies = []
    elif role_id == 'aw5-e2e1':
        prior = ROOT / 'results/throughput-20260929/a10-banked-aw5-stage-v1/whole-e2e1/manifest.json'
        whole = json.loads(prior.read_text())
        m['build'] = whole['build']
        m['build']['sv_sources'] = [repair.ENGINE_V2 if n == repair.ENGINE_V1 else
            'rtl/kernel/a10_packed_lookup_aw5_lint_bound_v2.sv' if n == old.LOOKUP_SV else n
            for n in m['build']['sv_sources']]
        m['steps'] = []
        for negative in (None, 'comparator'):
            name = 'prp-normal' if negative is None else 'prp-negative-comparator'
            argv = ['{exe}', '{root}/prp-aw5.txt'] + (['--negative-comparator'] if negative else [])
            m['steps'].append(dict(name=name, argv=argv, expected_returncode=1 if negative else 0,
                validator=dict(source=VALIDATOR, function='validate',
                    config=dict(role='e2e1', negative=negative), assets=dict(oracle='prp-oracle.json'))))
        dependencies = ['aw5-f1', 'aw5-f2', 'aw5-root', 'aw5-normalization', 'aw5-form']
    else:
        match = re.fullmatch(r'aw(8|16)-f([012])', role_id)
        need(match is not None, 'A10_BATCH_ROLE')
        aw, number = map(int, match.groups())
        need(aw == 8 or allow_full_constants, 'A10_BATCH_FULL_CONSTANTS_EXPLICIT')
        field = old.math.FIELDS[number]
        binding = old.gen.lookup_binding(1 << aw, 64, allow_full_constants=allow_full_constants)
        normal = '\n'.join(x['source'] for x in binding['compiled']) + '\n' + binding['source']
        name = f'rtl/kernel/a10_packed_lookup_aw{aw}_lint_bound_v2.sv'
        files[name] = repair.repair_lookup(normal, aw).encode()
        files[geometry.BENCH] = (ROOT / geometry.BENCH).read_bytes()
        need(files[geometry.BENCH].decode() == geometry.bench_source(), 'A10_BATCH_GEOMETRY_CPP')
        m['build']['parameters'].update(AW=aw, P=field.p, Q=field.q)
        m['build']['cpp_source'] = geometry.BENCH
        m['build']['cflags'] = ['-std=c++17', '-Werror=return-type', f'-DA10_AW={aw}',
                              f'-DA10_P={field.p}', f'-DA10_G={field.generator}']
        m['build']['sv_sources'] = [name if n == 'rtl/kernel/a10_packed_lookup_aw5_lint_bound_v2.sv' else n
                                    for n in m['build']['sv_sources']]
        m['steps'] = [dict(name='engine-normal', argv=['{exe}'], expected_returncode=0,
            validator=dict(source=VALIDATOR, function='validate',
                config=dict(role='engine', negative=None, aw=aw, field=field.p), assets={}))]
        m['source_only_ledger'] = geometry.ledger(aw)
        dependencies = (['aw5-f1', 'aw5-f2', 'aw5-root', 'aw5-normalization', 'aw5-form', 'aw5-e2e1']
                        if aw == 8 else ['aw8-f0', 'aw8-f1', 'aw8-f2'])
    # The normal passed design and frozen one-site parents remain in closure.
    # Never compile original and successor definitions simultaneously.
    m['sources'] = {n: sha(raw) for n, raw in files.items()}
    need(all(n in files for n in m['build']['sv_sources'] + [m['build']['cpp_source']]),
         'A10_BATCH_COMPILED_CLOSURE')
    m.pop('lint_baseline', None)
    m['source_root'] = '/not-a-dispatch-path/a10-batch/fpga'
    m['output_parent'] = '/not-a-dispatch-path/a10-batch/output'
    m['scope'] = f'Canonical A10 {role_id}; exact-source crtmont lineage, independent native contracts; not fit/clock/production.'
    m['batch_role'] = dict(id=role_id, parent_native_report_sha256=PASSED_REPORT,
        dependencies=dependencies, mutation=delta, numeric_full_N_locally_performed=False,
        typed_expected_nonzero_is_gate_success=delta is not None or role_id == 'aw5-e2e1')
    return m, files


def prepare_role(output, role_id, budget, *, allow_full_constants=False):
    need(not (ROOT / 'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    output = Path(output).resolve()
    need(not output.exists(), 'A10_BATCH_FRESH_ROLE')
    m, files = role(role_id, allow_full_constants=allow_full_constants)
    source = output / 'input/source/fpga'
    source.mkdir(parents=True)
    for name, raw in sorted(files.items()):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
    geometry_prep.closed(source, m['sources'])
    manifest_path = output / 'input/manifest.json'
    with manifest_path.open('x') as stream:
        json.dump(m, stream, indent=2)
        stream.write('\n')
    variants = []
    for pair in ('01', '23'):
        profile = 'gcp-c4d-static' + pair + '-v1'
        worker_id = 'a10-' + role_id + '-batch-' + pair + '-v1'
        packet = output / ('packet-' + pair)
        prepared = package.prepare(manifest_path, source, profile, worker_id, 'run', packet, Path(budget).resolve())
        selected = executor.profile(profile)
        variants.append(dict(profile=profile, worker_id=worker_id,
            packet=str(packet), archive=str(packet / 'package.tar.gz'),
            sha256=prepared['archive_sha256'], ticket_sha256=prepared['ticket_sha256'],
            manifest_sha256=sha((packet / 'manifest.json').read_bytes()),
            native_root=prepared['native_root'], build_key=prepared['build_key'],
            archive_bytes=prepared['archive_bytes'],
            resource_profile_sha256=sha(canonical(selected)),
            runner='tools/native_class_package_v2.py', runner_sha256=PACKAGE_SHA))
    a, b = [json.loads((Path(v['packet']) / 'manifest.json').read_text()) for v in variants]
    need(a['sources'] == b['sources'] and a['build'] == b['build'] and a['steps'] == b['steps'],
         'A10_BATCH_DUAL_EQUIVALENCE')
    result = dict(schema='a10-finite-role-dual-profile-v1', status='source_ready_not_dispatched',
        role=role_id, dependencies=m['batch_role']['dependencies'],
        source_map_sha256=sha(canonical(a['sources'])), build_sha256=sha(canonical(a['build'])),
        steps_sha256=sha(canonical(a['steps'])), source_files=len(a['sources']),
        variants=variants, select_exactly_one=True, mutation=m['batch_role']['mutation'],
        original_field0_result_not_reexecuted=True, promotion_allowed=False,
        full_N_numeric_NTT_locally_performed=False)
    with (output / 'role.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--budget', type=Path, required=True)
    parser.add_argument('--allow-full-constants', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare_role(args.output, args.role, args.budget,
                    allow_full_constants=args.allow_full_constants), indent=2))
