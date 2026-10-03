import unittest
from reference import stream27_canonical_fold_payload_bind as candidate
from reference import stream27_context_storage_combo_timing10_bind as parent


class FoldPayloadSource(unittest.TestCase):
    def test_default_and_exact_reverse(self):
        for n in (256,65536):
            original=parent.prepare(n,enabled=1,lean_production=0)['files'][candidate.OLD+'.sv']
            self.assertEqual(candidate.bind_leaf(original,enabled=0),original)
            changed=candidate.bind_leaf(original,enabled=1)
            self.assertEqual(candidate.reverse_leaf(changed),original)
            self.assertIn('fold_q_payload<=fold_q_pre;fold_remainder_payload<=fold_remainder_pre;',changed)
            self.assertIn('else if(fold_range_payload ||',changed)

    def test_no_other_parent_or_lean_waiver(self):
        with self.assertRaisesRegex(ValueError,'EXACT_PROTECTED'):
            candidate.bind_leaf('module arbitrary;endmodule',enabled=1)
        with self.assertRaisesRegex(ValueError,'BOOLEAN'):
            candidate.bind_leaf('',enabled=True)


if __name__=='__main__':unittest.main()
