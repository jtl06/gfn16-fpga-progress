import unittest
from fpga.reference.stream27_r15_async_fifo_native import role,RTL,CPP


class CdcSourceTests(unittest.TestCase):
    def test_gray_full_relation_and_single_bit_transitions(self):
        for aw in range(2,6):
            depth=1<<aw;mask=2*depth-1;flip=3<<(aw-1)
            gray=lambda x:(x>>1)^x
            for r in range(2*depth):
                self.assertEqual(gray((r+depth)&mask),gray(r)^flip)
                delta=gray(r)^gray((r+1)&mask)
                self.assertEqual(delta.bit_count(),1)

    def test_native_contract_and_no_unbounded_storage(self):
        m,files=role()
        self.assertEqual(m['build']['parameters'],dict(WIDTH=256,ADDR_W=3))
        self.assertEqual(set(files),set(m['sources']))
        self.assertIn(b'data[0:DEPTH-1]',files[RTL])
        self.assertIn(b'ADDR_W>5',files[RTL])
        cpp=files[CPP].decode()
        self.assertLess(cpp.index('gfn16_runtime::configure'),cpp.index('dut(&context)'))
        for token in ('R15_CDC_ORDER_OR_DATA','R15_CDC_STALLED_PAYLOAD','R15_CDC_RESET_AUTHORITY','R15_CDC_FINAL_DRAIN','pushes==pops+discarded'):
            self.assertIn(token,cpp)
        self.assertFalse(m['scope']['metastability_or_physical_constraints_qualified'])


if __name__=='__main__':unittest.main()
