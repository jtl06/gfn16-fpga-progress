import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from fpga.reference import core27_prefill_aw5_regression as gate
from fpga.reference.core27_prefill_target_vectors import target_vectors, square
from fpga.reference.core27_prefill_qualification_mutations import TEE_MUTANTS, tee_control, mutate_tee


ROOT = Path(__file__).resolve().parents[1]
CORE = 'genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill'


class QualificationPreparation(unittest.TestCase):
    def test_original_checkpoint_unchanged(self):
        d = json.loads((ROOT/gate.CHECKPOINT).read_text())
        for name, digest in d['files'].items():
            self.assertEqual(hashlib.sha256((ROOT.parent/name).read_bytes()).hexdigest(), digest)

    def test_fault_bridge_is_exact_explicit_injection_delta(self):
        core = (ROOT/'rtl/kernel'/(CORE+'.sv')).read_text()
        bridge = (ROOT/'rtl/tb/core27_prefill_fault_bridge.sv').read_text()
        bridge = bridge.removeprefix('// Simulation-only explicit fault bridge; never synthesize or promote this top.\n')
        bridge = bridge.replace('module core27_prefill_fault_bridge #(', 'module '+CORE+' #(')
        bridge = bridge.replace('    input logic [2:0] sim_host_error,\n    input logic sim_carry_error,\n', '')
        bridge = bridge.replace('    logic native_carry_error;\n    assign carry_error=native_carry_error | sim_carry_error;\n', '')
        bridge = bridge.replace('    logic [2:0] native_ntt_host_error;\n    assign ntt_host_error=native_ntt_host_error | sim_host_error;\n', '')
        bridge = bridge.replace('.host_error(native_ntt_host_error[f])', '.host_error(ntt_host_error[f])')
        bridge = bridge.replace('.error(native_carry_error)', '.error(carry_error)')
        self.assertEqual(bridge, core)

    def test_tail_observer_derives_from_v2(self):
        expected = (ROOT/'rtl/tb/core27_prefill_probe_v2.sv').read_text()
        expected = expected.replace('module core27_prefill_probe_v2 #(', 'module core27_prefill_tail_probe #(')
        expected = expected.replace(CORE+' #(', 'core27_prefill_fault_bridge #(')
        expected = expected.replace('input logic clk, rst_n, load_we, read_en, start,',
                    'input logic clk, rst_n, load_we, read_en, start,\n    input logic [2:0] sim_host_error,\n    input logic sim_carry_error,')
        self.assertEqual(expected, (ROOT/'rtl/tb/core27_prefill_tail_probe.sv').read_text())

    def test_independent_source_and_destination_monitoring(self):
        s = (ROOT/'rtl/tb/core27_prefill_probe_v2.sv').read_text()
        for token in ['carry_unit.mem_we', 'carry_unit.mem_en', 'carry_unit.mem_addr', 'carry_unit.mem_data',
                      'source_commit_valid!=dut.emit_commit_valid', 'observed_data[0]<=source_commit_data',
                      'child.data_we', 'child.data_wa', 'child.data_w']:
            self.assertIn(token, s)
        self.assertNotIn('observed_data[0]<=dut.emit_commit_data', s)
        self.assertNotIn('public_flat', s)

    def test_tee_mutants_have_fresh_symmetric_guard_control(self):
        s = (ROOT/'rtl/kernel/genefer_carry_prefix_stream_precision_emit.sv').read_text()
        monitor = (ROOT/'rtl/tb/core27_prefill_probe_v2.sv').read_text()
        for name, (before, after, fatal) in TEE_MUTANTS.items():
            changed, expected = mutate_tee(s, name)
            self.assertEqual(changed.replace(after, before, 1), tee_control(s))
            self.assertEqual(fatal, expected)
            self.assertIn(fatal, monitor)

    def test_bounded_groups_and_both_emission_selections(self):
        for group in gate.GROUPS:
            commands = gate.commands('/exe', '/vectors', group)
            self.assertLessEqual(len(commands), 7)
            self.assertEqual(len({x[0] for x in commands}), len(commands))
        self.assertEqual(len(gate.commands('/e', '/v', 'reset-tail')), 7)
        self.assertEqual([c[1][-2] for c in gate.commands('/e', '/v', 'reset-emission')], ['first','middle'])
        self.assertEqual(len(gate.commands('/e', '/v', 'base-change')), 2)

    def test_aw5_vectors_exact_integer_and_canonical(self):
        lines = target_vectors().splitlines()
        n, a, b = map(int, lines[0].split())
        rows = [list(map(int, line.split())) for line in lines[1:]]
        self.assertEqual(n, 32)
        self.assertTrue(all(len(row) == n for row in rows))
        self.assertEqual(square(rows[0], a), rows[1])
        self.assertEqual(square(rows[1], b), rows[2])
        self.assertEqual(square(rows[2], b, 1), rows[3])
        self.assertTrue(any(x >= 2*n+5 for x in rows[1]))
        with self.assertRaisesRegex(ValueError, 'AW5'): target_vectors(16)

    def test_closed_compiled_lists(self):
        self.assertEqual(len(gate.compiled(ROOT, 'normal')), 17)
        self.assertEqual(len(gate.compiled(ROOT, 'reset-tail')), 18)
        for group in gate.GROUPS:
            for name in gate.compiled(ROOT, group): self.assertTrue((ROOT/name).is_file())
        pins = gate.source_pins(ROOT)
        self.assertIn(gate.RUNNER, pins)
        self.assertIn('rtl/tb/core27_prefill_probe.sv', pins)

    def test_normal_output_phase_gate_and_tampering(self):
        parent = json.loads((ROOT/gate.NORMAL_REPORT).read_text())
        lines = []
        for old in parent['metrics']:
            row = {k:v for k,v in old.items() if k not in ('case','aw','n')}
            row['carry'] += 5; row['cycles'] += 5
            row.update(prefill_before=0, prefill_after=1)
            lines.append(old['case']+' '+' '.join(f'{k}={v}' for k,v in row.items()))
        lines.append('PASS n=32 squares=568 readbacks=561 aborts=20')
        output = '\n'.join(lines)
        self.assertEqual(len(gate.check_normal(output, parent)), 568)
        with self.assertRaisesRegex(ValueError, 'phase delta'):
            gate.check_normal(output.replace('carry=58', 'carry=59', 1), parent)
        with self.assertRaisesRegex(ValueError, 'footer'):
            gate.check_normal(output.replace('aborts=20', 'aborts=19'), parent)

    def test_native_controls_are_not_relaxed(self):
        s = (ROOT/gate.RUNNER).read_text()
        for token in ['-Werror=return-type', "socket.gethostname() == 'aethia'", "limits['affinity'] == [0, 2]",
                      'resource.RLIMIT_CORE', 'resource.RLIMIT_AS', '6*GIB', 'start_new_session=True',
                      'os.killpg', 'LOCK.open', 'baseline.check_probe', 'source-only imports']:
            self.assertIn(token, s)
        self.assertIn('core27_prefill_probe_v2', s)


if __name__ == '__main__': unittest.main()
