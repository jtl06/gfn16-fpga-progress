"""Import pinned worker reference assets into an F2 serial native role.

No numeric transforms, remote execution, or runner. The reference execution
gate belongs to the shared dispatcher dependency, not the data's own receipt.
This importer checks exact file pins, frozen arithmetic provenance, canonical
corpus structure and simple closed-form identities; it does not infer an
actual worker run from a self-reported JSON document.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

from fpga.reference import root_lookahead_field_v2 as field
from fpga.reference import root_lookahead_field_host_v3 as host


ROOT = field.ROOT
PARENT = ROOT / 'artifacts/root-lookahead-v1-prepared'
MANIFEST = 'aethia-aw5-one-field.json'
MANIFEST_SHA = '79f75584fda3e95730238f18e372496d749c9284a4b1429ecaae8a84630ffc06'
HOST_SHA = '806849d97b5b3a28a7a80fe2ca789fe26f15f2346ba0df8189169e601dde13d3'
DATA_SHA = 'aa3567a647adf0501f2bc33a98bb1f8b9ff39d7cc0e4d59ea7754c8252dc5e64'
SELF = 'reference/root_lookahead_field_import_v3.py'
FROZEN_EXTRA = {
    field.SELF: host.PARENT_SHA,
    field.BENCH: '34319982e2f0e3135fceebe376288de91ef1ab2ae30f3c0f7812a06ca93a7657',
    field.THREAD_HEADER: 'afd27444d1b4c991d11c84482db08f2fcef62757968e96ac83c5d44e55622f90',
    'tests/test_root_lookahead_field_v2.py': 'd4e20895e1bc78c3a516851555160bbb4a4b72b729e652565039e7177b630276',
    'reference/merged_negacyclic27_model.py': field.MATH_SHA,
}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def regular(path, pin):
    path = Path(path)
    field.need(path.is_absolute() and path.is_file() and not path.is_symlink()
               and path.resolve() == path, 'canonical regular external asset')
    field.need(type(pin) is str and re.fullmatch('[0-9a-f]{64}', pin) is not None
               and sha(path) == pin, 'external asset exact hash pin')
    return path


def validate_assets(vector, receipt, vector_pin, receipt_pin, aw, field_index):
    """Pure file/identity checks; test scalar inputs use the identical schema."""
    field.need(aw in (5, 8, 16) and type(aw) is int and
               type(field_index) is int and field_index in (0, 1, 2), 'import geometry')
    host.source_guard()
    field.need(sha(host.__file__) == HOST_SHA and
               sha(ROOT / 'reference/root_lookahead_field_data_v3.py') == DATA_SHA,
               'host/data successor source pins')
    vector, receipt = regular(vector, vector_pin), regular(receipt, receipt_pin)
    field.need(vector != receipt and receipt.stat().st_size <= 65536, 'distinct bounded receipt')
    meta = json.loads(receipt.read_text())
    f, n = field.field_math.FIELDS[field_index], 1 << aw
    words = (2 * aw + 2) * 257
    exact = dict(schema='F2-field-vector-receipt-v3', aw=aw, p=f.p, n=n,
                 cases=4, operations=20, readbacks=20*n, aborts=10, faults=11,
                 profile_words=words, profile_format=2, cycle_delta_expected=0,
                 host_guard_successor=host.SELF, host_guard_sha256=HOST_SHA,
                 frozen_arithmetic_parent_sha256=host.PARENT_SHA,
                 arithmetic_code_objects_unchanged=list(host.ARITHMETIC),
                 source_only_reference_data=True, native_RTL_executed=False,
                 vector_sha256=vector_pin, vector_bytes=vector.stat().st_size,
                 generator_sha256=DATA_SHA, numeric_full_N=aw == 16,
                 requires_linux_profile=aw > 8, source_and_resource_envelope_required=True)
    for key, value in exact.items():
        field.need(type(meta.get(key)) is type(value) and meta[key] == value,
                   'exact vector receipt field: ' + key)
    field.need(meta.get('source_hashes') == {field.SELF: host.PARENT_SHA,
               'reference/core27_prefetch_r2_structure.py': field.PROFILE_SHA,
               'reference/merged_negacyclic27_model.py': field.MATH_SHA}, 'frozen oracle source map')
    profile_id = meta.get('configured_static_profile')
    field.need(profile_id in host.ALLOWED, 'known configured vector profile')
    selected = host.static.profile(profile_id)
    if aw > 8:
        field.need(meta.get('platform') == 'Linux' and meta.get('hostname') == selected['host'],
                   'full vector known Linux identity')
        limits = meta.get('full_numeric_limits')
        field.need(type(limits) is dict and limits.get('affinity') == selected['cpus'] and
                   limits.get('full_topology') == selected['topology'] and
                   limits.get('physical_cores') == [selected['topology'][str(c)] for c in selected['cpus']] and
                   limits.get('memory_max_bytes') == selected['memory_bytes'] and
                   limits.get('swap_max_bytes') == 0, 'full vector captured resource identity')
        quota = limits.get('cpu_max')
        field.need(type(quota) is list and len(quota) == 2 and all(type(x) is str and x.isdecimal() for x in quota)
                   and int(quota[1]) > 0 and int(quota[0]) == 2*int(quota[1]), 'full vector captured CPU quota')
        field.need(type(limits.get('cgroup')) is str and limits['cgroup'].startswith('/')
                   and '\n' not in limits['cgroup'], 'full vector captured cgroup')
    else:
        field.need(meta.get('full_numeric_limits') is None, 'scalar vector no full-N resource claim')
    # At most 24 canonical N-word rows plus one profile row. Parse no executable
    # data and perform no NTT: this remains safe on the local Mac at AW16.
    field.need(vector.stat().st_size <= 24*n*11 + words*11 + 1024, 'bounded vector corpus')
    raw = vector.read_bytes()
    field.need(raw.endswith(b'\n') and b'\r' not in raw and b'\0' not in raw, 'canonical vector text')
    lines = raw.decode('ascii').splitlines()
    field.need(len(lines) == 26 and lines[0] == f'F2FIELD2 {aw} {f.p} {words} 4', 'exact vector header/row count')
    profile = [field.profile_word(f.p, f.generator, aw, 64, i) for i in range(words)]
    field.need(lines[1] == ' '.join(map(str, profile)), 'exact frozen profile words')
    for case in range(4):
        seed = 0xF202001 + aw + field_index
        for phase in range(6):
            tokens = lines[2+case*6+phase].split(' ')
            field.need(len(tokens) == n, 'exact canonical N-word phase row')
            for index, token in enumerate(tokens):
                field.need(re.fullmatch('0|[1-9][0-9]{0,8}', token) is not None,
                           'canonical decimal phase word')
                value = int(token)
                field.need(value < f.p, 'canonical field phase word')
                if phase == 0:
                    if case == 0: expected = int(index == 0)
                    elif case == 1: expected = f.p-1 if index == n-1 else 0
                    elif case == 2: expected = f.p-1
                    else:
                        seed = (1664525*seed+1013904223) & 0xffffffff
                        expected = seed % f.p
                    field.need(value == expected, 'exact input corpus identity')
                elif phase == 5 and case < 3:
                    if case == 0: expected = int(index == 0)
                    elif case == 1: expected = f.p-1 if index == n-2 else 0
                    else: expected = (2*index-n+2) % f.p
                    field.need(value == expected, 'closed-form final corpus identity')
    return dict(meta, import_checks='hash/provenance/profile/canonical rows/inputs/closed-form identities',
                full_transform_recomputed_by_importer=False,
                outer_reference_execution_not_inferred=True)


def prepare(output, vector, receipt, vector_pin, receipt_pin, aw=16, field_index=0):
    field.need(not (ROOT / 'docs/briefs/PAUSE').exists(), 'brief PAUSE')
    field.need(aw == 16, 'external integration preparation is AW16 only')
    meta = validate_assets(vector, receipt, vector_pin, receipt_pin, aw, field_index)
    parent = PARENT / MANIFEST
    field.need(sha(parent) == MANIFEST_SHA, 'frozen parent role manifest')
    old = json.loads(parent.read_text())
    source = PARENT / 'source/fpga'
    field.need({p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*') if p.is_file()}
               == old['sources'], 'frozen F2 source closure')
    for name, pin in FROZEN_EXTRA.items():
        field.need(sha(ROOT / name) == pin, 'frozen integration source: ' + name)
    output = Path(output)
    field.need(output.is_absolute() and not output.exists() and output.parent.is_dir()
               and output.parent.resolve() == output.parent, 'fresh canonical import packet')
    target = output / 'source/fpga'
    shutil.copytree(source, target)
    extra = [field.SELF, field.BENCH, field.THREAD_HEADER, SELF,
             'tests/test_root_lookahead_field_v2.py', 'reference/merged_negacyclic27_model.py']
    for name in extra:
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    asset = f'field-aw{aw}-f{field_index}-vectors.txt'
    receipt_asset = f'field-aw{aw}-f{field_index}-vector-receipt-v3.json'
    shutil.copyfile(vector, target / asset)
    shutil.copyfile(receipt, target / receipt_asset)
    field.need(sha(target / asset) == vector_pin and sha(target / receipt_asset) == receipt_pin,
               'external asset copy exact hash pins')
    for name, pin in {**old['sources'], **FROZEN_EXTRA}.items():
        field.need(sha(target / name) == pin, 'imported frozen source: ' + name)
    spec = field.integration_build(aw, field_index, 1)
    manifest = dict(old)
    manifest['build'] = {key: spec[key] for key in ('top', 'sv_sources', 'cpp_source', 'parameters', 'cflags', 'runtime_threads')}
    manifest['steps'] = [dict(name='field-control', argv=['{exe}', '{root}/'+asset],
                              expected_returncode=0, validator=spec['validator']),
                         dict(name='field-negative-oracle', **spec['negative_step'])]
    manifest['sources'] = {p.relative_to(target).as_posix(): sha(p) for p in target.rglob('*') if p.is_file()}
    manifest['scope'] = 'F2 AW16 field paired engine integration with exact worker-reference assets; source-only preparation.'
    manifest['admission'] = dict(old['admission'], prepared_by=SELF, promotion_allowed=False,
        limitation='Requires shared source/resource/reference dependency admission and r38 actual lint/build class gates; imported data receipt alone proves no native run.')
    path = output / 'role-manifest.json'
    path.write_text(json.dumps(manifest, indent=2)+'\n')
    result = dict(status='prepared_source_only_AW16_import_role', aw=aw, field=field_index,
                  role_manifest_sha256=sha(path), source_root=str(target),
                  source_files=len(manifest['sources']), sources=manifest['sources'],
                  vector_sha256=vector_pin, vector_receipt_sha256=receipt_pin,
                  reference_asset_checks=meta, source_only=True, launcher_clones_created=0,
                  reference_execution_requires_external_dispatcher_gate=True,
                  full_transform_recomputed_by_importer=False, native_RTL_executed=False)
    (output / 'preparation.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--vector', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--vector-sha256', required=True)
    parser.add_argument('--receipt-sha256', required=True)
    parser.add_argument('--field', type=int, default=0)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.vector, args.receipt, args.vector_sha256,
                             args.receipt_sha256, field_index=args.field), indent=2))
