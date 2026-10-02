import json
from pathlib import Path
import tempfile
import unittest
from fpga.reference import stream27_field_calendar_fault_native_v1 as old
from fpga.reference import stream27_field_calendar_fault_native_v2 as new


class ExactPhaseDelta(unittest.TestCase):
    def test_dut_header_steps_and_missing_first_edge_unchanged(self):
        for p in (8,16):
            with tempfile.TemporaryDirectory(prefix='s4-calendar-phase-') as root:
                a=Path(root)/'old';b=Path(root)/'new';old.prepare(a,p=p);new.prepare(b,p=p)
                ma=json.loads((a/'manifest.json').read_text());mb=json.loads((b/'manifest.json').read_text())
                self.assertEqual(ma['build'],mb['build']);self.assertEqual(ma['steps'],mb['steps'])
                for name,pin in ma['sources'].items():
                    if name!=old.BENCH:self.assertEqual(pin,mb['sources'][name],name)
                cpp=(b/'inputs/fpga'/old.BENCH).read_text()
                self.assertIn('tick>=PHYSICAL+1 && tick<PHYSICAL+T+1',cpp)
                self.assertIn('tick>=SINK+1 && tick<SINK+T+1',cpp)
                self.assertIn('if(tick==POINTWISE)',cpp)
                self.assertIn('if(tick<POINTWISE)need(!d.fault_pending&&!d.out_error',cpp)
                self.assertIn('d.fault_pending&&!d.out_error&&d.owner_count==1',cpp)
                self.assertIn('edge(d);need(d.out_error,"S4_CALENDAR_REGISTERED_MISSING_FIRST")',cpp)


if __name__=='__main__':unittest.main()
