import unittest
from pathlib import Path
from fpga.reference.core27_prefill_structure import validate_files, remove_passive_extension, CARRY


class PrefillStructure(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def test_exact_source_closure(self):
        result = validate_files(self.root)
        self.assertEqual(len(result['compiled']), 17)
        self.assertEqual(result['status'], 'source_only_not_native_qualified')

    def test_passive_carry_reconstruction(self):
        s = (self.root/'rtl/kernel'/(CARRY+'.sv')).read_text()
        old = (self.root/'rtl/kernel/genefer_carry_prefix_stream_precision.sv').read_text()
        self.assertEqual(remove_passive_extension(s), old)

    def test_carry_logic_mutation_not_hidden(self):
        s = (self.root/'rtl/kernel'/(CARRY+'.sv')).read_text()
        old = (self.root/'rtl/kernel/genefer_carry_prefix_stream_precision.sv').read_text()
        self.assertNotEqual(remove_passive_extension(s.replace('busy<=0;done<=1;', 'busy<=1;done<=1;', 1)), old)

    def test_native_monitor_actual_ram_and_typed_failures(self):
        s = (self.root/'rtl/tb/core27_prefill_probe.sv').read_text()
        for name in ['child.data_we', 'child.data_wa', 'child.data_w', 'T5_MONITOR_WRITE_AGE',
                     'T5_MONITOR_WRITE_MASK', 'T5_MONITOR_WRITE_ADDRESS', 'T5_MONITOR_COMPLETE_COUNT',
                     'T5_MONITOR_FAST_ELIGIBILITY']:
            self.assertIn(name, s)
        self.assertNotIn('public_flat', s)

    def test_bench_holds_native_return_guard(self):
        s = (self.root/'rtl/tb/core27_prefill_normal.cpp').read_text()
        self.assertIn('d.final();return 0;', s)
        self.assertIn('fast_before?0:', s)
        self.assertIn('T5_NORMAL_COMPLETE_IMAGE', s)


if __name__ == '__main__': unittest.main()
