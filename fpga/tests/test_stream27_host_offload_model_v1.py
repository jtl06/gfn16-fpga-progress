"""Small bounded B model checks; never native/full-N qualification."""
from dataclasses import replace
from unittest import mock
import unittest

from reference import stream27_host_offload_model_v1 as b
from reference import stream27_canonical_image_corpus_v1 as corpus
from reference import stream27_canonical_image_model_v1 as canonical
from reference import stream_ntt_blockwrap2_proposal as block


class HostBoundaryTests(unittest.TestCase):
    def test_profile_matches_restoring_setup_and_bounds(self):
        for n in (32, 256, 65536):
            floor = b.geometry(n, 16)['minimum_base']
            for base in (floor, 604832956, 1000000000):
                p = b.profile(n, 16, base, 42)
                rem, quotient = 1, 0
                for _ in range(96):
                    rem <<= 1
                    quotient <<= 1
                    if rem >= base:
                        rem -= base
                        quotient |= 1
                self.assertEqual((p.reciprocal, p.remainder), (quotient, rem))
                B, K = base - 1, 2 * n + 384
                self.assertEqual(p.coefficient_limit, 2 * ((n + 48) * B * B + 64 * B * K + 16 * K * K))
                self.assertLess(p.coefficient_limit, 1 << 77)

    def test_cold_full_word_converter_and_physical_lane_layout(self):
        for n in (32, 256):
            base = b.geometry(n, 16)['minimum_base']
            digits = [(j * 17) % base for j in range(n)]
            digits[3] = -1
            p = b.profile(n, 16, base, 7)
            packet = b.prepare_cold(digits, [-1] * 16, [2 * n + 384] * 16, p, context=1, epoch=65535)
            self.assertIs(b.validate_cold(packet), packet)
            for f, prime in enumerate(b.converter.FIELDS):
                for row in range(n // 16):
                    for lane in range(16):
                        logical = b.arithmetic.bit_reverse(lane, 4) * (n // 16) + row
                        self.assertEqual(packet.field_rows[f][row][lane], digits[logical] % prime)
                self.assertEqual(packet.correction_low[f], (prime - 1,) * 16)

    def test_malformed_full32_input_cannot_be_trimmed(self):
        p = b.profile(32, 16, 300, 0)
        for bad in (300, 1000000000, 0x80000000, 0xfffffffe, 1 << 32, True):
            with self.assertRaises(ValueError):
                b.prepare_cold([bad] + [0] * 31, [0] * 16, [0] * 16, p, context=0, epoch=0)
        packet = b.prepare_cold([0] * 32, [0] * 16, [0] * 16, p, context=0, epoch=0)
        planes = list(packet.field_rows)
        rows = list(planes[0]); rows[0] = (1 << 27,) + rows[0][1:]; planes[0] = tuple(rows)
        with self.assertRaisesRegex(ValueError, 'CANONICAL27'):
            b.validate_cold(replace(packet, field_rows=tuple(planes)))

    def test_profile_correction_geometry_and_owner_negatives(self):
        p = b.profile(32, 16, 300, 0)
        with self.assertRaises(ValueError):
            b.validate_profile(replace(p, reciprocal=p.reciprocal + 1))
        for c0, c1 in (([300] * 16, [0] * 16), ([0] * 16, [449] * 16)):
            with self.assertRaises(ValueError):
                b.prepare_cold([0] * 32, c0, c1, p, context=0, epoch=0)
        for n, lanes in ((64, 16), (32, 8), (True, 16)):
            with self.assertRaises(ValueError):
                b.profile(n, lanes, 1000000000, 0)

    def test_full_conversion_is_not_a_coordinator_numeric_path(self):
        p = b.profile(65536, 16, 604832956, 0)
        with mock.patch.object(b.sys, 'platform', 'darwin'):
            with self.assertRaisesRegex(ValueError, 'AETHIA_ONLY'):
                b.prepare_cold((), (), (), p, context=0, epoch=0)

    def test_existing_small_canonical_corpus_bit_exact(self):
        checked = 0
        for aw in (5, 8):
            for base, digits, c0, c1 in corpus.corpus(aw, 16):
                p = b.profile(1 << aw, 16, base, 7)
                owner = (31 << 24) | (65535 << 8) | 7
                packet = b.FinalPacket(p, 1, owner, tuple(digits), tuple(c0), tuple(c1))
                result = b.finalize(packet, expected_context=1, expected_owner=owner)
                self.assertEqual(result.digits, canonical.independent_integer_oracle(digits, c0, c1, base))
                checked += 1
        self.assertEqual(checked, 84)

    def test_small_squared_input_output_composition(self):
        # This proves only the host math composition at two small geometries.
        # The native endpoint, PRP loop and full-size ladder are NOT exercised.
        for n in (32, 256):
            base = b.geometry(n, 16)['minimum_base']
            p = b.profile(n, 16, base, 0)
            source = tuple((j * 71 + 19) % base for j in range(n))
            cold = b.prepare_cold(source, [0] * 16, [0] * 16, p, context=0, epoch=0)
            b.validate_cold(cold)
            coefficients = b.arithmetic.direct_negacyclic_square(source, double_bit=1)
            state, _ = block.carry_serial(coefficients, base, 16)
            output = b.finalize(b.FinalPacket(p, 0, 0, state.digits, state.c0, state.c1), expected_context=0, expected_owner=0)
            expected = b.arithmetic.canonicalize(coefficients, base)
            self.assertEqual(output.digits, tuple(expected))

    def test_payload_bytes_exact_word_order_and_zero_extended_limits(self):
        p = b.profile(32, 16, 300, 7)
        packet = b.prepare_cold([0xffffffff] + [0] * 31, [-1] + [0] * 15,
                                [448] + [0] * 15, p, context=0, epoch=0)
        raw = b.cold_payload_bytes(packet)
        self.assertEqual(len(raw), 4 * (3 * 32 + 6 * 16))
        self.assertEqual(raw[:4], (b.converter.FIELDS[0] - 1).to_bytes(4, 'little'))
        words = [int.from_bytes(raw[j:j + 4], 'little') for j in range(0, len(raw), 4)]
        self.assertEqual(words[3 * 32], b.converter.FIELDS[0] - 1)
        profile = b.profile_payload_bytes(p)
        self.assertEqual(len(profile), 32)
        self.assertEqual(int.from_bytes(profile[8:20], 'little'), p.reciprocal)
        self.assertEqual(int.from_bytes(profile[20:32], 'little'), p.coefficient_limit)
        self.assertLess(int.from_bytes(profile[28:32], 'little'), 1 << 13)

    def test_raw_final_row_order_decode_and_signed_boundaries(self):
        p = b.profile(32, 16, 300, 7)
        digits = list(range(32)); c0 = [-1] + [0] * 15; c1 = [448] + [0] * 15
        words = [digits[lane * 2 + row] for row in range(2) for lane in range(16)] + c0 + c1
        raw = b''.join((w & 0xffffffff).to_bytes(4, 'little') for w in words)
        packet = b.decode_final_payload(raw, p, context=1, owner=7)
        self.assertEqual((packet.digits, packet.c0, packet.c1), (tuple(digits), tuple(c0), tuple(c1)))
        self.assertEqual(b.finalize(packet, expected_context=1, expected_owner=7).digits,
                         canonical.independent_integer_oracle(digits, c0, c1, 300))
        with self.assertRaises(ValueError):
            b.decode_final_payload(raw[:-4], p, context=1, owner=7)

    def test_special_image_and_final_owner_ranges(self):
        p = b.profile(32, 16, 300, 3)
        packet = b.FinalPacket(p, 0, 3, (0,) * 32, (-1,) + (0,) * 15, (0,) * 16)
        self.assertEqual(b.finalize(packet, expected_context=0, expected_owner=3).digits, (-1,) + (0,) * 31)
        for bad in (replace(packet, owner=2), replace(packet, c1=(449,) * 16),
                    replace(packet, digits=(-1,) + (0,) * 31), replace(packet, context=1)):
            with self.assertRaises(ValueError):
                b.finalize(bad, expected_context=0, expected_owner=3)


if __name__ == '__main__':
    unittest.main()
