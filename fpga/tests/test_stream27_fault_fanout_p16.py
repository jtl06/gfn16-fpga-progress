import copy
import unittest
from fpga.reference import stream27_shared_field_flags as donor
from fpga.reference import stream27_fault_fanout_bind as frozen
from fpga.reference import stream27_fault_fanout_p16_bind as binding
from fpga.reference import stream27_fault_fanout_p16_native as native
from fpga.reference import stream27_fault_fanout_p16_fault_native as faults


class P16FaultFanoutTests(unittest.TestCase):
    def test_exact_setter_reset_reverse_controls_children_and_calendar(self):
        for field in range(3):
            parent=donor.prepare(256,16,field,mode='warm_signed',corr_serial_bfs=2);before=copy.deepcopy(parent)
            b=binding.bind(parent);self.assertEqual(parent,before);self.assertEqual(binding.bind(parent,enabled=0),parent)
            self.assertEqual(b['geometry'],parent['geometry'])
            self.assertEqual(frozen.reverse_root(b['files'][b['top']+'.sv'],parent['top'],b['top']),parent['files'][parent['top']+'.sv'])
            for name,text in parent['files'].items():
                if name!=parent['top']+'.sv':self.assertEqual(b['files'][name],text)
            with self.assertRaisesRegex(ValueError,'P8_CONTEXTS1'):frozen.bind(parent)
            with self.assertRaisesRegex(ValueError,'ALREADY_BOUND'):binding.bind(b)

    def test_fails_closed_and_composes_copied_p16_diet(self):
        parent=donor.prepare(256,16,1,mode='warm_signed',corr_serial_bfs=2,comm_stage_shared_mlab=1,mont_factored=1)
        b=binding.bind(parent);self.assertEqual(b['geometry'],parent['geometry'])
        broken=copy.deepcopy(parent);name=parent['top']+'.sv'
        broken['files'][name]=broken['files'][name].replace(frozen.SETTER,'!stop && admission_bad')
        with self.assertRaisesRegex(ValueError,'EXACT_SETTER'):binding.bind(broken)

    def test_independent_p16_corr2_normal_role_fixed_oracle_counts(self):
        m,files,_=native.role();self.assertEqual(m['test_role'],'normal')
        self.assertEqual(m['build']['parameters']['P'],16);self.assertEqual(m['build']['parameters']['CORR_SERIAL_BFS'],2)
        self.assertIn(b'ref_self_check();',files[native.CPP])
        self.assertEqual(m['steps'][0]['expected_stdout'],'S4_P16_FAULT_FANOUT_NORMAL aw=8 p=16 field=1 corr_serial_bfs=2 cases=9 frames=9 physical_rows=144 physical_words=2304 eligible_rows=112 commits=112 peak_owners=1\n')

    def test_p16_actual_serial2_fault_calendar_and_typed_origin_contract(self):
        m,files=faults.role();self.assertEqual(m['test_role'],'deliberate_fault')
        self.assertEqual([s['expected_returncode'] for s in m['steps']],[0,41])
        self.assertEqual(m['steps'][0]['expected_stdout'],m['steps'][1]['expected_stdout'])
        g=m['fault_fanout']['geometry'];self.assertIn(f'missing_first={g["pointwise_accept"]}',m['steps'][0]['expected_stdout'])
        cpp=files[faults.CPP].decode();self.assertIn('normal(d,c);footer(c);',cpp)
        self.assertIn('S4_P16_FAULT_FANOUT_ACCEPTED_ORIGIN_TAIL_NOT_ROLLED_BACK',cpp)
        self.assertIn('S4_P16_FAULT_FANOUT_CANCELED_RAW_TAIL_CALENDAR',cpp)


if __name__=='__main__':unittest.main()
