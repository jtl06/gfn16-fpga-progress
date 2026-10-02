"""Read-only replay of collected real native evidence; never rerun HDL."""
import json
import unittest
from fpga.reference import stream27_canonical_image_replay_v1 as owner


class ActualReplay(unittest.TestCase):
    def test_four_actual_native_receipts_and_typed_negative(self):
        for aw in (5,8):
            for p in (8,16):
                current=owner.replay(aw,p)
                saved=json.loads((owner.native.ROOT/f'results/throughput-20260929/s4-canonical-image-v2/aw{aw}-p{p}/owner-native-replay-v1.json').read_text())
                self.assertEqual(current,saved)
                self.assertEqual([s['returncode'] for s in current['steps'][-2:]],[0,1])
                self.assertEqual(current['properties']['MainPID'],'0')
                self.assertFalse(current['promotion_allowed'])


if __name__=='__main__':unittest.main()
