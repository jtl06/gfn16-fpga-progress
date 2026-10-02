"""Independent scheduling and strict typed counter controls; no HDL/math run."""
import json
import unittest
from fpga.reference import stream27_p8_warm_native_v2 as native
from fpga.reference import stream27_p8_warm_prepare_v2 as prepare
from fpga.reference import stream27_p8_warm_prepare_v1 as old


class P8WarmLeaseSuccessor(unittest.TestCase):
    def test_same_edge_bank_selection_and_release(self):
        # First lease releases209. Second exactly there uses the other old-free
        # bank, leaving post-edge occupancy1; the edge before leaves2.
        self.assertEqual(native.lease_ledger([0, 209], 178, 32)['peak'], 1)
        self.assertEqual(native.lease_ledger([0, 208], 178, 32)['peak'], 2)
        row = native.lease_ledger([0, 32, 209], 178, 32)
        self.assertEqual(row['rejected'], [209]) # No free bank before this release.
        self.assertEqual(row['accepted'], [0, 32]); self.assertEqual(row['released'], [209, 241])

    def test_geometry_derived_peak_not_observed_footer(self):
        self.assertEqual(native.ownership_contract(8, 0)['first_release'], 209)
        self.assertEqual(native.ownership_contract(8, 0)['post_edge_peak'], 1)
        self.assertEqual(native.ownership_contract(16, 0)['first_release'], 24801)
        self.assertEqual(native.ownership_contract(16, 0)['post_edge_peak'], 2)

    def test_roles_RTL_and_frame_vector_prefix_unchanged(self):
        for aw, field in ((8, 0), (8, 1), (8, 2), (16, 0)):
            a, before = old.role(aw, field); b, after = prepare.role(aw, field)
            for name, raw in before.items():
                if name not in (native.CPP, native.HEADER): self.assertEqual(raw, after[name])
            marker = b'struct Counts{'
            aa = before[native.CPP].split(marker)[0].replace(b'static bool negative_oracle=false;\n', b'')
            bb = after[native.CPP].split(marker)[0].replace(b'static bool negative_oracle=false,negative_peak=false;\n', b'')
            self.assertEqual(aa, bb)
            self.assertEqual(a['build'], b['build']); self.assertEqual(a['p8_warm']['geometry'], b['p8_warm']['geometry'])
            self.assertEqual(a['p8_warm']['generated_sha256'], b['p8_warm']['generated_sha256'])
            self.assertEqual(json.loads(json.dumps(b['p8_warm']['ownership_contract'])), native.ownership_contract(aw, field))
            self.assertEqual([s['expected_returncode'] for s in b['steps']], [0, 1, 1])
            self.assertIn(b'unsigned(d.owner_count)==expected_owners', after[native.CPP])
            self.assertIn(b'counts.peak==EXPECTED_PEAK', after[native.CPP])

    def test_exact_peak_and_oracle_typed_negatives(self):
        for aw, field in ((8, 0), (8, 1), (8, 2), (16, 0)):
            contracts = native.contracts(aw, field)
            for mode in ('normal', 'oracle', 'peak'):
                v = contracts[mode]; native.validate(v['stdout'], v['stderr'], v['returncode'], dict(aw=aw, field=field, mode=mode), {})
                with self.assertRaisesRegex(ValueError, 'TYPED_OUTPUT'):
                    native.validate(v['stdout']+'extra', v['stderr'], v['returncode'], dict(aw=aw, field=field, mode=mode), {})
            v = contracts['normal']; bad = v['stdout'].replace(f"peak_owners={v['stdout'].split('peak_owners=')[1][0]}",
                                                             'peak_owners='+('2' if aw == 8 else '1'))
            with self.assertRaisesRegex(ValueError, 'TYPED_OUTPUT'):
                native.validate(bad, '', 0, dict(aw=aw, field=field, mode='normal'), {})


if __name__ == '__main__': unittest.main()
