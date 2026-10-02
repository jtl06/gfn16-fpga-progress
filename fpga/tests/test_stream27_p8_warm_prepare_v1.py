"""Pure source/typed-contract checks; never runs HDL/compiler/ELF/full-N math."""
import unittest
from fpga.reference import stream27_p8_warm_native_v1 as native
from fpga.reference import stream27_p8_warm_prepare_v1 as prepare
from fpga.reference import stream27_shared_field_v1 as field
from fpga.reference import stream27_shared_warm_full_native_v1 as parent


class P8WarmPreparation(unittest.TestCase):
    def test_roles_exact_geometry_and_measured_RTL(self):
        for aw, f in ((8, 0), (8, 1), (8, 2), (16, 0)):
            m, files = prepare.role(aw, f); p = m['p8_warm']
            self.assertEqual(m['build']['parameters'], dict(AW=aw, P=8, CONTEXTS=1))
            self.assertEqual(p['geometry'], field.geometry(1 << aw, 8))
            self.assertEqual(len(p['generated_sha256']), 23)
            self.assertTrue(all(native.sha(files['rtl/'+name]) == pin for name, pin in p['generated_sha256'].items()))
            self.assertEqual(files[native.REFERENCE], (native.ROOT/native.REFERENCE).read_bytes())
            if aw == 16: self.assertEqual(p['generated_sha256'], native.verify()['source_sha256'])

    def test_frozen_compile_bench_delta_is_label_and_typed_control_only(self):
        for aw, f in ((8, 0), (8, 1), (8, 2), (16, 0)):
            b, _ = native.emitted_bundle(aw, f); expected, h = parent.compile_bench(b, f)
            actual, header = native.compile_bench(b, f); self.assertEqual(header, h)
            self.assertIn('ref_self_check();Counts counts;', actual)
            self.assertIn('need(unpack(d.data_out,lane)==physical->expected[reverse4(lane)*T+row]', actual)
            self.assertIn('const uint32_t wrong=physical->expected[reverse4(lane)*T+row]^1u;', actual)
            self.assertEqual(actual.count('S4_P8_WARM_NEGATIVE_ORACLE_REJECT'), 1)
            # All immutable frame/reference generation before the harness is unchanged.
            marker = 'struct Counts{'
            self.assertEqual(actual[:actual.index(marker)].replace('static bool negative_oracle=false;\n', ''),
                             expected[:expected.index(marker)])

    def test_counts_and_typed_control_mutations(self):
        for aw, f in ((8, 0), (8, 1), (8, 2), (16, 0)):
            n = 1 << aw; rows = n//8
            self.assertEqual(native.counts(aw, f), dict(cases=9, frames=9, physical_rows=9*rows,
                             physical_words=9*n, eligible_rows=7*rows, commits=7*rows, peak_owners=2))
            for negative in (False, True):
                v = native.contracts(aw, f)['negative' if negative else 'normal']; config = dict(aw=aw, field=f, negative=negative)
                native.validate(v['stdout'], v['stderr'], v['returncode'], config, {})
                for out, err, rc in ((v['stdout']+'PASS\n', v['stderr'], v['returncode']),
                                     (v['stdout'], v['stderr']+'extra\n', v['returncode']),
                                     (v['stdout'], v['stderr'], 1-v['returncode'])):
                    with self.assertRaisesRegex(ValueError, 'TYPED_OUTPUT'): native.validate(out, err, rc, config, {})

    def test_v1_AW5_rejection_and_role_limits_preserved(self):
        with self.assertRaisesRegex(ValueError, 'S4_SHARED_GEOMETRY_T_GE_P'): field.geometry(32, 8)
        for aw, f in ((5, 0), (6, 0), (16, 1), (16, 2), (8, 3), (8.0, 0), (8, True)):
            with self.assertRaisesRegex(ValueError, 'P8_WARM_ROLE'): native.contracts(aw, f)


if __name__ == '__main__': unittest.main()
