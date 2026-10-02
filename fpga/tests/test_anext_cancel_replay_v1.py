import json
import unittest
from fpga.reference import anext_cancel_replay_v1 as replay


class ActualCancelHostEvidence(unittest.TestCase):
    def test_both_actual_native_archives_and_saved_owner_replays(self):
        expected={5:'5b27807e95df71594180f46d71982c30ec61eaa800b9a6919fa673ea13f204fe',
                  8:'428616f82ef83ae2a15ea6d0470db85066d7b9c70993260d1bba9c9ab2b1a344'}
        for aw in (5,8):
            result=replay.replay(aw)
            saved=json.loads((replay.native.ROOT/f'results/throughput-20260929/anext-cancel-host-native-v1/aw{aw}/owner-native-replay-v1.json').read_text())
            self.assertEqual(result,saved);self.assertEqual(result['report_sha256'],expected[aw])
            self.assertEqual((result['sources'],result['generated'],result['artifacts']),(45,33,18))
            self.assertEqual(result['limits']['memory_max_bytes'],8*(1<<30))
            self.assertEqual(result['counts']['cancel_seams'],4);self.assertFalse(result['promotion_allowed'])

    def test_AW8_bound_to_exact_native_pass_not_owner_opinion(self):
        root=replay.native.ROOT/'queue';done=json.loads((root/'done/anext-cancel-host-aw8-q1-v1.json').read_text())
        dependency=done['after'][0]
        gate=json.loads((root/'evidence/anext-cancel-host-aw5-q1-v1/gate-receipt.json').read_text())
        parent=json.loads((root/'done/anext-cancel-host-aw5-q1-v1.json').read_text())
        self.assertEqual(dependency['id'],'anext-cancel-host-aw5-q1-v1')
        self.assertEqual(dependency['functional_sha256'],parent['dependency_gate']['functional_sha256'])
        self.assertEqual(replay.gate.sha(root/'evidence/anext-cancel-host-aw5-q1-v1/gate-receipt.json'),
                         parent['dependency_gate']['sha256'])
        self.assertEqual(gate['contract_sha256'],parent['dependency_gate']['contract_sha256'])
        self.assertEqual(gate['status'],'PASS_expected_contracts')


if __name__=='__main__':unittest.main()
