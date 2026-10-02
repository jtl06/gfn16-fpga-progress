"""Small numeric lookups + full-size geometry, no native or full numeric NTT."""
from pathlib import Path
import tempfile
import unittest

from fpga.reference import a10_packed_root_lookup_v1 as lookup
from fpga.reference import merged_negacyclic27_issue_model_v1 as geometry
from fpga.reference import merged_negacyclic27_model as math


class PackedA10LookupTests(unittest.TestCase):
    def test_lookup_matches_actual_bank_lane_root_order_all_fields_and_directions(self):
        for n in (32,256):
            for lanes in (4,64):
                for field,f in enumerate(math.FIELDS):
                    plan=lookup.layout(n,lanes,field)
                    psi=math.psi_for(n,f)
                    for inverse in (False,True):
                        for stage in range(plan['aw']):
                            for issue in range(plan['issues']):
                                actual=lookup.roots_for_request(plan,stage,issue,inverse=inverse)
                                for r in geometry.issue(n,lanes,stage,issue):
                                    root=pow(psi,-r.exponent if inverse else r.exponent,f.p)
                                    expected=root*math.normalization_constant(n,f)%f.p if inverse and stage==plan['aw']-1 else f.encode(root,1)
                                    self.assertEqual(actual[r.lane],expected)
                                self.assertEqual(actual[plan['active']:],[0]*(lanes-plan['active']))

    def test_every_aw16_symbolic_group_and_route_matches_physical_geometry(self):
        plan=lookup.layout()
        for stage,spec in enumerate(plan['stages']):
            for number in range(plan['issues']):
                address=number>>spec['issue_address_shift']
                bank=lookup.base_bank(plan,stage,number)
                for r in geometry.issue(65536,64,stage,number):
                    stream=(((r.lane>>stage)^(bank>>(stage+1)))&(spec['streams']-1)) if stage<plan['kw'] else 0
                    group=address*spec['streams']+stream if stage<plan['kw'] else address
                    self.assertEqual(group,r.root_group)
        self.assertEqual(plan['transform_roots_M20K_per_field_both_directions_proxy'],194)
        self.assertEqual(plan['recurrence_multiplier_pipes'],0)
        self.assertEqual(plan['recurrence_feedback_contexts'],0)
        self.assertEqual(plan['edge_ledger']['RAM_write_consume'],8)

    def test_source_one_read_structured_xor_tagged_destination_and_final_scale(self):
        compiled=lookup.compile_lookup(256,64,0)
        source=compiled['source']
        self.assertIn('out_valid<=valid_q && !out_error;',source)
        self.assertIn('roots<=selected_stage_roots[stage_q];out_tag<=tag_q;',source)
        self.assertIn('base_bank_q[1] ? s0_route[0][1] : s0_route[0][0]',source)
        self.assertIn('request_base_bank(stage,issue_index)',source)
        self.assertNotIn('genefer_montgomery',source)
        self.assertEqual(compiled['final_upper_scale'],math.normalization_constant(256,math.FIELDS[0]))
        with self.assertRaisesRegex(ValueError,'EXPLICIT_ONLY'):
            lookup.compile_lookup(65536)

    def test_accepted_request_tags_E0_E1_and_reset_quarantine_calendar(self):
        accepted=[(0,3),(1,8),(2,19),(5,27)]
        delivered=[(edge+1,tag) for edge,tag in accepted]
        self.assertEqual(delivered,[(1,3),(2,8),(3,19),(6,27)])
        # If reset occurs before an E1 destination capture, old valid/tag is killed.
        reset_edge=3
        retained=[(edge,tag) for edge,tag in delivered if edge<reset_edge]
        self.assertEqual(retained,[(1,3),(2,8)])
        self.assertEqual(lookup.layout()['edge_ledger'],dict(data_and_root_read_issue=0,
            root_route_and_data_destination_register=1,BF_accept=2,BF_output=7,RAM_write_consume=8))

    def test_fresh_generated_RTL_snapshot_no_native_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'lookup'
            result=lookup.prepare(path,32,64,1)
            self.assertFalse(result['native_or_engine_qualified'])
            self.assertFalse(result['full_N_numeric_NTT_performed'])
            self.assertFalse(result['promotion_allowed'])
            with self.assertRaisesRegex(ValueError,'FRESH_OUTPUT'):
                lookup.prepare(path,32,64,1)


if __name__=='__main__':
    unittest.main()
