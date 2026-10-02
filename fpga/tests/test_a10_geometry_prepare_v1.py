import json
from pathlib import Path
import tempfile
import unittest
from fpga.reference import a10_geometry_prepare_v1 as p

class PrepareGeometryTests(unittest.TestCase):
    def test_aw8_closed_geometry_and_explicit_full_constants(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'aw8';r=p.prepare(out)
            self.assertEqual(r['aw'],8);self.assertEqual(len(r['manifests']),3)
            self.assertEqual(r['source_only_ledger']['ROM_reads_per_transform'],14)
            p.closed(out/'source/fpga',r['source_sha256'])
            for entry in r['manifests']:
                m=json.loads((out/entry['path']).read_text())
                self.assertEqual(p.sha(out/entry['path']),entry['sha256'])
                self.assertEqual(m['build']['parameters']['AW'],8)
                self.assertEqual(m['build']['cpp_source'],'rtl/tb/a10_banked_engine_geometry_v1.cpp')
                self.assertIn('a10_packed_lookup_aw8_geometry_bound_v1.sv',' '.join(m['build']['sv_sources']))
                self.assertNotIn('a10_packed_lookup_aw5_bound_v1.sv',' '.join(m['build']['sv_sources']))
                self.assertEqual(m['steps'][0]['validator']['config']['aw'],8)
                self.assertTrue(m['source_root'].startswith('/not-a-dispatch-path/'))
            for name,pin in r['unchanged_RTL_donor_pins'].items():self.assertEqual(r['source_sha256'][name],pin)
            with self.assertRaisesRegex(ValueError,'FRESH_OUTPUT'):p.prepare(out)
            with self.assertRaisesRegex(ValueError,'FULL_CONSTANTS_EXPLICIT_ONLY'):p.prepare(Path(d)/'aw16',16)
            self.assertFalse((Path(d)/'aw16').exists())

    def test_input_geometry_rejects_unadmitted_values(self):
        with tempfile.TemporaryDirectory() as d:
            for aw in (4,6,9,15,17,True):
                with self.assertRaisesRegex(ValueError,'NATIVE_GEOMETRY'):p.prepare(Path(d)/str(aw),aw)

if __name__=='__main__':unittest.main()
