import json
from pathlib import Path
import tempfile
import unittest
from fpga.reference import stream27_p8b_probe_v1 as p
from fpga.reference import stream27_p8b_native_v1 as native


class P8B(unittest.TestCase):
    def test_source_width_and_canonical_boundary(self):
        for n in (32,64,256):
            b=p.compile_probe(n)
            self.assertEqual(b['geometry']['data_internal_bits'],27)
            self.assertEqual(b['geometry']['token_total_bits'],38)
            self.assertEqual(len(b['files']),12)
            text='\n'.join(b['files'].values())
            self.assertNotIn('genefer_ntt_lazy28_butterfly_v1',text)
            self.assertNotIn('genefer_montgomery_mul28x27_sparse_pipe_v2',text)
            for name,src in b['files'].items():
                if '_p8b_v1.sv' in name:self.assertNotIn('+:28]',src)
            self.assertIn('!stop && !range_bad',b['files'][b['top']+'.sv'])

    def test_canonical_small_square_independent_schoolbook(self):
        for n in (32,64,256):
            for field in range(3):
                mod=p.parent.FIELDS[field][0]
                values=[(i*i*37+19*i+997)%mod for i in range(n)]
                expected=[0]*n
                for i,a in enumerate(values):
                    for j,b in enumerate(values):expected[(i+j)%n]=(expected[(i+j)%n]+(1 if i+j<n else -1)*a*b)%mod
                self.assertEqual(p.parent.merged.square(values,8,field),expected)

    def test_calendar_and_footer(self):
        b=p.compile_probe()
        self.assertEqual(b['calendar']['first_physical_output'],73)
        self.assertEqual(b['calendar']['next_nonoverlap_start'],78)
        self.assertEqual(native.counts(),dict(events=20007,physical=670,eligible=66,resets=326,aborts=79))
        with tempfile.TemporaryDirectory() as tmp:
            receipt=native.prepare(Path(tmp)/'p')
            self.assertEqual(receipt['sources'],14)
            self.assertEqual(receipt['rtl_sources'],12)


if __name__=='__main__':unittest.main()
