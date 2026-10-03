"""FIELD100 scalar/source compatibility only; no local full-N numerics."""
import copy
import unittest

from fpga.reference import stream27_host_offload_field100_host_contract_v1 as contract


class Field100Host(unittest.TestCase):
    def test_frozen_c_abi_and_scalar_profiles(self):
        report=contract.verify()
        self.assertEqual(report['scalar_profiles'],16)
        self.assertFalse(report['old_R14_chip_evidence_inherited'])
        self.assertTrue(report['new_R14_F_native_required'])
        self.assertEqual([(r['n'],r['min_base'],r['K']) for r in report['geometry']],
                         [(256,599,896),(65536,131077,131456)])

    def test_wrong_prime_and_correction_permutation_reject(self):
        bundle=contract.captured(256)
        name=next(n for n in bundle['files'] if n.startswith('genefer_stream27_shared_warm_aw8_p16_f0'))
        for before,after in [(".P(32'd104857601)",".P(32'd104857600)"),
             ('ordered_c0[32+:32]=c0_in[256+:32]','ordered_c0[32+:32]=c0_in[32+:32]')]:
            bad=copy.deepcopy(bundle);bad['files'][name]=bad['files'][name].replace(before,after)
            with self.assertRaises(ValueError):contract.field_domain(bad)

    def test_wrong_floor_k_or_setup_reject(self):
        bundle=contract.captured(256)
        name=next(n for n in bundle['files'] if n.startswith('genefer_stream27_shared_warm_aw8_p16_f0'))
        for before,after in [("digit_base<32'd599","digit_base<32'd517"),("32'd896","32'd895")]:
            bad=copy.deepcopy(bundle);bad['files'][name]=bad['files'][name].replace(before,after)
            with self.assertRaises(ValueError):contract.field_domain(bad)
        bad=copy.deepcopy(bundle);bad['files'][contract.SETUP]+='\n'
        with self.assertRaises(ValueError):contract.field_domain(bad)


if __name__=='__main__':unittest.main()
