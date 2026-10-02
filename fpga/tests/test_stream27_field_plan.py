"""Source/topology/root checks only; no HDL/native/physical evidence."""
import unittest

from fpga.reference.stream27_field_plan import (
    topology, root_exponent, root_word, resource_plan, field_contract,
    require_complete_field, verify_sources,
)
from fpga.reference.stream27_field_compile import compile_transform
from fpga.reference.stream_ntt_schedule import transform, index_of
from fpga.reference.stream_ntt_blockcarry_schedule import joined_events
from fpga.reference.stream_ntt_model import FIELDS, bit_reverse


class FieldPlanningTests(unittest.TestCase):
    def test_source_pins(self):
        self.assertEqual(len(verify_sources()), 6)

    def test_compiler_geometry_and_roots_against_literal_transform(self):
        for n in (8, 32, 64, 128, 256):
            for inverse in (False, True):
                plan = topology(n, inverse=inverse)
                expected = transform(n, 8, inverse=inverse)
                for spec, old in zip(plan['stages'], expected['stages']):
                    for key in ('lane_bits', 'time_bits', 'shuffle_depth_per_buffer',
                                'commutator_replaced_lane_bit', 'unique_root_streams'):
                        actual = spec[key]
                        if key == 'unique_root_streams':
                            actual = [{k: v for k, v in row.items() if k != 'fixed_index'} for row in actual]
                        self.assertEqual(actual, old[key], (n, inverse, spec['stage'], key))
                    bit = spec['target_index_bit']
                    for cycle in range(n // 8):
                        for port, (lower, upper) in enumerate(spec['pairs']):
                            index = index_of(cycle, lower, spec['lane_bits'], spec['time_bits'])
                            partner = index_of(cycle, upper, spec['lane_bits'], spec['time_bits'])
                            self.assertEqual(index ^ (1 << bit), partner)
                            stream = spec['root_stream_for_pair'][port]
                            period = spec['unique_root_streams'][stream]['period']
                            exponent = (index & ((1 << bit) - 1)) * (n >> (bit + 1))
                            self.assertEqual(root_exponent(plan, spec['stage'], stream, cycle % period), exponent)

    def test_direct_small_transform_arithmetic_using_compiled_stage_roots(self):
        # Stage roots are checked with an independent literal modular transform.
        # Values are natural-indexed; physical lane/time mapping is explicit.
        for n in (8, 32, 64):
            for field, (prime, generator) in enumerate(FIELDS):
                for inverse in (False, True):
                    plan = topology(n, inverse=inverse)
                    values = [(i * 7919 + 17) % prime for i in range(n)]
                    current = list(values)
                    r_inverse = pow(1 << 32, -1, prime)
                    for spec in plan['stages']:
                        result = list(current)
                        for cycle in range(n // 8):
                            for port, (lower, upper) in enumerate(spec['pairs']):
                                a = index_of(cycle, lower, spec['lane_bits'], spec['time_bits'])
                                b = index_of(cycle, upper, spec['lane_bits'], spec['time_bits'])
                                stream = spec['root_stream_for_pair'][port]
                                period = spec['unique_root_streams'][stream]['period']
                                w = root_word(plan, spec['stage'], stream, cycle % period, field)
                                if inverse:
                                    product = current[b] * w * r_inverse % prime
                                    result[a] = (current[a] + product) % prime
                                    result[b] = (current[a] - product) % prime
                                else:
                                    result[a] = (current[a] + current[b]) % prime
                                    result[b] = (current[a] - current[b]) * w * r_inverse % prime
                        current = result
                    expected = transform(n, 8, inverse=inverse, values=values, field=field)['output_values']
                    if inverse:
                        expected = [v * n % prime for v in expected]  # RTL DIT unscaled
                    self.assertEqual(current, expected)

    def test_fullN_geometry_timing_and_itemized_memory_without_numeric_NTT(self):
        plan = field_contract(65536)
        self.assertEqual(plan['cycle_model']['dependent_whole_square_interval_conditional'], 16660)
        self.assertEqual(plan['cycle_model']['first_field_residue_output'], 16617)
        minimal = resource_plan(payload_bits=1)
        diagnostic = resource_plan(payload_bits=16)
        self.assertEqual(minimal['per_field_original_S1_noncontrol_ALM_proxy'], 74820)
        self.assertEqual(minimal['per_field_ALM_planning_proxy'], 75420)
        self.assertEqual(minimal['memory']['S1_packed_data_only_delay_M20K'], 202)
        self.assertEqual(minimal['memory']['literal_tagged_per_FIFO_delay_M20K'], 288)
        self.assertEqual(minimal['memory']['whole_literal_listed_M20K'], 2236)
        self.assertEqual(diagnostic['memory']['whole_literal_listed_M20K'], 2716)
        self.assertLess(diagnostic['memory']['whole_M20K_margin_before_possible_divider8'], 0)
        with self.assertRaisesRegex(ValueError, 'FIELD_INCOMPLETE'):
            require_complete_field(plan)

    def test_smallN_declared_field_and_whole_timing_matches_S1(self):
        for n in (32, 64, 128, 256):
            contract = field_contract(n)['cycle_model']
            events = joined_events(n, 8)
            self.assertEqual(contract['dependent_whole_square_interval_conditional'], events['unwaited_interval'])
            self.assertEqual(contract['first_field_residue_output'] + 42, events['first_digit'])

    def test_source_compiler_no_missing_rom_promoted(self):
        for inverse in (False, True):
            output = compile_transform(32, inverse=inverse)
            self.assertEqual(output['source'].count('genefer_ntt_difdit_butterfly27 #'), 20)
            self.assertEqual(output['source'].count('genefer_stream27_mdc_commutator_slots_v2 #'), 8)
            self.assertIn('.PAYLOAD_W(1)', output['source'])
            self.assertIn('stage_pending', output['source'])
            self.assertFalse(output['complete_field'] or output['RTL_qualified'] or output['HDL_run_performed'])
            for row in output['rom_ledger']:
                if row['stored_words']:
                    self.assertEqual(len(output['rom_files'][row['file']].splitlines()), row['period'])
        with self.assertRaisesRegex(ValueError, 'FIELD_LOCAL_NUMERIC_ROOT_LIMIT'):
            compile_transform(65536)
        source_only = compile_transform(65536, emit_numeric_roms=False)
        self.assertFalse(source_only['rom_files'])
        self.assertTrue(all(not row['complete_numeric_file'] for row in source_only['rom_ledger']))

    def test_prefetch_edge_contract_reset_and_dense_back_to_back(self):
        # Simulate nonblocking ROM q. First row is a static constant bypass;
        # root r+1 read at edge r is visible before row r+1's sampled edge.
        table = [101, 202, 303, 404]
        q = -999
        index = 0
        for reset_before in (False, True):
            if reset_before:
                index = 0  # q deliberately retains old payload
            for frame in range(3):
                for row in range(8):
                    used = table[0] if row == 0 else q
                    self.assertEqual(used, table[row % 4])
                    following = 1 if row == 0 else (index + 1) % 4
                    q, index = table[following], following


if __name__ == '__main__':
    unittest.main()
