import unittest
from unittest.mock import patch
from fpga.reference import a10_conversion_ledger_v1 as ledger


class ConversionLedgerTests(unittest.TestCase):
    def test_exact_parent_conversion_not_a_new_Montgomery_removal(self):
        self.assertEqual(ledger.source_guard(),ledger.PINS)
        for n in (32,256,65536):
            value=ledger.edge_ledger(n)
            self.assertEqual(value['conversion_cycles'],n//16+6)
            self.assertEqual(value['removed_additional_conversion_cycles'],0)
            self.assertFalse(value['numeric_NTT_performed'])

    def test_counter_mutants_are_not_accepted(self):
        for n in (32,256,65536):
            expected=ledger.edge_ledger(n)['conversion_cycles']
            self.assertEqual(ledger.check_counter(expected,n),expected)
            for fault in (expected-3,expected-1,expected+1,2*expected,True):
                with self.assertRaisesRegex(ValueError,'COUNTER_MISMATCH'):
                    ledger.check_counter(fault,n)

    def test_geometry_and_source_drift(self):
        for n in (0,8,33,65537,True):
            with self.assertRaises(ValueError): ledger.edge_ledger(n)
        with patch.object(ledger,'PINS',{ledger.PARENT:'0'*64}):
            with self.assertRaisesRegex(ValueError,'SOURCE_DRIFT'): ledger.source_guard()


if __name__=='__main__':unittest.main()
