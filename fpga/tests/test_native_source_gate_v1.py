"""Portable launcher safety contracts, no HDL compiler or native gate runs."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fpga.tools import native_source_gate_v1 as r


class NativeSourceGateTests(unittest.TestCase):
    def test_profiles_are_explicit_and_separate(self):
        self.assertEqual(set(r.PROFILES), {'aethia', 'gfn16-pilot-c4'})
        self.assertEqual(r.PROFILES['aethia']['cpus'], [4, 6])
        self.assertEqual(r.PROFILES['gfn16-pilot-c4']['cpus'], [0, 1])
        self.assertNotEqual(r.PROFILES['aethia']['hashes']['compiler'], r.PROFILES['gfn16-pilot-c4']['hashes']['compiler'])
        self.assertEqual(r.PROFILES['aethia']['lock'], '/home/jtl/gfn-fpga-lab/agent-work/square-core/fpga/artifacts/compile.lock')

    def test_complete_source_closure_rejects_added_header_and_tamper(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            (root / 'a.cpp').write_text('int x;\n')
            pins = {'a.cpp': r.sha(root / 'a.cpp')}
            r.check_sources(root, pins)
            (root / 'unlisted.h').write_text('different')
            with self.assertRaisesRegex(ValueError, 'exact source'):
                r.check_sources(root, pins)
            pins['unlisted.h'] = r.sha(root / 'unlisted.h')
            (root / 'a.cpp').write_text('tamper')
            with self.assertRaisesRegex(ValueError, 'pin/type'):
                r.check_sources(root, pins)

    def test_symlink_and_hardlink_sources_rejected(self):
        for kind in ('symlink', 'hardlink'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve()
                (root / 'a').write_text('x')
                if kind == 'symlink':
                    (root / 'b').symlink_to(root / 'a')
                else:
                    os.link(root / 'a', root / 'b')
                pins = {n: r.sha(root / n) for n in ('a', 'b')}
                with self.assertRaises(ValueError):
                    r.check_sources(root, pins)

    def test_non_source_artifacts_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            (root / 'cached.pyc').write_bytes(b'compiled')
            with self.assertRaisesRegex(ValueError, 'pin/type'):
                r.check_sources(root, {'cached.pyc': r.sha(root / 'cached.pyc')})

    def test_unsafe_names_rejected(self):
        for name in ('', '.', '../a', '/a', 'a/../b', './a', 'a//b', True):
            with self.subTest(name=name), self.assertRaises(ValueError):
                r.relative(name)

    def test_no_inherited_environment_and_explicit_pythonpath(self):
        with patch.dict(os.environ, {'LD_PRELOAD': 'bad', 'PYTHONPATH': '/bad', 'API_KEY': 'secret', 'MAKEFLAGS': '-j99'}):
            env = r.clean_env(Path('/snapshot/fpga'), Path('/scratch/tmp'), r.PROFILES['aethia'])
        self.assertEqual(env['PYTHONPATH'], '/snapshot:/snapshot/fpga')
        self.assertEqual(env['CCACHE_DISABLE'], '1')
        self.assertTrue(all(k not in env for k in ('LD_PRELOAD', 'API_KEY', 'MAKEFLAGS')))

    def test_command_tokens_do_not_invoke_shell(self):
        self.assertEqual(r.expand(['{exe}', '{root}/vectors.txt'], Path('/bin/model'), Path('/snapshot/fpga')),
                         ['/bin/model', '/snapshot/fpga/vectors.txt'])
        with self.assertRaisesRegex(ValueError, 'unknown command'):
            r.expand(['{exe}', '{other}'], Path('/bin/model'), Path('/snapshot'))

    def test_manifest_sha_rejected_before_host_or_process(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'manifest.json'; path.write_text('{}')
            with patch.object(r.socket, 'gethostname', side_effect=AssertionError('too early')):
                with self.assertRaisesRegex(ValueError, 'manifest SHA'):
                    r.load_manifest(path, '0' * 64)

    def test_off_host_rejected_before_source_read_or_subprocess(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'manifest.json'
            path.write_text('{"schema":"native-source-gate-v1","status":"prepared_not_executed","host":"aethia"}')
            with patch.object(r.socket, 'gethostname', return_value='mac'), patch.object(r.subprocess, 'Popen', side_effect=AssertionError('must not execute')):
                with self.assertRaisesRegex(ValueError, 'approved native host'):
                    r.execute(path, r.sha(path), Path(folder) / 'result')
            self.assertFalse((Path(folder) / 'result').exists())

    def test_runtime_guards_and_frozen_lock_are_present(self):
        # Structural backstop; runtime cgroup enforcement is a native admission gate.
        text = Path(r.__file__).read_text()
        for token in ('fcntl.LOCK_EX | fcntl.LOCK_NB', 'os.killpg(child.pid, signal.SIGKILL)',
                      'start_new_session=True', "'effective taskset affinity'", "'finite aggregate <=4GiB cgroup'",
                      "'finite aggregate <=200% CPU'", "'completed_native_commands_unreviewed'",
                      "'-c', ','.join(map(str, profile['cpus']))", "'preserved executable identity'"):
            self.assertIn(token, text)


if __name__ == '__main__':
    unittest.main()
