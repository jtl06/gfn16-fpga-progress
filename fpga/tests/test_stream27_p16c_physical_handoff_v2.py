from pathlib import Path
import json
import tempfile
import unittest
from fpga.reference import stream27_p16c_physical_handoff_v2 as m


class PhysicalHandoff(unittest.TestCase):
    def test_same_thirteen_rtl_explicit_metadata_snapshot_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'prepared'
            r=m.prepare(out)
            self.assertFalse(r['fit_allowed'])
            self.assertEqual(len(r['source_sha256']),13)
            p=out/'project'
            for name,pin in r['source_sha256'].items():self.assertEqual(m.sha(p/'rtl'/name),pin)
            self.assertEqual((p/'probe.qsf').read_text(),(m.PARENT/'probe.qsf').read_text()+m.SNAPSHOT)
            self.assertEqual((p/'run.tcl').read_bytes(),(m.PARENT/'run.tcl').read_bytes())
            self.assertEqual(json.loads((p/'manifest.json').read_text())['core_parameters'],{'AW':16,'CONTEXTS':1})
            with self.assertRaises(AssertionError):m.prepare(out)


if __name__=='__main__':unittest.main()
