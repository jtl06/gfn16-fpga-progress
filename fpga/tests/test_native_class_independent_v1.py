"""Independent pure r38 integration checks; never run HDL or native tools."""
import ast
import hashlib
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest

from fpga.tools import native_class_v1 as candidate


class IndependentClassIntegration(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.out = self.root / 'logs'
        self.out.mkdir()
        self.raw = candidate.host.static_module().pinned(
            'tools/native_source_gate_aethia_cpu02_v2.py').read_bytes()

    def test_exact_four_source_replacements_all_static_profiles(self):
        for identifier in candidate.SELECTIONS:
            selected = candidate.profile(identifier)
            old = candidate.host.adapted_source(self.raw, selected)
            new = candidate.adapted_source(self.raw, selected)
            replacements = [
                ('SELF = ' + repr(candidate.host.SELF), 'SELF = ' + repr(candidate.SELF)),
                ("'--cc', '--exe', '--build', '-j'",
                 "'--cc', '--exe', '--build', '-Wall', '-Wno-fatal', '-j'"),
                ("'--lint-only', '-Wall', '--threads'",
                 "'--lint-only', '-Wall', '-Wno-fatal', '--threads'"),
                ("if name == 'lint':\n            report['lint_admission'] = admit_lint(child.returncode, log.read_bytes(), error_log.read_bytes(), manifest, profile, root)\n            save()",
                 "if name in ('lint', 'build'):\n            try:\n                report[name + '_admission'] = classify(child.returncode, log.read_bytes(), error_log.read_bytes(), manifest, root)\n            except LintClassError as error:\n                report[name + '_admission'] = error.receipt\n                save()\n                raise\n            save()"),
            ]
            expected = old
            for before, after in replacements:
                self.assertEqual(expected.count(before), 1)
                expected = expected.replace(before, after, 1)
            self.assertEqual(new, expected)
            ast.parse(new)
            self.assertEqual(new.count("'-Wno-fatal'"), 2)
            self.assertIn('check_scratch_quota(scratch', new)
            self.assertIn('pass_fds=LEASE_FDS', new)
            self.assertIn('fcntl.LOCK_EX | fcntl.LOCK_NB', new)
            self.assertIn('os.killpg(child.pid, signal.SIGKILL)', new)
            self.assertLess(new.index("run('lint', lint)"), new.index("run('build', command)"))

    def harness(self, outcomes):
        text = candidate.adapted_source(self.raw, candidate.profile('gcp-c4d-static01-v1'))
        execute = next(node for node in ast.parse(text).body
                       if isinstance(node, ast.FunctionDef) and node.name == 'execute')
        run_node = next(node for node in execute.body
                        if isinstance(node, ast.FunctionDef) and node.name == 'run')
        calls, saves = [], []
        report = {'steps': [], 'artifacts': {}}
        pending = list(outcomes)

        def popen(command, **options):
            code, output, error = pending.pop(0)
            calls.append((command, options['pass_fds']))
            options['stdout'].write(output)
            options['stderr'].write(error)
            return SimpleNamespace(returncode=code, poll=lambda: code, wait=lambda: code)

        def remember(path):
            report['artifacts'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()

        namespace = dict(
            guard=lambda: None, time=time, resource=SimpleNamespace(
                RUSAGE_CHILDREN=0, getrusage=lambda _: SimpleNamespace(
                    ru_utime=0.0, ru_stime=0.0, ru_maxrss=0)),
            out=self.out, toolpaths={'taskset': Path('/mock/taskset')},
            profile={'cpus': [0, 1]}, root=self.root, env={},
            subprocess=SimpleNamespace(Popen=popen), LEASE_FDS=(101, 102),
            lock=SimpleNamespace(fileno=lambda: 103), remember=remember,
            sha=lambda path: hashlib.sha256(path.read_bytes()).hexdigest(),
            report=report, save=lambda: saves.append(True),
            manifest={'build': {'top': 'fixture'}, 'sources': {}},
            classify=candidate.classes.classify,
            LintClassError=candidate.classes.LintClassError,
            require=lambda ok, why: None if ok else (_ for _ in ()).throw(ValueError(why)))
        code = ast.fix_missing_locations(ast.Module(body=[run_node], type_ignores=[]))
        exec(compile(code, '<independent-r38-run-fragment>', 'exec'), namespace)
        return namespace['run'], report, calls, saves

    def test_actual_run_fragment_styles_reach_build_with_leases(self):
        run, report, calls, _ = self.harness([
            (0, 'lint information\n', '%Warning-UNUSEDSIGNAL: fixture.sv:1:1: unused\n'),
            (0, 'compiler information\n', '%Warning-DECLFILENAME: fixture.sv:1:1: naming\n')])
        run('lint', ['/mock/verilator', '--lint-only', '-Wall', '-Wno-fatal'])
        run('build', ['/mock/verilator', '--build', '-Wall', '-Wno-fatal'])
        self.assertEqual([row['name'] for row in report['steps']], ['lint', 'build'])
        self.assertEqual(report['lint_admission']['class_counts'], {'UNUSEDSIGNAL': 1})
        self.assertEqual(report['build_admission']['class_counts'], {'DECLFILENAME': 1})
        self.assertTrue(all(descriptors == (101, 102, 103) for _, descriptors in calls))

    def test_actual_run_fragment_lint_defect_stops_before_build(self):
        run, report, calls, saves = self.harness([
            (0, '', '%Warning-WIDTHTRUNC: fixture.sv:1:1: lost bits\n')])
        with self.assertRaises(candidate.classes.LintClassError):
            run('lint', ['/mock/verilator', '--lint-only', '-Wall', '-Wno-fatal'])
        self.assertEqual(len(calls), 1)
        self.assertEqual(report['lint_admission']['status'], 'blocked_lint_classes')
        self.assertEqual(report['lint_admission']['fatal_class_counts'], {'WIDTHTRUNC': 1})
        self.assertNotIn('build_admission', report)
        self.assertGreaterEqual(len(saves), 2)

    def test_actual_run_fragment_build_defect_stops_before_probe(self):
        run, report, calls, saves = self.harness([
            (0, '', ''), (0, '', '%Warning-UNOPTFLAT: fixture.sv:1:1: cycle\n')])
        run('lint', ['/mock/verilator', '--lint-only', '-Wall', '-Wno-fatal'])
        with self.assertRaises(candidate.classes.LintClassError):
            run('build', ['/mock/verilator', '--build', '-Wall', '-Wno-fatal'])
        self.assertEqual(len(calls), 2)
        self.assertEqual(report['build_admission']['status'], 'blocked_lint_classes')
        self.assertEqual(report['build_admission']['fatal_class_counts'], {'UNOPTFLAT': 1})
        self.assertEqual([row['name'] for row in report['steps']], ['lint', 'build'])
        self.assertGreaterEqual(len(saves), 4)


if __name__ == '__main__':
    unittest.main()
