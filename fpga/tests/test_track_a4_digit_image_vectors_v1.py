"""Independent directed digit-image contract checks; no HDL tools."""
import hashlib
import unittest
from fpga.reference.track_a4_digit_image_vectors_v1 import Image, corpus


def event(image, **changes):
    row = dict(rst=1, configure=0, clear_image=0, base=image.base or image.minimum,
               generation=image.generation, read_en=0, read_offset=0, read_mask=65535,
               read_apply_corrections=1, read_tag=0, write_en=0, write_offset=0,
               write_mask=65535, write_kind=0, clear_corrections=0, set_minus_one=0,
               boundary_commit=0, write_words=[0]*16, low=[0]*16, high=[0]*16)
    row.update(changes)
    for key in ('write_words', 'low', 'high'):
        row[key] = [v & 0xffffffff for v in row[key]]
    return image.edge(row)


class DigitImageContractTests(unittest.TestCase):
    def configured(self, aw=5):
        image = Image(aw)
        event(image, configure=1, clear_image=1, base=10**9, generation=23)
        for row in range(image.t):
            event(image, write_en=1, write_offset=row, write_words=[j*100+row for j in range(16)])
        return image

    def test_signed_rotated_boundary_and_effective_read_capture(self):
        image = self.configured()
        lows = [100+j for j in range(16)]; highs = [j-8 for j in range(16)]
        event(image, boundary_commit=1, low=lows, high=highs)
        self.assertEqual(image.c0, [-115]+lows[:-1])
        self.assertEqual(image.c1, [-7]+highs[:-1])
        event(image, read_en=1, read_offset=0, read_tag=13)
        expected = [j*100+([-115]+lows[:-1])[j] for j in range(16)]
        self.assertEqual(image.words, expected)
        self.assertEqual((image.read_tag,image.read_generation), (13,23))
        event(image, boundary_commit=1, low=[0]*16, high=[0]*16)
        self.assertEqual(image.words, expected)  # Captured data cannot follow live metadata.
        event(image, read_en=1, read_apply_corrections=0)
        self.assertEqual(image.words, [j*100 for j in range(16)])

    def test_shadow_capture_canonical_invalidation_and_host_replace(self):
        image = self.configured()
        self.assertEqual((image.sv0,image.sv1), (65535,65535))
        event(image, boundary_commit=1, low=[15]*16, high=[2]*16)
        event(image, write_en=1, write_kind=1, write_offset=1, write_mask=4)
        self.assertEqual(image.c1[2], 2)
        self.assertFalse(image.sv1 & 4)
        event(image, write_en=1, write_kind=2, write_mask=1, write_words=[-1]+[0]*15)
        self.assertEqual(image.c0[0], 0)
        self.assertFalse(image.sv0 & 1)
        event(image, read_en=1, read_mask=1)
        self.assertEqual(image.words[0], -1)
        event(image, write_en=1, write_mask=1, write_words=[77]+[0]*15)
        self.assertTrue(image.sv0 & 1)
        self.assertEqual(image.shadow0[0], 77)

    def test_atomic_rejection_and_fault_priority(self):
        image = self.configured()
        memory = dict(image.memory); c0 = list(image.c0); shadows = list(image.shadow0)
        out = event(image, read_en=1, write_en=1, read_mask=1, write_mask=1, write_words=[99]*16)
        self.assertEqual(out[8], 5)
        self.assertEqual((image.memory,image.c0,image.shadow0), (memory,c0,shadows))
        event(image, read_en=1, write_en=1, read_mask=1, write_mask=2, write_words=[99]*16)
        self.assertEqual(image.memory[image.t], 99)
        self.assertEqual(image.words[0], 0)
        for changes, code in ((dict(configure=1,read_en=1,base=0),1),
                              (dict(configure=1,base=0),2),
                              (dict(write_en=1,generation=24,write_kind=3),3),
                              (dict(write_en=1,write_kind=3,write_words=[-2]*16),4),
                              (dict(write_en=1,write_kind=2,write_words=[-2]*16),6),
                              (dict(boundary_commit=1,high=[-(1<<31)]*16),7)):
            before = dict(image.memory)
            self.assertEqual(event(image,**changes)[8], code)
            self.assertEqual(image.memory,before)

    def test_reset_preserves_ram_and_first_config_must_clear(self):
        image = self.configured()
        event(image,boundary_commit=1,low=[3]*16,high=[-2]*16)
        memory = dict(image.memory)
        event(image,rst=0)
        self.assertEqual(image.memory,memory)
        self.assertEqual(image.c0+image.c1,[0]*32)
        self.assertEqual((image.sv0,image.sv1,image.configured), (0,0,0))
        self.assertEqual(event(image,configure=1,base=10**9)[8],2)
        event(image,configure=1,clear_image=1,base=10**9,generation=91)
        event(image,read_en=1,read_offset=1)
        self.assertEqual(image.words,[100*j+1 for j in range(16)])

    def test_minus_one_marker_and_overwrite_zero(self):
        image = self.configured()
        for offset in range(image.t):
            event(image,write_en=1,write_kind=1,write_offset=offset)
        event(image,set_minus_one=1)
        event(image,read_en=1,read_mask=1)
        self.assertEqual(image.words[0],-1)
        event(image,write_en=1,write_kind=2,write_mask=1,write_words=[123]+[0]*15)
        event(image,read_en=1,read_mask=1)
        self.assertEqual(image.words[0],123)
        self.assertEqual(image.c0+image.c1,[0]*32)

    def test_corpus_extent_all_faults_and_numeric_bounds(self):
        for aw in (5,8):
            text,meta=corpus(aw)
            rows=[list(map(int,line.split())) for line in text.splitlines()[1:]]
            self.assertEqual(len(rows),meta['events'])
            self.assertTrue(all(len(row)==157 for row in rows))
            self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),meta['sha256'])
            self.assertTrue(all(n>0 for n in meta['error_codes'].values()))
            self.assertEqual(sum(row[72] for row in rows),meta['errors'])
            self.assertTrue(all(-(1<<32)<=v<(1<<32) for row in rows for v in row[77:93]))
        for aw in (4,16,True):
            with self.assertRaises(ValueError):
                corpus(aw)


if __name__=='__main__':
    unittest.main()
