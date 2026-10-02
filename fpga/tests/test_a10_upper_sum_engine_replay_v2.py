import json
import unittest
from fpga.reference import a10_upper_sum_engine_replay_v2 as native


class ActualUpperEngines(unittest.TestCase):
    def test_all_nine_saved_owner_replays(self):
        for aw in (5,8,16):
            for field in range(3):
                path=native.prep.ROOT/f'results/throughput-20260929/a10-upper-sum-engine-v2/aw{aw}-f{field}/owner-native-replay-v2.json'
                result=native.replay(aw,field)
                self.assertEqual(result,json.loads(path.read_text()))
                self.assertEqual(result['engine_cycle_delta'],0)
                self.assertEqual(result['cell_input_to_output'],5)
                self.assertFalse(result['promotion_allowed'])

    def test_scope_and_geometry_rejects(self):
        for aw,field in ((4,0),(17,0),(5,3),(5,True)):
            with self.assertRaisesRegex(ValueError,'NATIVE_ROLE'):
                native.replay(aw,field)


if __name__=='__main__':unittest.main()
