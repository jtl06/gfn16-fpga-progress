import json
from pathlib import Path
import tempfile
import unittest

from fpga.reference import a10_field_physical_probe_v1 as probe


class A10PhysicalProbeTests(unittest.TestCase):
    def test_common_recipe_and_exact_native_child(self):
        files, receipt=probe.source_inputs()
        self.assertEqual(receipt['child_sha256'],probe.CHILD_SHA)
        self.assertEqual((receipt['request_added_edges'],receipt['response_added_edges']),(1,1))
        self.assertEqual(len(receipt['source_register_anchors']),25)
        self.assertEqual(len(receipt['destination_register_anchors']),24)
        wrapper=files[probe.TOP+'.sv'].decode()
        self.assertIn('profile_abort',wrapper)
        self.assertIn('root_rom_reads <= child_root_rom_reads_d;',wrapper)
        self.assertIn('normalization_products <= child_normalization_products_d;',wrapper)
        for port in receipt['ports']:
            if port['name'] in ('clk','rst_n'):continue
            if port['direction']=='input':
                self.assertIn('launch_'+port['name']+'_q <= '+port['name']+';',wrapper)
            else:
                self.assertIn(port['name']+' <= child_'+port['name']+'_d;',wrapper)
        self.assertEqual(len(files),9)

    def test_source_closed_qsf_guard_four_and_six_workers(self):
        plain=probe.load_exact(probe.PLAIN,probe.PLAIN_SHA,'_plain_a10_test')
        for workers in (4,6):
            with tempfile.TemporaryDirectory(prefix='a10-field-fit-') as directory:
                root=Path(directory).resolve();project=root/'project'
                report=probe.prepare(project,workers)
                # Pure verify_project fixture only; never execute launcher.
                (root/'run-aws-fit-v6.sh').write_text('# source descriptor fixture\n')
                runner=plain.runner(dict(root=str(root),workers=workers,memory=20<<30,
                    slots={'a':list(range(workers))}), 'gfn16-aws-m8i',False)
                checked=runner.verify_project(project)
                self.assertEqual(checked['manifest_sha256'],report['manifest_sha256'])
                self.assertEqual(checked['qsf_parameters'],probe.PARAMETERS)
                self.assertEqual(set(checked['source_sha256']),set(report['source_sha256']))
                qsf=(project/'probe.qsf').read_text()
                self.assertIn('ENABLE_INTERMEDIATE_SNAPSHOTS ON',qsf)
                self.assertEqual((project/'run.tcl').read_text(),plain.FULL_TCL)
                self.assertNotIn('execute_module -tool asm',(project/'run.tcl').read_text())
                m=json.loads((project/'manifest.json').read_text())
                self.assertEqual(m['root_profile_format'],3)
                self.assertTrue(m['wrapper_native_gate_pending'])
                self.assertFalse(m['physical_timing_proven'])
                self.assertEqual(m['exemption'],'component_sizing_probe')
                (project/'probe.qsf').write_text(qsf.replace('set_parameter -name AW 16','set_parameter -name AW 8'))
                with self.assertRaisesRegex(Exception,'parameter mismatch'):runner.verify_project(project)

    def test_fresh_output_and_worker_bounds(self):
        for workers in (1,8,True):
            with self.assertRaises(ValueError):probe.prepare(Path('unused-output'),workers)
        with tempfile.TemporaryDirectory(prefix='a10-fit-existing-') as directory:
            with self.assertRaisesRegex(ValueError,'FRESH_PROJECT'):probe.prepare(Path(directory),6)


if __name__=='__main__':unittest.main()
