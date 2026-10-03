import json
import unittest
from fpga.reference import stream27_r15_real_shell_clock_global_v1 as repair
from fpga.tools import fit_dispatch as fit


class GlobalReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent=repair.PARENT
        cls.project=repair.BASE/'physical-global-refclk-v1/project'
        cls.old=json.loads((cls.parent/'manifest.json').read_bytes())
        cls.new=json.loads((cls.project/'manifest.json').read_bytes())

    def test_only_supported_qsf_routing_delta(self):
        self.assertEqual((self.project/'probe.qsf').read_text(),
          (self.parent/'probe.qsf').read_text()+repair.ASSIGNMENT)
        self.assertEqual(self.new['device'],self.old['device'])
        self.assertEqual(self.new['clock_period_ns'],12)
        self.assertEqual(self.new['compile_processors'],8)
        self.assertEqual(self.new['seed'],1)
        self.assertNotIn('AUTO_RESERVE_CLKUSR_FOR_CALIBRATION OFF',(self.project/'probe.qsf').read_text())

    def test_all_rtl_ip_and_timing_constraints_identical(self):
        self.assertEqual(self.new['source_sha256'],self.old['source_sha256'])
        a=self.old['r15_real_shell'];b=self.new['r15_real_shell']
        for key in ('vendor_sources','qip_roots','effective_parameters','board_sources','clock_proof','base_sdc','cdc_sdc','cdc_qsf'):
            self.assertEqual(a[key],b[key])
        for p in self.parent.rglob('*'):
            if p.is_file() and (p.suffix in ('.sv','.v','.vhd','.sdc','.qip','.ip','.qsys') or 'vendor' in p.parts):
                self.assertEqual(p.read_bytes(),(self.project/p.relative_to(self.parent)).read_bytes())

    def test_exact_projection_and_structural_guard(self):
        fit.real_shell_verify_project(self.project,8)
        module=fit.real_shell_structure(fit.load(repair.ROOT/'tools/prefit_structural_guard_v1.py'))
        spec=json.loads((self.project.parent/'structural-inventory.json').read_bytes())
        self.assertEqual(module.source_inventory(self.project,spec)['findings'],[])
        self.assertEqual(len(spec['transfers']),38)

    def test_parent_and_fresh_output_refusal(self):
        self.assertEqual(repair.sha((self.parent/'manifest.json').read_bytes()),repair.PARENT_SHA)
        with self.assertRaisesRegex(ValueError,'FRESH_OUTPUT'):repair.prepare(self.project)

if __name__=='__main__':unittest.main()
