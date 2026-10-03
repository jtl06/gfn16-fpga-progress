from dataclasses import replace
from fractions import Fraction
import unittest

from fpga.host.r15_arithmetic import HostFault, SoftwareBackend
from fpga.host.r15_image_codec import (CANONICAL_A, RAW_B, Publication, ExportWord,
    CanonicalCollector, encode_signed96, decode_signed96, load_software_backend)


class ImageCodec(unittest.TestCase):
    def snapshot(self):
        return Publication(32, 600, 1, (4 << 24) | (2 << 8) | 3, 5, True)

    def word(self, index, value, **changes):
        s = self.snapshot()
        return replace(ExportWord(CANONICAL_A, s.context, s.owner, index,
                                  encode_signed96(value)), **changes)

    def image(self, digits):
        c = CanonicalCollector(self.snapshot(), enabled=True)
        for i, value in enumerate(digits):
            c.accept(self.word(i, value))
        return c.finish()

    def test_default_off_and_formats(self):
        with self.assertRaisesRegex(HostFault, 'OFF'):
            CanonicalCollector(self.snapshot())
        for format, error in ((RAW_B, 'UNQUALIFIED'), ('arbitrary', 'UNKNOWN')):
            with self.assertRaisesRegex(HostFault, error):
                CanonicalCollector(self.snapshot(), enabled=True, format=format)

    def test_coherent_owner_and_completed_count(self):
        for s in (replace(self.snapshot(), coherent_ack=False),
                  replace(self.snapshot(), completed=4),
                  replace(self.snapshot(), completed=1 << 32),
                  replace(self.snapshot(), owner=1 << 56)):
            with self.assertRaises(HostFault):
                CanonicalCollector(s, enabled=True)

    def test_normal_and_special_load_without_finalizer(self):
        b = SoftwareBackend(600, 32, enabled=True)
        image = self.image([3, 2] + [0] * 30)
        self.assertEqual(load_software_backend(image, b), 1203)
        self.assertEqual(b.read(), 1203)
        special = self.image([-1] + [0] * 31)
        self.assertTrue(special.special)
        self.assertEqual(load_software_backend(special, b), b.modulus - 1)
        with self.assertRaisesRegex(HostFault, 'PROFILE'):
            load_software_backend(image, SoftwareBackend(599, 32, enabled=True))

    def test_full96_before_canonical_range_no_trim(self):
        for value in (1 << 32, 1 << 64, -(1 << 64), -2, 600):
            c = CanonicalCollector(self.snapshot(), enabled=True)
            self.assertEqual(decode_signed96(encode_signed96(value)), value)
            with self.assertRaisesRegex(HostFault, 'NO_TRIM'):
                c.accept(self.word(0, value))
            self.assertTrue(c.failed)

    def test_non_builtin_integer_modulus_special_converts_before_backend_load(self):
        # A coordinator-safe stand-in for a non-int GMP modulus: subtraction
        # returns a distinct numeric type, while backend.load requires int.
        b = SoftwareBackend(600, 32, enabled=True)
        b.modulus = Fraction(b.modulus)
        value = load_software_backend(self.image([-1] + [0] * 31), b)
        self.assertIs(type(value), int)
        self.assertEqual(b.read(), int(b.modulus - 1))

    def test_partial_duplicate_gap_and_peer_records_are_not_publishable(self):
        c = CanonicalCollector(self.snapshot(), enabled=True)
        c.accept(self.word(0, 1))
        with self.assertRaisesRegex(HostFault, 'COMPLETE'):
            c.finish()
        for bad in (self.word(0, 2), self.word(2, 2),
                    self.word(1, 2, context=0),
                    self.word(1, 2, owner=self.snapshot().owner ^ (1 << 40)),
                    self.word(1, 2, format=RAW_B),
                    self.word(1, 2, data=b'\x00' * 4)):
            c = CanonicalCollector(self.snapshot(), enabled=True)
            c.accept(self.word(0, 1))
            with self.assertRaises(HostFault):
                c.accept(bad)
            self.assertTrue(c.failed)
            with self.assertRaises(HostFault):
                c.accept(self.word(1, 2))

    def test_only_exact_special_image_and_no_post_publication_accept(self):
        for digits in ([-1, 1] + [0] * 30, [0, -1] + [0] * 30):
            with self.assertRaisesRegex(HostFault, 'SPECIAL'):
                self.image(digits)
        c = CanonicalCollector(self.snapshot(), enabled=True)
        for i in range(32):
            c.accept(self.word(i, 0))
        c.finish()
        with self.assertRaisesRegex(HostFault, 'NOT_WRITABLE'):
            c.accept(self.word(32, 0))


if __name__ == '__main__':
    unittest.main()
