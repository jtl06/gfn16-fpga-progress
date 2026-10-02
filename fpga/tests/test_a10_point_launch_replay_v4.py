"""Collected-evidence checks only; never execute preserved ELF/HDL."""
import copy
import json
from pathlib import Path
import unittest
from fpga.reference import a10_point_launch_replay_v4 as replay


class CollectedPointNative(unittest.TestCase):
    def test_all_three_saved_owner_replays(self):
        for field in (0, 1, 2):
            path = replay.prep.ROOT/f'results/throughput-20260929/a10-point-launch-v4/aw16-f{field}/owner-native-replay-v4.json'
            self.assertEqual(replay.replay(field), json.loads(path.read_text()))

    def test_counter_contract_mutant_is_not_an_observation_waiver(self):
        qid = 'a10-point-aw16-f0-q1-v4'
        done = json.loads((replay.prep.ROOT/'queue/done'/f'{qid}.json').read_text())
        manifest = Path(done['package']['archive']).parent/'manifest.json'
        contract = copy.deepcopy(replay.gate.make_contract(qid, manifest))
        contract['manifest']['steps'][0]['expected_stdout'] = contract['manifest']['steps'][0]['expected_stdout'].replace('88520', '88515')
        report = Path(done['result']['evidence'])/'output/native/report.json'
        with self.assertRaisesRegex(ValueError, 'contract identity'):
            replay.gate.validate_result(contract, report, id=qid)

    def test_invalid_field_replay_rejects(self):
        for field in (True, -1, 3):
            with self.assertRaisesRegex(ValueError, 'REPLAY_FIELD'):
                replay.replay(field)


if __name__ == '__main__':
    unittest.main()
