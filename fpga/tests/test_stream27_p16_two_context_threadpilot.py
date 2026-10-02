import copy
import json
import unittest
from fpga.reference import stream27_p16_two_context_threadpilot as pilot


class C2ThreadPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.m,cls.files=pilot.role()

    def test_unchanged_production_and_feed_count_source_contract(self):
        m,files=self.m,self.files
        self.assertEqual(len(m['build']['sv_sources']),54)
        for name,pin in m['r84']['production_generated_sha256'].items():
            self.assertEqual(pilot.sha(files['rtl/'+name]),pin)
        text=files[pilot.CPP].decode()
        self.assertIn('d.start_contexts=d.batch_mode=d.feed_mode=mask',text)
        self.assertIn('const bool accepted_command=d.command_accept;',text)
        self.assertLess(text.index('const bool accepted_command'),text.index('if(accepted_command)'))
        self.assertIn('R84_THREAD100_ALL_DESCRIPTORS_ACCEPTED',text)
        self.assertIn('d.command_double=BITS[command_ctx][next_command[command_ctx]]',text)
        self.assertIn('constexpr unsigned',files['rtl/tb/s4_p16_two_context_full_config.h'].decode())
        self.assertNotIn('BITS[2][2]',files['rtl/tb/s4_p16_two_context_full_config.h'].decode())
        self.assertEqual([sum(x) for x in pilot.bits()],[51,50])
        self.assertEqual(m['test_role'],'normal')
        self.assertFalse(m['r84']['native_thread_pilot']['baseline_C1_forecast_used'])

    def test_all100_port_correction_feedback_windows(self):
        v=self.m['r84']['own100_calendar']
        self.assertEqual(v['frames'],200)
        self.assertEqual(v['launch_gaps'],[4229,4230])
        self.assertEqual(v['lease_peak'],3)
        self.assertEqual(v['feedback_peak_rows'],[0,0])
        self.assertEqual(len(v['correction']),200)
        self.assertGreaterEqual(min(x['margin'] for x in v['correction']),0)
        self.assertEqual(v['window_widths']['carry'],4142)
        self.assertFalse(v['full_N_numeric_performed'])

    @staticmethod
    def footer():
        launches=[[204+k*8459 for k in range(100)],[4433+k*8459 for k in range(100)]]
        warm=[row[-1]+12558 for row in launches]
        done=[warm[0]+660000,warm[0]+1320000]
        return dict(aw=16,p=16,contexts=2,bases=pilot.BASES,count_per_context=100,squares=200,
            descriptors=198,doubles=101,reads=4*65536,signed96=True,independent_reference=True,
            initial_resets=1,initial_load_words=2*65536,interval=8459,peer_live_reads=65536,
            model_threads=8,launches=launches,joint_cycles=done[1]+65536,overlap_edges=1000000,
            done_edges=done,warm_edges=warm,setup_edges=[99,199],reference_seconds=100.0,model_seconds=400.0,seconds=500.0)

    def test_typed_native_thread100_and_epoch_counter_rejections(self):
        def check(v):return pilot.validate('R84_C2_THREAD100_PASS '+json.dumps(v)+'\n','',0,pilot.config(),{})
        self.assertEqual(check(self.footer())['status'],'PASS_expected_contracts')
        for k,x in [('model_threads',1),('descriptors',197),('doubles',100),('initial_resets',2),
                    ('count_per_context',99),('peer_live_reads',65535),('seconds',501.0)]:
            v=self.footer();v[k]=x
            with self.subTest(key=k),self.assertRaises(ValueError):check(v)
        v=copy.deepcopy(self.footer());v['launches'][1][50]+=1
        with self.assertRaises(ValueError):check(v)


if __name__=='__main__':unittest.main()
