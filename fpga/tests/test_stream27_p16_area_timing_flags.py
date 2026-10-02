import hashlib
import json
from pathlib import Path
import re
import unittest

from fpga.reference import stream27_p16_area_timing_flags as area
from fpga.reference import stream27_p16_timing_flags as donor
from fpga.reference import stream27_comm_packed_bind as packed
from fpga.reference import stream27_root_outputreg_bind as rootreg
from fpga.reference import stream27_term_lookahead_p16_bind as lookahead


class AreaTimingTests(unittest.TestCase):
    @staticmethod
    def field(f):
        return donor.prepare_field(256,16,f,mode='warm',boundary_inputreg=1,
            quarantine_replicas=1,final_gs_inputreg=1,term_select_token=1)

    @staticmethod
    def whole(paired=False):
        name='whole-paired-aw16.json' if paired else 'whole-standalone-aw16.json'
        return json.loads((area.ROOT/'results/throughput-20260929/trackS-p16-timing-v1/bundles-v1'/name).read_text())

    def test_default_deep_copy_exact(self):
        for parent in (self.field(0),self.whole()):
            bound = area.bind(parent) if 'diet_binding' in parent else area.bind_field(parent)
            self.assertEqual(bound,parent)
            bound['files'].clear()
            self.assertTrue(parent['files'])

    def test_field_sources_commute_and_schedule_is_identical(self):
        for f in range(3):
            parent=self.field(f)
            first=area.bind_field(parent,comm_delay_packed=1,root_weight_outputreg=1,term_lookahead=1)
            second=lookahead.bind(rootreg.bind(packed.bind(parent)))
            third=rootreg.bind(packed.bind(lookahead.bind(parent)))
            self.assertEqual(first['files'],second['files'])
            self.assertEqual(first['files'],third['files'])
            self.assertEqual(first['geometry'],parent['geometry'])
            self.assertEqual(first['parameters'],parent['parameters'])

    def test_private_whole_closure_nonfield_preservation(self):
        for paired in (False,True):
            parent=self.whole(paired)
            bound=area.bind(parent,comm_delay_packed=1,root_weight_outputreg=1,term_lookahead=1)
            self.assertEqual(bound['geometry'],parent['geometry'])
            self.assertEqual(bound['parameters'],parent['parameters'])
            self.assertEqual(bound['top'],parent['top'])
            for name in donor.donor.fitted.PRESERVED:
                self.assertEqual(bound['files'][name],parent['files'][name])
            self.assertEqual(len(bound['root_weight_outputreg_contracts']),3)
            self.assertEqual(len(bound['term_lookahead_contracts']),3)
            self.assertEqual(sum(c['lazy_butterfly_instances'] for c in bound['root_weight_outputreg_contracts']),744)
            definitions=[]
            for text in bound['files'].values():
                definitions+=re.findall(r'\bmodule\s+(\w+)\s*(?:#|\()',text)
            self.assertEqual(len(definitions),len(set(definitions)))
            for name,text in bound['files'].items():
                self.assertEqual(bound['generated_sha256'][name],hashlib.sha256(text.encode()).hexdigest())
            self.assertFalse(bound['area_timing_roster']['whole_resource_GO'])
            self.assertFalse(bound['area_timing_roster']['root_M20K_output_FF_absorption_claim'])

    def test_standalone_is_exact_subset_of_paired(self):
        flags=dict(comm_delay_packed=1,root_weight_outputreg=1,term_lookahead=1)
        plain=area.bind(self.whole(),**flags)
        pair=area.bind(self.whole(True),**flags)
        self.assertTrue(all(pair['files'].get(n)==t for n,t in plain['files'].items()))


if __name__=='__main__':
    unittest.main()
