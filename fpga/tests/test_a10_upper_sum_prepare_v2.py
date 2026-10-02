"""Pure source/contract checks; no HDL, compiler or executable invocation."""
from pathlib import Path
import tempfile
import unittest

from fpga.reference import a10_upper_sum_native_v2 as native
from fpga.reference import a10_upper_sum_prepare_v2 as prepare


class UpperSumPreparation(unittest.TestCase):
    def test_frozen_pair_exact_sources_and_no_engine_adapter(self):
        self.assertEqual(native.verify(), native.PINS)
        for field in range(3):
            manifest, files = prepare.role(field)
            p, q = native.field_basis(field)
            self.assertEqual(manifest['build']['sv_sources'], list(native.SV_SOURCES))
            self.assertEqual(manifest['build']['parameters'], dict(P=p, Q=q))
            self.assertEqual(manifest['build']['top'], native.TOP)
            self.assertEqual(len(files), 11)
            self.assertEqual([step['expected_returncode'] for step in manifest['steps']], [0, 1])
            self.assertEqual(manifest['upper_sum']['reset_ages'], list(range(7)))
            self.assertFalse(any('host_image' in name or 'host16_engine' in name for name in files))

    def test_independent_event_counts(self):
        self.assertEqual(native.native_counts(), dict(cycles=3443, accepted=3254, outputs=3249,
                         ct=1059, gs=1058, normalized=1132, bubbles=181, resets=8, cancelled=5,
                         before_checks=6886, latency=5, ii=1))
        self.assertEqual(7**3*3 + 2048 + 64 + 77 + 8 + 7 + 7*3, 3254)
        self.assertEqual(3443 - 3254 - 8, 181)

    def test_ordinary_R_inverse_basis(self):
        for p, q in native.FIELDS:
            # Parent sparse reducer uses subtractive REDC, hence Q=P^-1.
            self.assertEqual((p*q) % 2**32, 1)
            inverse = pow(2**32 % p, p-2, p)
            self.assertEqual(inverse, pow(2**32, -1, p))
            self.assertEqual((2**32*inverse) % p, 1)

    def test_exact_typed_outputs_and_all_mutants(self):
        for field in range(3):
            for negative in (False, True):
                value = native.contracts(field)['negative' if negative else 'normal']
                config = dict(field=field, negative=negative)
                self.assertEqual(native.validate(value['stdout'], value['stderr'], value['returncode'], config, {})['status'],
                                 'PASS_expected_contracts')
                for out, err, rc in ((value['stdout']+'PASS\n', value['stderr'], value['returncode']),
                                     (value['stdout'], value['stderr']+'extra\n', value['returncode']),
                                     (value['stdout'], value['stderr'], 1-value['returncode'])):
                    with self.assertRaisesRegex(ValueError, 'TYPED_OUTPUT'):
                        native.validate(out, err, rc, config, {})
            normal = native.contracts(field)['normal']
            with self.assertRaisesRegex(ValueError, 'TYPED_OUTPUT'):
                native.validate(normal['stdout'].replace('latency=5', 'latency=6'), '', 0,
                                dict(field=field, negative=False), {})
        for invalid in (-1, 3, 0.0, True, '0'):
            with self.assertRaisesRegex(ValueError, 'FIELD'): native.contracts(invalid)
        with self.assertRaisesRegex(ValueError, 'NATIVE_CONFIG'):
            native.validate('', '', 1, dict(field=0, negative=1), {})

    def test_source_drift_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in native.PINS:
                path = root/name; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((native.ROOT/name).read_bytes())
            native.verify(root)
            target = root/native.PAIR; original = target.read_bytes(); target.write_bytes(original+b'\n')
            with self.assertRaisesRegex(ValueError, 'SOURCE_DRIFT'): native.verify(root)
            target.write_bytes(original); target.unlink(); target.symlink_to(native.ROOT/native.PAIR)
            with self.assertRaisesRegex(ValueError, 'SOURCE_DRIFT'): native.verify(root)


if __name__ == '__main__': unittest.main()
