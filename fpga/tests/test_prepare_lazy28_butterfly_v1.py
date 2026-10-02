import json
from pathlib import Path
import tempfile
import unittest
from fpga.reference import prepare_lazy28_butterfly_v1 as p


class PrepareTests(unittest.TestCase):
    def test_pinned_prerequisites(self):
        pins=p.source_pins();model=p.load_model(pins)
        self.assertEqual(model.MULTIPLIER_SHA,pins[p.MULT])

    def test_typed_native_contracts_require_wall(self):
        pins=p.source_pins();model=p.load_model(pins)
        for field in p.FIELDS:
            for role in ['control']+list(p.ERRORS):
                sources=dict(pins)
                if role!='control':sources[f'mutants/{role}/genefer_ntt_lazy28_butterfly_v1.sv']='0'*64
                _,counts=model.corpus(field,role);m=p.manifest(field,role,sources,counts)
                self.assertIn('-Wall',m['admission']['required_external_lint'])
                self.assertFalse(m['admission']['launcher_enforces_lint'])
                self.assertEqual(m['build']['parameters']['P'],field)
                self.assertIn(f'-DTEST_P={field}',m['build']['cflags'])
                self.assertEqual(m['steps'][0]['expected_returncode'],0 if role=='control' else 1)

    def test_matched_resource_project_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);projects=p.physical(out)
            self.assertEqual(len(projects),6)
            for field in p.FIELDS:
                a=out/'physical'/f'p{field}-canonical-parent';b=out/'physical'/f'p{field}-lazy'
                for name in ('probe.sdc','probe.qpf','run.tcl'):self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())
                self.assertEqual((a/'probe.qsf').read_text().replace('USE_LAZY 0','USE_LAZY 1'),(b/'probe.qsf').read_text())
                self.assertEqual(json.loads((a/'manifest.json').read_text())['source_sha256'],json.loads((b/'manifest.json').read_text())['source_sha256'])
                self.assertNotIn('asm',(a/'run.tcl').read_text())


if __name__=='__main__':unittest.main()
