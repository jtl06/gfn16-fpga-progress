import importlib.util
import unittest
from fpga.reference import stream27_r15_compute_pilot_native as own


class R15ComputePilotTests(unittest.TestCase):
    def test_source_header_only_count_delta_and_own_allocation(self):
        a,af,ab=own.role(100);b,bf,bb=own.role(1000)
        self.assertEqual(ab,bb)
        self.assertEqual(a['build'],b['build'])
        self.assertEqual(set(af),set(bf))
        self.assertEqual({n for n in af if af[n]!=bf[n]},{own.HEADER})
        self.assertIn('COUNT=100,INTERVAL=8461,FIRST_DIGIT=8459,CARRY_DONE=12558',af[own.HEADER].decode())
        self.assertIn('COUNT=1000,INTERVAL=8461,FIRST_DIGIT=8459,CARRY_DONE=12558',bf[own.HEADER].decode())
        self.assertEqual(len(a['build']['sv_sources']),61)
        self.assertEqual(a['steps'][0]['validator']['config']['allocation_family'],'AzureFIT-serial1-2physical-8GiB-j2')
        self.assertFalse(a['r15_compute']['own_long']['forecast_inherited'])
        self.assertTrue(a['r15_compute']['own_long']['actual_Azure_pilot_measurement_pending'])
        spec=importlib.util.spec_from_file_location('_native_result_validator',own.ROOT/own.SELF)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertTrue(callable(module.validate))
        with self.assertRaises(ValueError):module.validate('','',0,{}, {})


if __name__=='__main__':unittest.main()
