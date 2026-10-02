"""Exact L16/F0 inherited-diagnostic admission, never clean-lint evidence.

Runs the pinned CPU02 launcher with only SELF and lint-return admission changed.
The original failed gate and every arithmetic/source ancestor remain immutable.
"""
import hashlib
import json
from pathlib import Path
import types

SELF = 'tools/native_root_lookahead_debt_v3.py'
PARENT = 'tools/native_source_gate_aethia_cpu02_v2.py'
PARENT_SHA = '452f9bfdebc535d39c1e493b61378de50720088788698435fd6d11974eb670b3'
ROOT = '/home/jtl/gfn-fpga-lab/agent-work/root-lookahead-cpu02-debt-v3/snapshot-v1/fpga'
BASELINE = 'evidence/f2-wall-failed-manifest.json'
BASELINE_SHA = '67476d7878c22f6f5cf8c508c3c1c222b97c1cae93ff47bcc04a67d89f5e417a'
REVIEW = 'evidence/f2-wall-failed-review.json'
REVIEW_SHA = 'a404927e5f2be992552d9f3a89615d49cbbb0e85f3c8ed325ee54c2f69d7508e'
STDERR = 'evidence/f2-wall-failed.stderr.log'
STDERR_SHA = '979fa3d421d9eead237efade6e2c28789a40f4011ca7615899bbb24b1db4de15'
NORMALIZED_SHA = '98d1062c5dcbb9e731416b475e899b5838fe04fefffc0bbc7b69eff7033131fc'


def require(ok, why):
    if not ok:
        raise ValueError(why)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def normalize(raw, root):
    require(type(raw) is bytes and len(raw) < 16384 and b'\0' not in raw, 'diagnostic bytes/size')
    # Only presentation indentation and the exact approved source-root prefix
    # vary. Keep every line, record, site, instance, message and final trailer.
    return ('\n'.join(line.strip().replace(str(root), '{ROOT}')
                      for line in raw.decode('utf-8').splitlines())+'\n').encode()


def accept_exact_lint_debt(name, command, code, stdout, stderr, manifest, tools, root, build):
    require(name == 'lint' and type(code) is int and code == 1 and stdout == b'', 'exact failed lint only')
    require(str(root) == ROOT and root.resolve() == root, 'single admitted source root')
    for path, pin in ((BASELINE, BASELINE_SHA), (REVIEW, REVIEW_SHA), (STDERR, STDERR_SHA)):
        require(manifest['sources'].get(path) == pin and digest((root/path).read_bytes()) == pin,
                'pinned failed evidence '+path)
    old = json.loads((root/BASELINE).read_text())
    require(manifest['host'] == 'aethia' and manifest['cpu_profile'] == 'aethia-physical-0-2-v1', 'host/profile')
    for key in ('build', 'probe', 'steps'):
        require(manifest[key] == old[key], 'unchanged exact role '+key)
    require(all(manifest['sources'].get(k) == v and digest((root/k).read_bytes()) == v
                for k, v in old['sources'].items()), 'all36 ancestor source hashes')
    config = old['build']
    expected = [str(tools['taskset']), '-c', '0,2', str(tools['verilator']),
                '--lint-only', '-Wall', '--threads', '1', '--top-module', config['top'],
                *[f'-G{k}={v}' for k, v in config['parameters'].items()],
                '--Mdir', str(build), *[str(root/k) for k in config['sv_sources']]]
    require(command == expected, 'exact ordered lint argv')
    require(digest(normalize((root/STDERR).read_bytes(), old['source_root'])) == NORMALIZED_SHA,
            'baseline normalized diagnostic identity')
    require(digest(normalize(stderr, root)) == NORMALIZED_SHA, 'unlisted/missing/changed diagnostic')
    return dict(status='accepted_exact_inherited_lint_debt_NOT_clean_lint',
                warning_count=2, raw_returncode=code, raw_stderr_sha256=digest(stderr),
                normalized_stderr_sha256=NORMALIZED_SHA, failed_manifest_sha256=BASELINE_SHA,
                independent_debt_review_sha256=REVIEW_SHA,
                scope='Only unchanged L16/F0 control; no other fields/lanes/roles inherit this admission.')


def adapted_source(raw):
    require(digest(raw) == PARENT_SHA, 'frozen launcher identity')
    text = raw.decode()
    before = "SELF = '"+PARENT+"'"
    require(text.count(before) == 1, 'SELF anchor')
    text = text.replace(before, "SELF = '"+SELF+"'", 1)
    before = "        require(child.returncode == expected, 'unexpected return code: ' + name)"
    require(text.count(before) == 1, 'return-code anchor')
    after = """        if name == 'lint':
            report['lint_debt'] = accept_exact_lint_debt(name, command, child.returncode,
                log.read_bytes(), error_log.read_bytes(), manifest, toolpaths, root, build)
            save()
        else:
            require(child.returncode == expected, 'unexpected return code: ' + name)"""
    return text.replace(before, after, 1)


def load_parent():
    path = Path(__file__).resolve().parent/Path(PARENT).name
    module = types.ModuleType('_f2_exact_debt_cpu02_v3')
    module.__file__ = str(Path(__file__).resolve())
    module.accept_exact_lint_debt = accept_exact_lint_debt
    exec(compile(adapted_source(path.read_bytes()), str(path)+'[exact-lint-debt-v3]', 'exec'), module.__dict__)
    return module


if __name__ == '__main__':
    load_parent().main()
