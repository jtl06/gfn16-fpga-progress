"""Small bigint/source-only E2E-1 tests; no Verilator or AW16 execution."""
import copy
import unittest

from fpga.reference import core27_crtmont_prp_e2e_v1 as e


class E2EProofTests(unittest.TestCase):
    def test_all_labels_have_proofs_not_probable_prime_assertions(self):
        for base, classification, witness in e.SPEC:
            certificate = e.prove_label(base, classification, witness)
            n = base**32+1
            if classification == 'prime':
                k, s = int(certificate['odd_cofactor_hex'], 16), certificate['power_of_two']
                self.assertEqual(n-1, k*(1 << s))
                self.assertEqual(k % 2, 1)
                self.assertLess(k, 1 << s)
                self.assertEqual(pow(witness, (n-1)//2, n), n-1)
            else:
                self.assertEqual(n % certificate['factor'], 0)
                self.assertTrue(1 < certificate['factor'] < n)

    def test_false_labels_certificates_and_other_profiles_rejected(self):
        for values in ((70, 'prime', 2, 5), (96, 'prime', 4, 5), (96, 'composite', 5, 5),
                       (68, 'composite', 2, 5), (1000000001, 'composite', 2, 5), (96, 'prime', 5, 8)):
            with self.assertRaises(ValueError):
                e.prove_label(*values)

    def test_complete_exponent_schedule_matches_independent_pow(self):
        text, oracle = e.corpus()
        self.assertEqual(e.corpus(), (text, oracle))
        self.assertEqual(len(text.splitlines()), 17)
        self.assertEqual([c['base'] for c in oracle['cases']], [69,70,96,112,989233152,999999998,999999999,1000000000])
        self.assertEqual(sum(c['classification']=='prime' for c in oracle['cases']), 3)
        for case in oracle['cases']:
            bits = case['exponent_bits']; b = case['base']; exponent = b**32
            self.assertEqual(int(bits, 2), exponent)
            self.assertEqual(bits[0], '1')
            prefix, residue = 0, 1
            for bit in bits:
                prefix = 2*prefix + int(bit)
                residue = residue*residue*(1 << int(bit)) % (exponent+1)
            self.assertEqual(prefix, exponent)
            self.assertEqual(residue, pow(2, exponent, exponent+1))
            self.assertEqual(hex(residue), case['expected_residue_hex'])
        self.assertEqual(oracle['operations'], sum(c['operations'] for c in oracle['cases']))

    def test_radix_roundtrip_and_minus_one_encoding(self):
        for base in (69,96,1000000000):
            n = base**32+1
            for value in (0,1,base-1,base,n-2,n-1):
                self.assertEqual(e.decode(e.encode(value,base),base),value)
            self.assertEqual(e.encode(n-1,base),[-1]+[0]*31)
            with self.assertRaises(ValueError): e.decode([-1,1]+[0]*30,base)
            with self.assertRaises(ValueError): e.decode([base]+[0]*31,base)

    def logs(self):
        _, oracle = e.corpus(); lines=[]
        for c in oracle['cases']:
            lines.append(f"E2E_RESULT case={c['index']} base={c['base']} class={c['classification']} "
                         f"steps={c['operations']} doubles={c['doubles']} cycles={c['operations']*100} "
                         f"prp={int(c['expected_prp'])} digits="+','.join(map(str,c['expected_digits'])))
        lines.append(f"E2E_PASS aw=5 cases=8 operations={oracle['operations']} doubles={oracle['doubles']} "
                     f"readbacks=8 cycles={oracle['operations']*100}")
        return '\n'.join(lines)+'\n', lines[0]+'\n', 'E2E_RESIDUE_MISMATCH case=0 digit=0\n'

    def test_exact_residue_review_accepts_matched_fixture(self):
        result=e.review_logs(*self.logs())
        self.assertEqual(result['status'],'passed_small_aw5_prp_residues_and_comparator')
        self.assertEqual(len(result['cases']),8)

    def test_residue_negative_and_coverage_mutations_fail_review(self):
        normal,negative,stderr=self.logs()
        changed=normal.splitlines(); head,digits=changed[0].split(' digits='); values=list(map(int,digits.split(',')))
        values[0]=(values[0]+1)%69; changed[0]=head+' digits='+','.join(map(str,values))
        failures=[('\n'.join(changed)+'\n',negative,stderr),
                  (normal.replace('steps=196','steps=195',1),negative,stderr),
                  (normal.replace('cases=8','cases=7'),negative,stderr),
                  (normal,negative,''), (normal,normal,stderr),
                  (normal+'extra\n',negative,stderr), (normal,negative,stderr.replace('digit=0','digit=1'))]
        for args in failures:
            with self.assertRaises(ValueError):e.review_logs(*args)

    def test_schedule_mutations_change_composite_final_residue(self):
        _, oracle=e.corpus(); c=oracle['cases'][0]; m=c['base']**32+1; bits=c['exponent_bits']
        def run(seq):
            x=1
            for bit in seq:x=x*x*(1 << int(bit))%m
            return x
        expected=int(c['expected_residue_hex'],16)
        self.assertNotEqual(run(bits[1:]),expected)
        self.assertNotEqual(run(bits[:-1]+str(1-int(bits[-1]))),expected)
        self.assertNotEqual(run(bits[::-1]),expected)

    def test_rtl_lineage_is_exactly_the_audited_sixteen_sources(self):
        order,pins=e.parent_sources()
        self.assertEqual(len(order),16);self.assertEqual(len(pins),16)
        self.assertEqual(pins['rtl/kernel/'+e.TOP+'.sv'],'b6dbd4fccc6d7708fd295d3c82e2ebec444c4a2fbde8612851f10f979da04895')


if __name__=='__main__':unittest.main()
