"""Actual immutable C1 dossier controls; no native/remote command."""
import sys
from pathlib import Path
import unittest

FPGA = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(FPGA/'tools'))
import plain_fit_path_ledger_v2 as ledger


class ControllerLedgerTests(unittest.TestCase):
    def test_actual_c1_root_update_and_route_cell_statistics(self):
        dossier = FPGA/'queue/fit-r54-controller-v1/terminal/c1-current'
        result = ledger.collect(dossier,'da84f1ca2adb0c18d68528711863236356b7caed22bdf9e56a74828181b92b92')
        self.assertEqual(result['setup']['endpoint_family_counts'],{'NTT root recurrence/update -> NTT root recurrence/update':10})
        first = result['setup']['paths'][0]
        self.assertEqual(first['slack_ns'],-1.579)
        self.assertEqual(first['native_data_statistics']['IC']['total_delay_ns'],3.955)
        self.assertEqual(first['native_data_statistics']['Cell']['total_delay_ns'],5.646)
        self.assertEqual(result['native_high_fanout']['top20'][0]['logical_fanout'],5482)
        self.assertEqual(result['native_resources']['labs'],36233)
        self.assertFalse(result['audited_clock'])

    def test_wrong_terminal_pin_and_unknown_demand_refused(self):
        dossier = FPGA/'queue/fit-r54-controller-v1/terminal/c1-current'
        with self.assertRaises(ValueError): ledger.collect(dossier,'0'*64)
        with self.assertRaises(ValueError): ledger.tables.congestion('No raw native demand table')


if __name__ == '__main__': unittest.main()
