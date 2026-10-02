"""Pure source/control checks; no HDL, native, vendor, or full-N arithmetic."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

from reference import stream27_context_storage2_route_v1 as r


class RouteSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.files = r.build()
        cls.spec = r.inventory(cls.manifest, cls.files)

    def test_exact_selected_rtl_and_only_full_flow_controls(self):
        parent = r.read(r.PARENT / 'manifest.json')
        self.assertEqual(self.manifest['source_sha256'], parent['source_sha256'])
        self.assertEqual(len(self.manifest['source_sha256']), 53)
        self.assertEqual(self.manifest['core_parameters'], parent['core_parameters'])
        self.assertEqual(self.manifest['allowed_stages'], ['syn', 'fit', 'sta'])
        self.assertEqual(self.manifest['clock_period_ns'], 14)
        self.assertEqual(self.files['probe.qsf'], (r.PARENT / 'probe.qsf').read_bytes())
        self.assertEqual(self.files['probe.qpf'], (r.PARENT / 'probe.qpf').read_bytes())
        self.assertEqual(self.files['run.tcl'], r.FLOW.read_bytes())
        self.assertFalse(self.manifest['promotion_allowed'])

    def test_actual_place_sources_match(self):
        place_project = r.PLACE.parent / 'evidence/project'
        captured = r.read(place_project / 'manifest.json')
        self.assertEqual(captured['source_sha256'], self.manifest['source_sha256'])
        self.assertEqual(captured['top'], self.manifest['top'])
        self.assertEqual(captured['core_parameters'], self.manifest['core_parameters'])

    def test_inventory_phases_do_not_invent_fault_source_ff(self):
        self.assertEqual(len(self.spec['transfers']), 20)
        fault = next(t for t in self.spec['transfers'] if t['id'] == 'prospective_fault_to_sticky_origin')
        self.assertEqual(fault['registered_stages'], [])
        self.assertIn('NO source FF', fault['exception']['reason'])
        self.assertEqual(self.spec['coverage_claim'], 'declared_source_inventory_not_netlist_completeness')
        self.assertEqual(self.spec['identity']['clock_period_ns'], 14)
        self.assertEqual(self.spec['identity']['parameters']['CONTEXTS'], 2)

    def test_anchor_drift_fails(self):
        files = dict(self.files)
        name = 'rtl/' + r.TOP + '.sv'
        files[name] = files[name].replace(b'capture_req_d<=capture_fire;', b'capture_req_d<=1;')
        with self.assertRaisesRegex(ValueError, 'structural anchor'):
            r.inventory(self.manifest, files)

    def test_frozen_prepared_inventory_current_checker(self):
        folder = r.ROOT / 'results/throughput-20260929/trackS-c2-storage2-route14-v1'
        module_spec = importlib.util.spec_from_file_location('route_source_test_checker', r.ROOT / 'tools/prefit_structural_guard_v1.py')
        checker = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(checker)
        frozen = json.loads((folder / 'structural-inventory.json').read_text())
        self.assertEqual(checker.source_inventory(folder / 'project', frozen)['findings'], [])
        tampered = copy.deepcopy(frozen)
        tampered['identity']['clock_period_ns'] = 10
        with self.assertRaises(ValueError):
            checker.source_inventory(folder / 'project', tampered)


if __name__ == '__main__':
    unittest.main()
