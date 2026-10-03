import copy
import json
import unittest

from fpga.host.r15_genefer_pl_output import validate, COMMIT
from fpga.host.r15_genefer_pl_recipe import recipe


class Output(unittest.TestCase):
    def good(self):
        return dict(schema='r15-pinned-genefer-pl-gl-oracle-v1', status='software_interop_equal',
            upstream_commit=COMMIT, upstream_PL_GL_methods_executed=True,
            synthetic_GMP_transform=True, real_genefer_transform=False,
            full_N_PRP=False, board=False, BOINC_server=False, promotion=False,
            build_stderr='', rows=[dict(base=base, n=32, depth=3, bytes=556,
                proof_sha256='a'*64, pkey=1, upstream_GL_bad_result_rejected=True)
                for base in (10, 599, 600)])

    def text(self, value):
        return 'R15_PL_RESULT ' + json.dumps(value)

    def test_strict_scope_and_cases(self):
        good = self.good()
        self.assertEqual(validate(self.text(good)), good)
        mutations = []
        for key in ('board', 'promotion', 'full_N_PRP', 'real_genefer_transform'):
            bad = copy.deepcopy(good);bad[key] = True;mutations.append(bad)
        bad = copy.deepcopy(good);bad['rows'].pop();mutations.append(bad)
        bad = copy.deepcopy(good);bad['rows'][0]['bytes'] = 555;mutations.append(bad)
        bad = copy.deepcopy(good);bad['rows'][1]['upstream_GL_bad_result_rejected'] = False;mutations.append(bad)
        bad = copy.deepcopy(good);bad['rows'][2]['pkey'] = True;mutations.append(bad)
        for bad in mutations:
            with self.assertRaises(ValueError):
                validate(self.text(bad))
        with self.assertRaises(ValueError):
            validate(self.text(good)+'\n'+self.text(good))

    def test_closure_is_source_only_and_finite(self):
        value = recipe()
        self.assertEqual(len(value['source_sha256']), 19)
        self.assertEqual(value['max_command_seconds'], 105)
        self.assertIn('--work', value['argv'])
        self.assertFalse(value['scope']['HDL'])


if __name__ == '__main__':
    unittest.main()
