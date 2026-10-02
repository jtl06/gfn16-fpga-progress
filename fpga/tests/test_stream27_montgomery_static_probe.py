import ast
import json
import re
import unittest
from fpga.reference import stream27_montgomery_static_probe as s


class StaticButterflyWrapper(unittest.TestCase):
    def test_four_independent_bindings_and_arithmetic_identity(self):
        s.verify()
        self.assertEqual(s.TEXT.count(".gs(1'b0)"),2)
        self.assertEqual(s.TEXT.count(".gs(1'b1)"),2)
        self.assertEqual(s.TEXT.count('.TAG_W(1)'),4)
        for index,name in enumerate(('normalized_ct','fused_ct','normalized_gs','fused_gs')):
            self.assertIn(name+'(',s.TEXT)
            self.assertIn(f'.in_valid(valid_q[{index}])',s.TEXT)
            self.assertIn(f'.u(u_q[{28*index}+:28])',s.TEXT)
        self.assertNotIn('input logic gs',s.TEXT)
        self.assertIn('edge+6',s.CPP_TEXT)
        self.assertIn('STATIC_NORMALIZED_BIT_EXACT',s.CPP_TEXT)
        self.assertIn('STATIC_MODE_VALUE_TAG',s.CPP_TEXT)

    def test_native_validator_module_import_closure_is_captured(self):
        for p in s.n.model.FIELDS:
            manifest,files=s.role(p)
            self.assertEqual(manifest['test_role'],'normal')
            self.assertEqual(manifest['build']['sv_sources'],[s.SV,*s.PINS])
            self.assertTrue(all(s.sha(raw)==manifest['sources'][name] for name,raw in files.items()))
            # Only module-level imports execute during worker validator loading.
            # Fit-only imports are intentionally inside their unused functions.
            for name,raw in files.items():
                if not name.endswith('.py'):continue
                for node in ast.parse(raw).body:
                    if not isinstance(node,ast.ImportFrom) or not (node.module or '').startswith('fpga.'):continue
                    module=node.module.removeprefix('fpga.').replace('.','/')
                    if module=='reference':
                        for alias in node.names:self.assertIn('reference/'+alias.name+'.py',files)
                    else:self.assertIn(module+'.py',files)
            self.assertTrue(all(re.fullmatch('[a-z][a-z0-9-]*',step['name']) for step in manifest['steps']))
            ready=manifest['rtl_readiness'];snapshot=ready['source_snapshot']
            self.assertEqual(ready['candidate_source_sha256'],s.sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()))

    def test_exact_footer_requires_both_directions_and_control_checks(self):
        for p in s.n.model.FIELDS:
            counts=s.counts(p)
            self.assertTrue(all(counts[key]>3000 for key in ('normalized_ct','fused_ct','normalized_gs','fused_gs')))
            footer=f'P5_STATIC_PASS p={p} '+' '.join(f'{k}={v}' for k,v in counts.items())+'\n'
            result=s.validate(footer,'',0,{'p':p},{})
            self.assertEqual((result['wrapper_latency'],result['butterfly_latency'],result['II']),(6,5,1))
            for bad in (footer.replace('normalized_ct=','wrong_mode='),footer.replace('cancelled=','missing_reset=')):
                with self.assertRaises(ValueError):s.validate(bad,'',0,{'p':p},{})
            with self.assertRaises(ValueError):s.validate(footer,'',1,{'p':p},{})


if __name__=='__main__':unittest.main()
