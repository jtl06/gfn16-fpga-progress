import importlib.util
import re
import unittest
from fpga.reference import stream27_context_lean_prp_native as parent
from fpga.reference import stream27_context_lean_watchdog_prp_native as recipe


class SamePrpSuccessor(unittest.TestCase):
    def test_same_prp_cpp_and_arrays_one_root_only(self):
        before,bf,bb=parent.role('lean')
        after,af,ab,identifier=recipe.role('normal')
        self.assertEqual(len(ab['files']),58)
        self.assertEqual(bf[parent.CPP],af[parent.CPP])
        asset='reference-assets/r10-healthy-prp-n256.json'
        self.assertEqual(bf[asset],af[asset])
        self.assertEqual(before['build']['parameters'],after['build']['parameters'])
        self.assertEqual(bb['geometry'],ab['geometry'])
        self.assertEqual(before['steps'][0]['validator'],after['steps'][0]['validator'])
        self.assertEqual(identifier,'s4-p16-c2-r10-lean-watchdog-prp-normal-q1-v1')
        self.assertEqual(after['test_role'],'normal')

    def test_passive_failed_parent_and_exact_localization_contract(self):
        manifest,files,bundle,identifier=recipe.role('diagnostic')
        old=parent.role('lean')[2]
        self.assertEqual(len(bundle['files']),59)
        for name,text in old['files'].items():self.assertEqual(bundle['files'][name],text)
        observer=bundle['files'][bundle['top']+'.sv']
        self.assertNotIn('always',observer)
        self.assertIsNone(re.search(r'\b(initial|always|always_ff|always_comb)\b',observer))
        self.assertNotIn('force ',observer)
        self.assertIn('candidate.lean_watchdog_error',observer)
        for parameter in manifest['build']['parameters']:self.assertIn('.'+parameter+'('+parameter+')',observer)
        text=files[recipe.CPP].decode()
        self.assertLess(text.index('gfn16_runtime::configure(context,argc,argv)'),text.index('DUT d(&context)'))
        witness='A_PRP_WATCHDOG_DIAG age=20805 watchdog=1 local=0 counter=20479 limit=20480 completed0=96 completed1=95 started0=97 started1=96\n'
        value=recipe.validate(parent.LABELS['lean']+'\n',witness,1,{'mode':'passive-old-watchdog'},{})
        self.assertEqual(value['measurements']['local_error'],0)
        self.assertFalse(value['promotion_allowed'])
        for bad in (witness.replace('watchdog=1','watchdog=0'),witness.replace('local=0','local=1'),witness.replace('completed0=96','completed0=0')):
            with self.assertRaises(ValueError):recipe.validate(parent.LABELS['lean']+'\n',bad,1,{'mode':'passive-old-watchdog'},{})
        spec=importlib.util.spec_from_file_location('standalone_native_validator',recipe.ROOT/recipe.SELF)
        standalone=importlib.util.module_from_spec(spec);spec.loader.exec_module(standalone)
        self.assertEqual(standalone.validate(parent.LABELS['lean']+'\n',witness,1,{'mode':'passive-old-watchdog'},{}),value)


if __name__=='__main__':unittest.main()
