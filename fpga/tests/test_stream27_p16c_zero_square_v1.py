import json
from pathlib import Path
import tempfile
import unittest
from fpga.reference import stream27_p16c_zero_square_v1 as m


class ZeroSquare(unittest.TestCase):
    def test_exact_one_expression(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'negative'
            receipt=m.prepare(target)
            self.assertEqual(receipt['changed_sources'],[m.SOURCE])
            self.assertEqual(receipt['preserved_sources'],16)
            manifest=json.loads((target/'manifest.json').read_text())
            self.assertEqual(manifest['steps'][0]['expected_stderr'],m.FAILURE)
            self.assertEqual(manifest['steps'][0]['expected_returncode'],1)

    def test_first_direct_schoolbook_mismatch(self):
        prime=104857601
        expected=[0]*64
        expected[(63+63)%64]=prime-1
        mismatches=[]
        for row in range(4):
            for lane in range(16):
                index=int(f'{lane:04b}'[::-1],2)*4+row
                if expected[index]!=0:mismatches.append((85+row,lane))
        self.assertEqual(mismatches,[(87,15)])


if __name__=='__main__':unittest.main()
