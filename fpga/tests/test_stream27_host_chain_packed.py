import copy
from unittest.mock import patch
import unittest
from reference import stream27_host_chain_packed as whole
from reference import stream27_comm_packed_bind as leaf


def fixture():
    files = {leaf.OLD + '.sv': (leaf.ROOT / leaf.PARENT).read_text(),
             'host.sv': 'module host; ' + leaf.OLD + ' field_delay(); endmodule'}
    files.update({name: 'preserved_' + name for name in whole.parent.PRESERVED})
    return dict(top='host', parameters=dict(AW=16, P=16, CONTEXTS=1, CANONICAL_PIPE_STAGES=1,
        **whole.parent.FLAGS), geometry=dict(warm_interval=8459), files=files,
        generated_sha256={name: leaf.sha(text.encode()) for name, text in files.items()},
        source_dependencies=[], source_sha256={}, diet_binding=dict(boundary_inputreg=0))


class PackedWholeTests(unittest.TestCase):
    def test_default_exact_and_copied(self):
        parent = fixture()
        result = whole.bind(parent)
        self.assertEqual(result, parent)
        self.assertIsNot(result, parent)
        with patch.object(whole.parent, 'prepare', return_value=parent) as donor:
            self.assertEqual(whole.prepare(65536, 16, paired=True), parent)
            donor.assert_called_once_with(65536, 16, paired=True)

    def test_only_leaf_consumers_change_not_other_flags(self):
        parent = fixture(); frozen = copy.deepcopy(parent)
        result = whole.bind(parent, comm_delay_packed=1)
        self.assertEqual(parent, frozen)
        self.assertEqual(result['geometry'], parent['geometry'])
        self.assertEqual(result['parameters'], parent['parameters'])
        self.assertEqual(result['top'], parent['top'])
        self.assertEqual(result['files']['host.sv'].replace(leaf.NEW, leaf.OLD), parent['files']['host.sv'])
        for name in whole.parent.PRESERVED:
            self.assertEqual(result['files'][name], parent['files'][name])
        self.assertFalse(result['packed_whole_binding']['whole_fit_GO'])

    def test_no_accidental_timing_or_unqualified_whole_donor(self):
        for key, value in [('P', 8), ('CONTEXTS', 2), ('CANONICAL_PIPE_STAGES', 0)]:
            parent = fixture(); parent['parameters'][key] = value
            with self.assertRaises(ValueError): whole.bind(parent, comm_delay_packed=1)
        parent = fixture(); parent['timing_roster'] = {'BOUNDARY_INPUTREG': 1}
        with self.assertRaises(ValueError): whole.bind(parent, comm_delay_packed=1)


if __name__ == '__main__':
    unittest.main()
