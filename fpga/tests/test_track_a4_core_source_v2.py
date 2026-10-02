import unittest
from fpga.reference.track_a4_core_source_v2 import verify, successor


class CoreDeltaTests(unittest.TestCase):
    def test_exact_successors(self):
        self.assertEqual(verify()["exact_successors"],4)

    def test_fault_not_suppressed(self):
        p="rtl/kernel/genefer_track_a4_field_transfer_v1.sv"
        text="genefer_track_a4_field_transfer_v1 !cancel && !error && !field_error && !protocol_fault else if(field_error || protocol_fault || error)"
        actual=successor(p,text)
        self.assertNotIn("!field_error",actual)
        self.assertIn("else if(field_error || protocol_fault || error)",actual)


if __name__ == "__main__":
    unittest.main()
