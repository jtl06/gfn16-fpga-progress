import json
import unittest
from fpga.reference import stream27_host_chain_physical_f164_v1 as candidate
from fpga.tools import plain_fit_queue_v3 as queue


class ControlsOnlyF164(unittest.TestCase):
    ROOT = candidate.ROOT / 'artifacts/s4-p8-whole-host-aw16-f164-source-v1'
    AWS = candidate.ROOT / candidate.native.structural.parent.PROJECT

    def test_RTL_and_nonworker_controls_unchanged(self):
        old = json.loads((self.AWS / 'manifest.json').read_text())
        new = json.loads((self.ROOT / 'project/manifest.json').read_text())
        self.assertEqual(old['source_sha256'], new['source_sha256'])
        self.assertEqual(len(new['source_sha256']), 49)
        self.assertEqual(new['compile_processors'], 4)
        self.assertEqual(old['core_parameters'], new['core_parameters'])
        for filename in ('probe.qpf', 'probe.sdc', 'run.tcl'):
            self.assertEqual((self.AWS / filename).read_bytes(), (self.ROOT / 'project' / filename).read_bytes())
        self.assertEqual((self.ROOT / 'project/probe.qsf').read_text(),
            (self.AWS / 'probe.qsf').read_text().replace('NUM_PARALLEL_PROCESSORS 6\n', 'NUM_PARALLEL_PROCESSORS 4\n'))

    def test_existing_F16_queue_source_verifier(self):
        descriptor = json.loads((self.ROOT / 'variant-f164.json').read_text())
        receipt = json.loads((self.ROOT / 'source-handoff.json').read_text())
        self.assertEqual(queue.source_variant('gfn16-azure-f16', descriptor), receipt['project_context'])
        self.assertEqual(receipt['structural_guard_findings'], [])
        self.assertEqual(receipt['transfer_count'], 26)
        self.assertFalse(receipt['fit_allowed'])
        self.assertFalse(receipt['field_sizing_exemption'])
        self.assertFalse(receipt['false_paths_added'])

    def test_same_actual_native_and_independent_binding(self):
        owner = json.loads(candidate.native.OWNER.read_text())
        receipt = json.loads((self.ROOT / 'source-handoff.json').read_text())
        self.assertEqual(receipt['project_context']['source_sha256'], owner['standalone_generated_sha256'])
        self.assertEqual(receipt['actual_native_gate_sha256'], owner['gate_sha256'])
        self.assertEqual(receipt['actual_native_report_sha256'], owner['report_sha256'])
        self.assertEqual(receipt['parameters'], dict(AW=16, P=8, CONTEXTS=1, EPOCH_SEED=65534))


if __name__ == '__main__':
    unittest.main()
