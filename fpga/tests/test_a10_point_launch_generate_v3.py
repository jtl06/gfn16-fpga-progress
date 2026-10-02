"""Only source/symbolic token checks; native oracle gates follow separately."""
import unittest
from fpga.reference import a10_point_launch_generate_v3 as gen


class PointLaunch(unittest.TestCase):
    def test_exact_fitted_source_and_measured_cone(self):
        self.assertEqual(gen.sha(gen.source_parent().encode()),gen.PARENT_SHA)

    def test_eight_narrow_changes_restore_parent(self):
        source=gen.source();restored=source
        self.assertEqual((gen.ROOT/gen.TARGET).read_text(),source)
        self.assertEqual(len(gen.changes()),8)
        for old,new in reversed(gen.changes()):restored=restored.replace(new,old)
        self.assertEqual(restored.rstrip(),gen.source_parent().rstrip())
        self.assertIn('(* preserve,dont_merge *) logic [31:0] point_lhs_q;',source)
        self.assertIn('always_ff @(posedge clk)if(rst_n && mul_in_valid[lane])',source)
        self.assertIn('point_launch_valid<=mul_in_valid[lane];',source)
        self.assertNotIn('assign mul_lhs=point_half_d ? data_q',source)

    def test_BF_root_profile_domain_unchanged(self):
        before,after=gen.source_parent(),gen.source()
        self.assertEqual(before[before.index('    genefer_a10_profile3_constants_v1'):before.index('    function automatic')],
                         after[after.index('    genefer_a10_profile3_constants_v1'):after.index('    function automatic')])
        for token in ('data_destination[bank]<=data_q[bank];','orientation_pipe[7]',
            '.gs(bf_in_valid[lane] && active_inverse)', '.normalization(normalization)',
            'if(bf_in_valid[0] && (!lookup_valid || lookup_tag!=issue_tag_destination))'):
            self.assertEqual(before.count(token),after.count(token))

    def test_cycles_only_point_plus_one(self):
        for aw in (5,8,16):
            original=gen.math.ledger(aw);new=gen.ledger(aw)
            self.assertEqual(new['transform_cycles'],original['transform_cycles'])
            self.assertEqual(new['point_cycles'],original['point_cycles']+1)
            self.assertEqual(new['engine_work_cycles'],original['engine_work_cycles']+5)
            self.assertEqual(new['whole_controller_ntt_cycles'],original['whole_controller_ntt_cycles']+1)
            for key in ('roots_per_transform','ROM_reads_per_transform','normalization_products'):
                self.assertEqual(new[key],original[key])
        self.assertEqual(gen.ledger(16)['point_cycles'],1032)
        self.assertEqual(gen.ledger(16)['whole_controller_ntt_cycles'],17710)

    def test_symbolic_point_bank_row_tokens_no_collision(self):
        for aw in (5,8,16):
            groups=((1<<aw)+63)//64
            issue={r:dict(group=r,row=r//2,half=sum((r>>j)&1 for j in range(0,max(0,aw-6),7))%2) for r in range(groups)}
            write={r+8:token for r,token in issue.items()}
            self.assertEqual(len(write),groups)
            for edge,token in write.items():
                self.assertEqual(token,issue[edge-8])
                if edge in issue:self.assertNotEqual(token['row'],issue[edge]['row'])
            # Removing either final point row/half edge is an intentional
            # source-tag fault; a multirow group must not alias its predecessor.
            if groups>1:self.assertNotEqual(issue[0],issue[1])


if __name__=='__main__':unittest.main()
