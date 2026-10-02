import json
from pathlib import Path
import re
import unittest
from fpga.reference import core27_prefill_aw5_v2_regression as gate

ROOT = Path(__file__).resolve().parents[1]


class PrefillV2Preparation(unittest.TestCase):
    def test_enum_values_extracted_from_pinned_sources(self):
        self.assertEqual(gate.validate_observer_states(ROOT), {
            'CORE_IDLE': 0, 'CORE_CARRY_WAIT': 11, 'CORE_PREFILL_CHECK': 13, 'CARRY_EMIT': 7})
        width, mapping = gate.state_enum('typedef enum logic [3:0] {A,B,C} state_t;')
        self.assertEqual((width, mapping), (4, {'A':0,'B':1,'C':2}))
        for bad in ['typedef enum logic [3:0] {A=1,B} state_t;',
                    'typedef enum logic [3:0] {A,A} state_t;', '']:
            with self.assertRaises(ValueError): gate.state_enum(bad)

    def test_observer_v3_only_state_width_binding_delta(self):
        added = '''    // Explicit-width values are mechanically checked against the exact pinned
    // core/carry enum declarations before staging and before native imports.
    localparam logic [3:0] CORE_IDLE=4'd0,CORE_CARRY_WAIT=4'd11,
        CORE_PREFILL_CHECK=4'd13,CARRY_EMIT=4'd7;
    initial if($bits(dut.state)!=4 || $bits(dut.carry_unit.state)!=4)
        $fatal(1,"T5_OBSERVER_STATE_WIDTH");
'''
        for before, after, old_top, new_top in [
            ('core27_prefill_probe_v2.sv','core27_prefill_probe_v3.sv','core27_prefill_probe_v2','core27_prefill_probe_v3'),
            ('core27_prefill_tail_probe.sv','core27_prefill_tail_probe_v3.sv','core27_prefill_tail_probe','core27_prefill_tail_probe_v3')]:
            old = (ROOT/'rtl/tb'/before).read_text()
            current = (ROOT/'rtl/tb'/after).read_text()
            restored = current.replace(added, '', 1).replace('module '+new_top, 'module '+old_top, 1)
            for key, value in [('CORE_PREFILL_CHECK','dut.PREFILL_CHECK'),('CORE_CARRY_WAIT','dut.CARRY_WAIT'),
                               ('CORE_IDLE','dut.IDLE'),('CARRY_EMIT','dut.carry_unit.EMIT')]:
                restored = restored.replace(key, value)
            self.assertEqual(restored, old)
            self.assertNotRegex(current, r'dut\.(?:carry_unit\.)?(?:IDLE|CARRY_WAIT|PREFILL_CHECK|EMIT)\b')

    def test_normal_adapter_only_top_include_rename(self):
        for suffix in ('.cpp','_threaded.cpp'):
            old = (ROOT/'rtl/tb'/('core27_prefill_normal_v2'+suffix)).read_text()
            current = (ROOT/'rtl/tb'/('core27_prefill_normal_v3'+suffix)).read_text()
            self.assertEqual(current.replace('Vcore27_prefill_probe_v3','Vcore27_prefill_probe_v2')
                             .replace('"core27_prefill_normal_v3.cpp"','"core27_prefill_normal_v2.cpp"'), old)

    def test_all_original_ninety_sources_preserved(self):
        old = json.loads((ROOT/'results/throughput-20260929/core27-prefill-aw5-stage-v1/manifest.json').read_text())
        pins = gate.source_pins(ROOT)
        self.assertEqual(len(old['sources']), 90)
        self.assertTrue(all(pins.get(k) == v for k,v in old['sources'].items()))

    def test_no_warning_suppression_and_separate_snapshot(self):
        source = (ROOT/gate.RUNNER).read_text()
        self.assertNotIn('-Wno', source)
        self.assertNotIn('lint_off', (ROOT/'rtl/tb/core27_prefill_probe_v3.sv').read_text())
        self.assertIn('-Werror=return-type', source)
        self.assertIn('core27-prefill-aw5-v2/snapshot-v2/fpga', str(gate.ROOT))
        self.assertEqual(gate.compiled(ROOT,'normal')[-1], 'rtl/tb/core27_prefill_probe_v3.sv')

    def test_target_footers_bind_every_command_field(self):
        for group in gate.GROUPS:
            if group == 'normal': continue
            for _, command in gate.commands('/e','/v',group):
                mode = command[1]; changed = mode in ('--changed-base','--base-reject')
                counts = (3,3,0) if mode == '--changed-base' else (2,2,1) if mode == '--base-reject' else (1,1,1)
                row = 'none' if changed else command[4]
                fields = dict(mode=mode, age='0' if changed else command[3], row=row,
                              row_index='0' if row=='first' else '1', middle_aliases_final='1', event_hits='1',
                              successful=str(counts[0]),readbacks=str(counts[1]),recoveries=str(counts[2]))
                render = lambda f: 'T5_TARGET_PASS '+' '.join(k+'='+v for k,v in f.items())+'\n'
                self.assertEqual(gate.check_target_output(render(fields),command),fields)
                for key in fields:
                    with self.subTest(group=group, command=command, field=key):
                        changed_fields = dict(fields);changed_fields[key] = 'wrong'
                        with self.assertRaisesRegex(ValueError,'command-bound'):
                            gate.check_target_output(render(changed_fields),command)
                with self.assertRaisesRegex(ValueError,'unique'):
                    gate.check_target_output(render(fields).strip()+' age=0\n',command)
                with self.assertRaisesRegex(ValueError,'one targeted'):
                    gate.check_target_output(render(fields)*2,command)

    def test_quarantine_checks_all_requested_flags(self):
        source = (ROOT/'rtl/tb/core27_prefill_tail_v2.cpp').read_text()
        self.assertIn('!d.busy && !d.done && !d.error && !d.read_valid && !d.dbg_prefilled && !d.profile_cache_valid,"T5_RESET_TAIL_GHOST"',source)
        self.assertIn('!d.busy && !d.done && d.error && !d.read_valid && !d.dbg_prefilled && !d.profile_cache_valid,"T5_FAILED_QUARANTINE_LEAK"',source)


if __name__ == '__main__': unittest.main()
