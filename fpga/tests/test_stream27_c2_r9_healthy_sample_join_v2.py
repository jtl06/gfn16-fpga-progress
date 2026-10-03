import copy
import unittest
from reference import stream27_c2_r9_healthy_sample_join as base
from reference import stream27_c2_r9_healthy_sample_join_v2 as binding


class R9Binding(unittest.TestCase):
    def test_exact_producer_and_actual_log_binding(self):
        self.assertEqual(base.own.sha((base.ROOT/base.SELF).read_bytes()),binding.BASE_PIN)
        self.assertEqual(base.own.sha((base.ROOT/base.INDEX).read_bytes()),binding.INDEX_PIN)
        self.assertIn('normal-full-c2-r9-alone-and-joint.log',
                      (base.ROOT/binding.SELF).read_text())

    def test_publication_guard_negative(self):
        g=base.source()['geometry'];e=base.arithmetic.event_calendar(g,2)
        f=dict(interval=8459,warm_edges=e['warm_edges'],done_edges=e['publication_edges'],
            joint_cycles=e['pair_completion_cycles']+65536,setup_edges=[99,199],
            bases=[604832956,999999937],signed96=True,independent_reference=True,
            launches=[[x+i*8459 for i in range(2)] for x in e['first_edges']],
            context_alone_bit_identical=True,squares=8,reads=393216,peer_live_reads=65536)
        self.assertEqual(base.validate_footer(f,2,g),e)
        bad=copy.deepcopy(f);bad['done_edges'][1]-=1
        with self.assertRaises(ValueError):base.validate_footer(bad,2,g)


if __name__=='__main__':unittest.main()
