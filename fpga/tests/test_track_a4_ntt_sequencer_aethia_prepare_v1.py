import json
from pathlib import Path
import tempfile
import unittest
from fpga.reference import track_a4_ntt_sequencer_aethia_prepare_v1 as a


class AethiaPreparationTests(unittest.TestCase):
    def test_only_host_and_placement_changes(self):
        pins,_=a.source_pins();parent=a.parent_module().manifest(pins);new=a.manifest(pins)
        self.assertEqual(new['host'],'aethia')
        self.assertEqual(new['source_root'],a.SOURCE)
        self.assertEqual(new['output_parent'],a.BASE)
        for key in ('schema','status','sources','build','probe','steps'):
            self.assertEqual(new[key],parent[key])
        self.assertEqual(a.sha(a.ROOT/a.GCP),a.GCP_SHA)

    def test_fresh_package_exact_closure(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'stage';result=a.prepare(out)
            source=out/'source/fpga'
            actual={str(p.relative_to(source)):a.sha(p) for p in source.rglob('*') if p.is_file()}
            self.assertEqual(actual,result['sources'])
            self.assertEqual(json.loads((out/'aw5-manifest.json').read_text()),a.manifest(actual))
            self.assertFalse(result['native_execution'])
            with self.assertRaisesRegex(ValueError,'fresh'):
                a.prepare(out)


if __name__=='__main__':unittest.main()
