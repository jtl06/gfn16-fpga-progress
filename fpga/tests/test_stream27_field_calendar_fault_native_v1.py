import json
from pathlib import Path
import tempfile
import unittest
from fpga.reference import stream27_field_calendar_fault_native_v1 as native
from fpga.reference import stream27_shared_field_v4 as shared


class MissingFirstCalendar(unittest.TestCase):
    def test_only_explicit_diagnostic_forward_injection_changes(self):
        for p in (8,16):
            with tempfile.TemporaryDirectory(prefix='s4-calendar-source-') as directory:
                packet=Path(directory)/'packet';r=native.prepare(packet,p=p);b=shared.prepare(32,p,0,mode='warm_signed')
                source=packet/'inputs/fpga/rtl';text=(source/(r['top']+'.sv')).read_text()
                text=text.replace(r['top'],b['top']).replace('context_enabled,debug_drop_forward,','context_enabled,')
                text=text.replace('digit_slot && !debug_drop_forward','digit_slot')
                self.assertEqual(text,b['files'][b['top']+'.sv'])
                for name,value in b['files'].items():
                    if name!=b['top']+'.sv':self.assertEqual((source/name).read_text(),value)

    def test_declared_fault_edge_and_typed_negative_are_calendar_bound(self):
        for p,first in ((8,39),(16,41)):
            with tempfile.TemporaryDirectory(prefix='s4-calendar-source-') as directory:
                packet=Path(directory)/'packet';r=native.prepare(packet,p=p);m=json.loads((packet/'manifest.json').read_text())
                self.assertEqual(r['geometry']['pointwise_accept'],first)
                self.assertIn('missing_first_tick='+str(first),m['steps'][0]['expected_stdout'])
                self.assertEqual(m['steps'][1]['expected_stderr'],f'S4_CALENDAR_TYPED expected={first+1} actual={first}\n')
                self.assertEqual(m['steps'][1]['expected_returncode'],1)
                bench=(packet/'inputs/fpga/rtl/tb/stream27_field_calendar_fault_v1.cpp').read_text()
                self.assertIn('S4_CALENDAR_NO_EARLY_CT_FAULT',bench)
                self.assertIn('d.fault_pending&&!d.out_error&&d.owner_count==1',bench)
                self.assertIn('S4_CALENDAR_RAW_EXTERNAL_START_FAULT',bench)


if __name__=='__main__':unittest.main()
