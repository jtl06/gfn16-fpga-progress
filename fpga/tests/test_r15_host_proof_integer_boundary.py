"""Small source-only regressions; real GMP fixture lives in chosen-GMP recipe."""
import importlib.util
from pathlib import Path
import unittest

from fpga.host.r15_arithmetic import HostFault, SoftwareBackend
from fpga.host.r15_genefer_proof import digits, generate_proof, verify_proof


class BoxedInteger(int):
    pass


class BoxedModulus(int):
    def __rmod__(self, other):
        return BoxedInteger(int(other) % int(self))


class IntegerBoundary(unittest.TestCase):
    def original(self):
        path = Path(__file__).resolve().parents[1] / (
            'artifacts/r15-host-software-normal-azure-v3/packet-v1/'
            'source/fpga/host/r15_genefer_proof.py')
        spec = importlib.util.spec_from_file_location('fpga.host._failed_v3_proof', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_literal_python_reference_bytes_unchanged(self):
        old = self.original()
        for base in (10, 599, 600):
            a = SoftwareBackend(base, 32, enabled=True)
            b = SoftwareBackend(base, 32, enabled=True)
            exponent = base**32
            raw = generate_proof(a, exponent, 3, enabled=True)
            self.assertEqual(raw, old.generate_proof(b, exponent, 3, enabled=True))
            self.assertEqual(len(raw), 556)
            self.assertTrue(verify_proof(a, exponent, raw, enabled=True))

    def test_boxed_modular_result_reproduces_old_failure_without_loosening_codec(self):
        old = self.original()
        before = SoftwareBackend(600, 32, enabled=True)
        before.modulus = BoxedModulus(before.modulus)
        with self.assertRaisesRegex(HostFault, 'PROOF_RESIDUE'):
            old.generate_proof(before, 600**32, 3, enabled=True)
        after = SoftwareBackend(600, 32, enabled=True)
        after.modulus = BoxedModulus(after.modulus)
        raw = generate_proof(after, 600**32, 3, enabled=True)
        reference = SoftwareBackend(600, 32, enabled=True)
        self.assertEqual(raw, generate_proof(reference, 600**32, 3, enabled=True))
        for invalid in (True, 1.0, BoxedInteger(1), -1, 600**32+1):
            with self.assertRaisesRegex(HostFault, 'PROOF_RESIDUE'):
                digits(invalid, 600, 32)


if __name__ == '__main__':
    unittest.main()
