import unittest
from fpga.reference import stream27_host_image_model_v1 as m


class HostImageModel(unittest.TestCase):
    def test_signed_storage_and_same_edge_scalar_rows(self):
        for aw in (5, 8):
            for p in (8, 16):
                image = m.Image(aw, p); g = image.g
                for i in range(g['n']):
                    image.edge(load=True, address=i, word=(i*2654435761)&0xffffffff)
                for i in range(g['n']):
                    response = image.edge(read=True, address=i)
                    self.assertTrue(response['read_valid'])
                    self.assertEqual(response['read_data'], m.signed96((i*2654435761)&0xffffffff))
                for row in range(g['t']):
                    response = image.edge(row=True, row_address=row)
                    self.assertTrue(response['row_read_valid'])
                    self.assertEqual(response['row_read_data'], tuple(((b*g['t']+row)*2654435761)&0xffffffff for b in range(p)))

    def test_exact_priority_no_idle_range_validation(self):
        image = m.Image(5, 16)
        for raw in (0, -1, -2, -(1 << 31), (1 << 31)-1, 0xffffffff):
            self.assertFalse(image.edge(load=True, read=True, address=3, word=raw)['read_valid'])
            self.assertEqual(image.edge(read=True, address=3)['read_data'], m.signed96(raw))
        image.edge(load=True, address=3, word=7, access=False)
        self.assertEqual(image.edge(read=True, address=3)['read_data'], -1)
        image.edge(row=True, row_address=1, load=True, address=3, word=7)
        self.assertEqual(image.edge(read=True, address=3)['read_data'], -1)
        image.edge(commit=True, commit_address=3, commit_word=-2,
                   row=True, row_address=1, load=True, read=True, address=4, word=99)
        self.assertEqual(image.edge(read=True, address=3)['read_data'], -2)
        self.assertIsNone(image.words[4])

    def test_reset_flushes_only_eligibility_not_image(self):
        image = m.Image(5, 8)
        image.edge(load=True, address=31, word=-2)
        image.edge(read=True, address=31)
        response = image.edge(rst=False, load=True, read=True, row=True, commit=True,
                              address=31, word=4, commit_address=31, commit_word=5)
        self.assertFalse(response['read_valid']); self.assertFalse(response['row_read_valid'])
        for _ in range(4):
            self.assertFalse(image.edge()['read_valid'])
        self.assertEqual(image.edge(read=True, address=31)['read_data'], -2)

    def test_symbolic_fullN_storage_only(self):
        for p in (8, 16):
            g = m.geometry(16, p)
            self.assertEqual((g['shadow_bits'], g['scalar_copy_edges'], g['m20k_packing_proxy']),
                             (2097152, 65536, 128))
        with self.assertRaisesRegex(ValueError, 'NO_FULLN'):
            m.Image(16, 16)
        for aw, p in ((4, 8), (17, 16), (5, 4), (5, True)):
            with self.assertRaises(ValueError):
                m.geometry(aw, p)

    def test_native_footers_derived_from_event_schedule(self):
        self.assertEqual(list(m.native_counts(5,16).values()),
                         [506,257,30,480,112,48,84,16,3,1012,1024,32])
        self.assertEqual(list(m.native_counts(8,16).values()),
                         [2886,1601,128,2048,784,272,322,16,3,5772,8192,256])
        self.assertEqual(m.native_counts(5,8)['edges'], 448)
        self.assertEqual(m.native_counts(8,8)['edges'], 2926)
        with self.assertRaises(ValueError):
            m.native_counts(16, 16)


if __name__ == '__main__':
    unittest.main()
