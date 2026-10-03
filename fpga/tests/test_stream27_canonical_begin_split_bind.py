import json
import unittest
from fpga.reference import stream27_canonical_begin_split_bind as b
from fpga.reference.stream27_canonical_begin_split_model import ROOT


class BeginSplitBind(unittest.TestCase):
    def test_exact_default_and_reverse(self):
        bundle=json.loads((ROOT/'results/throughput-20260929/trackS-c2-storage-combo-registerederror-native-v1/aw8-normal/production-bundle.json').read_text())
        text=bundle['files'][b.OLD+'.sv']
        self.assertEqual(b.bind_leaf(text,enabled=0),text)
        changed=b.bind_leaf(text,enabled=1)
        self.assertEqual(b.reverse_leaf(changed),text)
        self.assertEqual(changed.count('base_reg<=base;'),1)
        self.assertEqual(changed.count('base_reg<=2;'),1)
        self.assertEqual(changed.count('always_ff'),text.count('always_ff'))
        with self.assertRaises(ValueError):
            b.bind_leaf(text+'\n',enabled=1)


if __name__=='__main__':
    unittest.main()
