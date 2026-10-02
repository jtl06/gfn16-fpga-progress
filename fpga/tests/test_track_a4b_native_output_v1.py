import unittest
from fpga.reference.track_a4b_native_output_v1 import validate

class A4bOutputAdapterTests(unittest.TestCase):
    def test_boundary_control_and_mutant(self):
        text='A4_ADMISSION_PASS case=raw commands=36 no_ram_edges=12 ticks=5000\n'
        self.assertEqual(validate(text,'',0,dict(mode='boundary',case='raw'),{})['case'],'raw')
        result=validate('','A4_ADMISSION_RAW_REJECTION\n',1,
            dict(mode='boundary',case='raw',mutant='admit_unowned_write'),{})
        self.assertEqual(result['typed_failure'],'A4_ADMISSION_RAW_REJECTION')

    def test_no_exit_only_or_extra_configuration_acceptance(self):
        cases=[('', '', 0,dict(mode='boundary',case='raw'),{}),
            ('', '', 0,dict(mode='normal',aw=5),{}),
            ('', '', 0,dict(mode='representative',aw=16),{'unbound':'value'}),
            ('', '', 0,dict(mode='boundary',case='raw',skip=True),{}),
            ('', '', True,dict(mode='boundary',case='raw'),{})]
        for args in cases:
            with self.assertRaises(ValueError):validate(*args)

if __name__=='__main__':unittest.main()
