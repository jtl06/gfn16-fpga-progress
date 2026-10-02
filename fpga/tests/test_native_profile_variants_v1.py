import copy
import json
from pathlib import Path
import unittest
from fpga.tools import native_profile_variants_v1 as v


class VariantTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'artifacts'
        self.pair=[json.loads((root/name/'manifest.json').read_text()) for name in
          ('stream27-p16c-aw6-zero-square-v1','stream27-p16c-aw6-zero-square23-v1')]
    def test_actual_closed_static_pair(self):self.assertTrue(v.match_variants(self.pair)['one_logical_claim_required'])
    def test_only_exact_framework_difference_allowed(self):
        changed=copy.deepcopy(self.pair)
        changed[1]['sources']['tools/native_class_package_v2.py']=v.KNOWN_CONTROLS['tools/native_class_package_v2.py']
        v.match_variants(changed)
        changed[1]['sources']['tools/native_class_package_v2.py']='f'*64
        with self.assertRaises(ValueError):v.match_variants(changed)
    def test_arithmetic_case_and_oracle_changes_reject(self):
        for kind in ('source','build','step','probe'):
            changed=copy.deepcopy(self.pair)
            if kind=='source':changed[1]['sources'][changed[1]['build']['sv_sources'][0]]='a'*64
            elif kind=='build':changed[1]['build']['parameters']['AW']=7
            elif kind=='step':changed[1]['steps'][0]['expected_returncode']=0 if changed[1]['steps'][0].get('expected_returncode',0)!=0 else 1
            else:changed[1]['probe']['expected_json']['context_threads']=2
            with self.assertRaises(ValueError):v.match_variants(changed)
    def test_same_profile_and_missing_closure_reject(self):
        changed=copy.deepcopy(self.pair);changed[1]['cpu_profile']=changed[0]['cpu_profile']
        with self.assertRaises(ValueError):v.match_variants(changed)
        changed=copy.deepcopy(self.pair);del changed[1]['sources'][changed[1]['build']['cpp_source']]
        with self.assertRaises(ValueError):v.match_variants(changed)
    def test_compiled_control_is_never_ignored(self):
        changed=copy.deepcopy(self.pair[0]);name='tools/native_class_package_v1.py'
        changed['build']['cpp_source']=name
        result=v.functional_fingerprint(changed)
        self.assertIn(name,result['identity']['sources']);self.assertNotIn(name,result['ignored_exact_controls'])


if __name__=='__main__':unittest.main()
