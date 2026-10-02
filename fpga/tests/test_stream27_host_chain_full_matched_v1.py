import unittest
from fpga.reference import stream27_host_chain_full_matched_v1 as candidate


class MatchedBaseNormal(unittest.TestCase):
    def test_same_RTL_new_base_and_normal_only(self):
        old, old_files = candidate.parent.role()
        new, files = candidate.role()
        self.assertEqual(old['build'], new['build'])
        self.assertEqual({k: v for k, v in old_files.items() if k.endswith('.sv')},
            {k: v for k, v in files.items() if k.endswith('.sv')})
        self.assertEqual(old_files[candidate.parent.CPP], files[candidate.parent.CPP])
        self.assertIn(b'BASE=604832956', files[candidate.parent.HEADER])
        self.assertEqual(len(new['steps']), 1)
        self.assertEqual(new['full_host']['base'], 604832956)
        self.assertFalse(new['full_host']['reused_base1e9_numeric_qualification'])

    def test_closed_base_and_normal_contract(self):
        stdout = candidate.parent.footer_prefix() + '272282\n'
        config = dict(aw=16, p=8, base=604832956, mode='normal')
        result = candidate.validate(stdout, '', 0, config, {})
        self.assertEqual(result['counts']['paired_reads'], 131072)
        with self.assertRaises(ValueError):
            candidate.validate(stdout, '', 0, {**config, 'base': 1000000000}, {})
        with self.assertRaises(ValueError):
            candidate.validate(stdout, '', 0, {**config, 'mode': 'oracle'}, {})


if __name__ == '__main__':
    unittest.main()
