"""Source-only point-specific PRP/retained-state roles; immutable numeric donors.

The already used +1-cycle upper qualification harness is byte-pinned and only
its model/candidate identity is relabeled to the independently qualified point
RTL. Arithmetic, initial state, loop, checkpoints and error controls do not
change. No native execution or full-size reference generation occurs here.
"""
import hashlib
import json
from pathlib import Path
from fpga.reference import anext_point_source_v1 as point

ROOT = Path(__file__).resolve().parents[1]
CORE = 'f37123255ed08225f9c26a5d556fafb94c4e3eda9547b28713be956cda4cbe7b'
BLOCK = '076f6dcf120b448f38aff04fcb438e0f43158262ef08fcaa7c07ce8de8c83091'
PARENTS = {
    'rtl/tb/anext_upper_small_prp_v1.cpp': '1f4d01f366a4f4ab1620ff1daa871583e186c6a89cb72d2a0a2bdb28b0afc851',
    'rtl/tb/anext_upper_soak_v1.cpp': '09ee4727904a1a2c7aae8dedfac19d1544ed59f9960e266e17c2882b1a44d67b',
    'reference/anext_upper_small_prp_v1.py': 'e508de12cb15f271ba512b8f0d9cc1649bd3afad7ccca75674553c898f4078a7',
    'reference/anext_upper_soak_output_v1.py': '96eaa6bfe74d4e1b115b4e88ebc9d94441403ee07fb111bfd79d6b5363aba9f9',
}
ROLES = {
    'prp': ('anext-small-prp-aw5-role-v1', 'f0616eadb7804366991aa4e7fc53125dfa36e2556cf7c9e2ef3a154673f59989'),
    'short': ('anext-soak-short-aw16-role-v1', '2d8a6832db2c37f61f0c0a0036f6bee1de18b3ca468b7598160b5469e6fcb69f'),
    'pilot': ('anext-soak-chunk00-aw16-role-v1', 'cb036a46262afd2efea6c88983e47ee894cf3aad9355d08da5779eed9095dbae'),
    'continuous': ('anext-soak-continuous-aw16-role-v1', '93600acbdbec2cef42f4531a0eaf55ac18040afeaa058e47578e42f25a37869b'),
}
POINT_ROLES = {
    5: ('anext-point-whole-aw5-role-v1', '11340a6819c863139bff8b50564d44a0b5d1df3b2eaa8b154f969a0e42d7aeeb'),
    16: ('anext-point-representative-aw16-role-v1', '98ae80e62e95f70d08acf1d03af9bb9fdf84003852d900afaecce769d358c84a'),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def need(ok, why):
    if not ok:
        raise ValueError(why)


def once(text, old, new):
    need(text.count(old) == 1, 'one point qualification identity anchor '+old)
    return text.replace(old, new, 1)


def expected():
    result = {}
    for path, pin in PARENTS.items():
        need(sha(ROOT/path) == pin, 'frozen +1-cycle qualification parent '+path)
        text = (ROOT/path).read_text()
        if path.endswith('.cpp'):
            need(text.count('genefer_anext_upper_core_v1') == 2, 'two C++ model references')
            text = text.replace('genefer_anext_upper_core_v1', 'genefer_anext_point_core_v1')
        else:
            text = once(text, "candidate='A-next-upper-v1'", "candidate='A-next-point-v1'")
            if 'soak' in path:
                text = once(text, "CORE_SHA='47a84a9f20490709756af28623b3a7233832a2080a435f2fe71b2487b0dbe8bc'", "CORE_SHA='"+CORE+"'")
                text = once(text, 'genefer_anext_upper_core_v1.sv', 'genefer_anext_point_core_v1.sv')
        result[path.replace('anext_upper_', 'anext_point_')] = text
    return result


def verify():
    point.verify()
    need(sha(ROOT/'rtl/kernel/genefer_anext_point_core_v1.sv') == CORE
         and sha(ROOT/'rtl/kernel/genefer_anext_point_block_engine_v1.sv') == BLOCK, 'frozen point RTL identities')
    for name, text in expected().items():
        need((ROOT/name).read_text() == text, 'identity-only point qualification delta '+name)
    return dict(source_only=True, RTL_changed=False, arithmetic_changed=False,
                reset_reload_loop_unchanged=True, inherited_result=False)


def closed(role, pin):
    root = ROOT/'artifacts'/role
    need(sha(root/'manifest.json') == pin, 'frozen role manifest '+role)
    manifest = json.loads((root/'manifest.json').read_text())
    files = {}
    for name, digest in manifest['sources'].items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'closed relative role source')
        path = root/'source/fpga'/name
        need(not path.is_symlink() and sha(path) == digest, 'immutable role source '+name)
        files[name] = path.read_bytes()
    return manifest, files


def prepare(kind, output):
    verify()
    need(kind in ROLES, 'finite point qualification recipe')
    output = Path(output).resolve()
    need(not output.exists() and not (ROOT/'docs/briefs/PAUSE').exists(), 'fresh output/no PAUSE')
    manifest, files = closed(*ROLES[kind])
    model, model_files = closed(*POINT_ROLES[5 if kind == 'prp' else 16])
    for name, data in model_files.items():
        need(name not in files or files[name] == data, 'no ancestor source overwrite '+name)
        files[name] = data
    for name in [*PARENTS, *expected(), 'reference/anext_point_qualification_v1.py',
        'tests/test_anext_point_qualification_v1.py', 'tests/test_anext_soak_v1.py',
        'rtl/tb/anext_small_prp_v1.cpp', 'reference/anext_small_prp_v1.py',
        'rtl/tb/anext_soak_v1.cpp', 'reference/anext_soak_output_v1.py',
        'reference/anext_soak_source_v1.py', 'reference/core27_small_gfn_prp_v1.py',
        'reference/core27_t5b_soak_v1.py', 'reference/core27_crtmont_soak_v1.py',
        'rtl/tb/core27_t5b_soak_v1.cpp']:
        data = (ROOT/name).read_bytes()
        need(name not in files or files[name] == data, 'unchanged existing closure dependency '+name)
        files[name] = data
    manifest['build']['top'] = model['build']['top']
    manifest['build']['sv_sources'] = model['build']['sv_sources']
    manifest['build']['cpp_source'] = manifest['build']['cpp_source'].replace('anext_small_prp', 'anext_point_small_prp').replace('anext_soak', 'anext_point_soak')
    for step in manifest['steps']:
        step['validator']['source'] = step['validator']['source'].replace('anext_small_prp', 'anext_point_small_prp').replace('anext_soak', 'anext_point_soak')
    need(len(manifest['build']['sv_sources']) == 30
         and all(not name.startswith('donor/') for name in manifest['build']['sv_sources']), 'only thirty actual point RTL compile inputs')
    need(files['rtl/kernel/genefer_anext_point_core_v1.sv'] == (ROOT/'rtl/kernel/genefer_anext_point_core_v1.sv').read_bytes(), 'exact point model')
    source = output/'source/fpga'
    source.mkdir(parents=True)
    for name, data in files.items():
        path = source/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    manifest['sources'] = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return dict(kind=kind, manifest_sha256=sha(output/'manifest.json'), source_count=len(files),
                compiled_sv=30, core_sha256=CORE, block_sha256=BLOCK,
                numerical_assets_unchanged=True, native_executed=False)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=ROLES, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.kind, args.output), indent=2))
