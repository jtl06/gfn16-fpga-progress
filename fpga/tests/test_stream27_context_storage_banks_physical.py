import copy
import re
import unittest
from unittest.mock import patch
from fpga.reference import stream27_context_storage_banks_physical as physical


class StoragePhysicalTests(unittest.TestCase):
    def test_syn_exact_private_normal_and_no_route(self):
        manifest, files=physical.build()
        self.assertEqual(len(manifest['source_sha256']),53)
        self.assertEqual(manifest['allowed_stages'],['syn'])
        self.assertEqual(files['run.tcl'],(physical.PARENT/'run.tcl').read_bytes())
        self.assertEqual(manifest['native_normal_id'],'s4-p16-c2-storage2-full-normal-q1-v1')
        self.assertFalse(manifest['storage2']['wholefit_released'])

    def test_field_matched_controls_except_top_and_source_lines(self):
        manifest, files=physical.build_field()
        for name in ('probe.qpf','probe.sdc','run.tcl'):
            self.assertEqual(files[name],(physical.FIELD_PARENT/name).read_bytes())
        original=(physical.FIELD_PARENT/'probe.qsf').read_text()
        candidate=files['probe.qsf'].decode()
        strip=lambda text:re.sub(r'^set_global_assignment -name (SYSTEMVERILOG_FILE|TOP_LEVEL_ENTITY) .*\n','',text,flags=re.M)
        self.assertEqual(strip(original),strip(candidate))
        self.assertEqual(manifest['scope'],'component_probe')
        self.assertFalse(manifest['storage2']['compact_tags'])

    def test_field_default_parameters_and_exact_source53(self):
        manifest, files=physical.build_field()
        self.assertEqual(manifest['compile_processors'],4)
        self.assertEqual(manifest['seed'],1)
        self.assertEqual(manifest['clock_period_ns'],10)
        self.assertEqual(manifest['field_parameters']['CONTEXTS'],2)
        self.assertEqual(len([name for name in files if name.endswith('.sv')]),53)
        self.assertTrue(manifest['top'].endswith('_storage2_v1'))

    def test_parent_source_map_drift_rejected(self):
        original=physical.native.capture('full')
        bad=copy.deepcopy(original)
        bad[2]['generated_sha256'][next(iter(bad[2]['generated_sha256']))]='0'*64
        with patch.object(physical.native,'capture',return_value=bad):
            with self.assertRaises(ValueError):physical.build_field()


if __name__=='__main__':unittest.main()
