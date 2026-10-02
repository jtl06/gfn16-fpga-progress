import copy
import unittest
from fpga.reference import stream27_shared_field_flags as donor
from fpga.reference import stream27_fault_fanout_bind as bind
from fpga.reference import stream27_fault_fanout_native as native
from fpga.reference import stream27_fault_fanout_fault_native as faults


class FaultFanoutSourceTests(unittest.TestCase):
    def test_exact_reverse_and_unmodified_dependencies_all_fields(self):
        for field in range(3):
            parent=donor.prepare(256,8,field,mode='warm_signed')
            before=copy.deepcopy(parent);after=bind.bind(parent)
            self.assertEqual(parent,before)
            self.assertEqual(bind.bind(parent,enabled=0),parent)
            root=after['files'][after['top']+'.sv']
            self.assertEqual(bind.reverse_root(root,parent['top'],after['top']),parent['files'][parent['top']+'.sv'])
            for name,text in parent['files'].items():
                if name!=parent['top']+'.sv':self.assertEqual(after['files'][name],text)
            self.assertEqual(after['geometry'],parent['geometry'])
            self.assertEqual(root.count('controller_error<=1;'),1)
            self.assertEqual(root.count('controller_error<=0;'),1)
            self.assertEqual(root.count('if('+bind.SETTER+')'),1)
            self.assertIn('assign out_error=controller_error;',root)
            self.assertEqual(root.count('.quarantine(transform_quarantine['),2)

    def test_boundary_composition_and_original_setter_fail_closed(self):
        parent=donor.prepare(256,8,2,mode='warm_signed',boundary_inputreg=1)
        after=bind.bind(parent)
        self.assertEqual(after['geometry'],parent['geometry'])
        self.assertIn('.quarantine(stop),.in_valid(boundary_slot)',after['files'][after['top']+'.sv'])
        broken=copy.deepcopy(parent)
        broken['files'][parent['top']+'.sv']=broken['files'][parent['top']+'.sv'].replace(bind.SETTER,'!stop && admission_bad')
        with self.assertRaisesRegex(ValueError,'EXACT_ORIGINAL_SETTER'):bind.bind(broken)
        with self.assertRaisesRegex(ValueError,'ALREADY_BOUND'):bind.bind(after)

    def test_replicas_equal_original_for_every_fault_reset_calendar(self):
        # Exhaust all short raw reset/fault inputs, including between-edge
        # reset and a fault at a previously legal commit origin edge.
        for pattern in range(1<<10):
            original=False;replicas=[False,False]
            for edge in range(5):
                rst=bool(pattern>>(2*edge)&1);fault=bool(pattern>>(2*edge+1)&1)
                setter=(not original) and fault
                if not rst:original=False;replicas=[False,False]
                else:
                    original=original or setter
                    replicas=[q or setter for q in replicas]
                self.assertEqual(replicas,[original,original])

    def test_source_specific_normal_role_independent_math_and_calendar(self):
        m,files,snapshot=native.role(8,2)
        self.assertEqual(m['test_role'],'normal')
        self.assertEqual(m['build']['parameters']['QUARANTINE_REPLICAS'],1)
        self.assertIn(b'ref_self_check();',files[native.CPP])
        self.assertIn(b'stream27_shared_reference_ntt_v1.h',files[native.CPP])
        self.assertEqual(m['fault_fanout']['counts'],dict(cases=9,frames=9,physical_rows=288,
            physical_words=2304,eligible_rows=224,commits=224,peak_owners=1))
        self.assertEqual(m['steps'][0]['expected_stdout'],
            'S4_FAULT_FANOUT_NORMAL aw=8 p=8 field=2 boundary_inputreg=0 cases=9 frames=9 physical_rows=288 physical_words=2304 eligible_rows=224 commits=224 peak_owners=1\n')
        self.assertTrue(all(m['sources'][name]==pin for name,pin in snapshot.items()))

    def test_separate_genuine_fault_and_typed_setter_mutation_contract(self):
        m,files=faults.role()
        self.assertEqual(m['test_role'],'deliberate_fault')
        self.assertEqual([s['expected_returncode'] for s in m['steps']],[0,41])
        self.assertEqual(m['steps'][0]['expected_stdout'],m['steps'][1]['expected_stdout'])
        self.assertIn('missing_first=88 ',m['steps'][0]['expected_stdout'])
        self.assertIn('reset_ages=10,179 ',m['steps'][0]['expected_stdout'])
        sv=files['rtl/'+m['build']['top']+'.sv'].decode()
        self.assertIn('.fault_set(('+bind.SETTER+') && !debug_mask_replica_set)',sv)
        self.assertIn('.frame_start(digit_slot && !debug_drop_forward',sv)
        cpp=files[faults.CPP].decode()
        for token in ('S4_FAULT_FANOUT_ACTUAL_MISSING_FIRST_ORIGIN',
                      'S4_FAULT_FANOUT_ACCEPTED_ORIGIN_TAIL_NOT_ROLLED_BACK',
                      'S4_FAULT_FANOUT_RESET_LONG_STALE_TAIL',
                      'S4_FAULT_FANOUT_CANCELED_RAW_TAIL_CALENDAR',
                      'normal(d,c);footer(c);','if(negative)'):
            self.assertIn(token,cpp)


if __name__=='__main__':unittest.main()
