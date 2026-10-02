"""Finite source/typed contract checks only; never invokes HDL or ELF."""
from pathlib import Path
import tempfile
import unittest

from fpga.reference import stream27_host_image_native_v1 as native
from fpga.reference import stream27_host_image_prepare_v1 as prepare


class HostImagePreparation(unittest.TestCase):
    def test_exact_promoted_t5b_closure(self):
        self.assertEqual(native.verify(), native.PINS)
        self.assertEqual(len(native.T5B_PINS), 16)
        self.assertEqual(native.T5B_PINS['rtl/kernel/' + native.T5B_TOP + '.sv'], native.T5B_TOP_SHA)

    def test_four_roles_pair_actual_top_and_typed_steps(self):
        for aw in (5, 8):
            for p in (8, 16):
                manifest, files = prepare.role(aw, p)
                self.assertEqual(manifest['build']['sv_sources'], [*native.T5B_PINS, native.SV, native.PAIR])
                self.assertEqual(len(manifest['build']['sv_sources']), 18)
                self.assertEqual(manifest['build']['parameters'], dict(AW=aw, P=p))
                self.assertTrue(set(manifest['build']['sv_sources'] + [native.CPP]) <= files.keys())
                self.assertEqual(len(files), 27)
                self.assertEqual([step['expected_returncode'] for step in manifest['steps']], [0, 1])
                self.assertEqual(manifest['host_image']['parent_start'], 0)
                self.assertEqual(manifest['host_image']['geometry']['read_edge'], 'E0_after_NBA')
                self.assertFalse(manifest['host_image']['geometry']['payload_register_after_RAM'])

    def test_exact_typed_positive_negative_and_mutants(self):
        for aw in (5, 8):
            for p in (8, 16):
                for negative in (False, True):
                    contract = native.contracts(aw, p)['negative' if negative else 'normal']
                    config = dict(aw=aw, p=p, negative=negative)
                    self.assertEqual(native.validate(contract['stdout'], contract['stderr'], contract['returncode'], config, {})['status'],
                                     'PASS_expected_contracts')
                    for out, err, rc in ((contract['stdout'] + 'PASS\n', contract['stderr'], contract['returncode']),
                                         (contract['stdout'], contract['stderr'] + 'extra\n', contract['returncode']),
                                         (contract['stdout'], contract['stderr'], 1 - contract['returncode'])):
                        with self.assertRaisesRegex(ValueError, 'TYPED_OUTPUT'):
                            native.validate(out, err, rc, config, {})
                normal = native.contracts(aw, p)['normal']
                with self.assertRaisesRegex(ValueError, 'TYPED_OUTPUT'):
                    native.validate(normal['stdout'].replace('read_edge=E0', 'read_edge=E1'), '', 0,
                                    dict(aw=aw, p=p, negative=False), {})

    def test_fullN_and_noninteger_geometries_rejected(self):
        for aw, p in ((16, 8), (4, 8), (5, 4), (5.0, 8), (5, True)):
            with self.assertRaisesRegex(ValueError, 'SMALL_GEOMETRY'):
                native.contracts(aw, p)

    def test_source_drift_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in native.PINS:
                path = root/name; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((native.ROOT/name).read_bytes())
            native.verify(root)
            target = root/native.PAIR; original = target.read_bytes()
            target.write_bytes(original + b'\n')
            with self.assertRaisesRegex(ValueError, 'SOURCE_DRIFT'):
                native.verify(root)
            target.write_bytes(original); target.unlink(); target.symlink_to(native.ROOT/native.PAIR)
            with self.assertRaisesRegex(ValueError, 'SOURCE_DRIFT'):
                native.verify(root)


if __name__ == '__main__':
    unittest.main()
