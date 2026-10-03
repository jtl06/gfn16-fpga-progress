import unittest

from fpga.host.r15_arithmetic import (Checkpoint, Features, HostFault, SoftwareBackend,
                                    genefer_trace, run_verified_window)
from fpga.host.r15_genefer_proof import (challenge, decode_proof, digits, encode_proof,
                                      generate_proof, hash64, verify_proof)


class R15HostArithmetic(unittest.TestCase):
    def backend(self):
        return SoftwareBackend(10, 32, enabled=True)

    def test_defaults_off(self):
        self.assertFalse(any(Features().__dict__.values()))
        with self.assertRaisesRegex(HostFault, 'OFF'):
            SoftwareBackend(10, 32)
        with self.assertRaisesRegex(HostFault, 'OFF'):
            encode_proof(10, 32, (1, 2))

    def test_source_exact_genefer_gl_schedule(self):
        for base, n in ((10, 32), (599, 32), (600, 32)):
            exponent = base**n
            backend = SoftwareBackend(base, n, enabled=True)
            result, product, valid, _ = genefer_trace(backend, exponent, 7)
            self.assertEqual(result, pow(2, exponent, exponent+1))
            self.assertTrue(valid)
            self.assertNotEqual(product, 0)

    def test_verified_window_and_corruption_rollback(self):
        backend = self.backend()
        cp = Checkpoint(10, 32, 0x120001, 0, 0, 7, 'source-fixture')
        bits = [True, False, True, True]*4
        good = run_verified_window(backend, bits, 4, cp, enabled=True)
        self.assertIsNotNone(good)
        expected = 7
        for bit in bits:
            expected = expected*expected*(2 if bit else 1) % backend.modulus
        self.assertEqual(good.value, expected)
        def flip(b, i):
            if i == 3:
                b.load((b.read()+1) % b.modulus)
        bad = run_verified_window(backend, bits, 4, cp, enabled=True, inject=flip)
        self.assertIsNone(bad)
        self.assertEqual(backend.read(), cp.value)
        # Replay from the old verified checkpoint, not the corrupt result.
        replay = run_verified_window(backend, bits, 4, cp, enabled=True)
        self.assertEqual(replay, good)

    def test_checkpoint_restart_corrupt_truncated_wrong_owner(self):
        cp = Checkpoint(10, 32, 1, 0, 8, 91, 'own-source')
        raw = cp.encode()
        self.assertEqual(Checkpoint.decode(raw, expected_source='own-source',
                                         expected_owner=1, expected_context=0), cp)
        for bad in (raw[:-1], raw.replace(b'0x5b', b'0x5c'), b'garbage'):
            with self.assertRaises(HostFault):
                Checkpoint.decode(bad, expected_source='own-source', expected_owner=1,
                                  expected_context=0)
        with self.assertRaisesRegex(HostFault, 'IDENTITY'):
            Checkpoint.decode(raw, expected_source='peer', expected_owner=1, expected_context=0)

    def test_proof_full_exponent_and_roundtrip(self):
        for base in (10, 599, 600):
            backend = SoftwareBackend(base, 32, enabled=True)
            exponent = base**32
            raw = generate_proof(backend, exponent, 3, enabled=True)
            mus = decode_proof(raw, base, 32, enabled=True)
            self.assertEqual(mus[0], pow(2, exponent, exponent+1))
            self.assertTrue(verify_proof(backend, exponent, raw, enabled=True))
            self.assertEqual(encode_proof(base, 32, mus, enabled=True), raw)

    def test_proof_crc_truncation_profile_and_mathematical_negative(self):
        backend = self.backend()
        exponent = 10**32
        raw = generate_proof(backend, exponent, 2, enabled=True)
        for bad in (raw[:-1], raw+b'x', raw[:-4]+b'xxxx'):
            with self.assertRaises(HostFault):
                decode_proof(bad, 10, 32, enabled=True)
        with self.assertRaisesRegex(HostFault, 'PROFILE'):
            decode_proof(raw, 11, 32, enabled=True)
        mus = list(decode_proof(raw, 10, 32, enabled=True))
        mus[-1] = (mus[-1]+1) % backend.modulus
        repaired_crc = encode_proof(10, 32, mus, enabled=True)
        self.assertFalse(verify_proof(backend, exponent, repaired_crc, enabled=True))

    def test_special_gint_wire_and_zero_hash(self):
        special = 10**32
        raw = encode_proof(10, 32, (special, 1), enabled=True)
        self.assertEqual(raw[16:20], b'\xff'*4)
        self.assertEqual(decode_proof(raw, 10, 32, enabled=True), (special, 1))
        self.assertGreaterEqual(challenge(digits(special, 10, 32)), 2)
        with self.assertRaisesRegex(HostFault, 'HASH_ZERO'):
            hash64((0,)*32)


if __name__ == '__main__':
    unittest.main()
