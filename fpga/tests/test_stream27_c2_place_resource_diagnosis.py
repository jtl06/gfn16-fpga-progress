"""Pure report/parser checks; no HDL or numerical full-N execution."""
import importlib.util
from pathlib import Path
import unittest
from decimal import Decimal as D

PATH=Path(__file__).resolve().parents[1]/'reference/stream27_c2_place_resource_diagnosis.py'
spec=importlib.util.spec_from_file_location('c2_place_diagnosis',PATH)
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)


def row(path,entity,inc,exc,regs,bits,m20k,dsp):
    cells=['node',f'{inc} ({exc})',f'{inc} ({exc})','0 (0)','0 (0)',
           '0 (0)','0 (0)',f'{regs[0]} ({regs[1]})','0',str(bits),str(m20k),
           str(dsp),str(dsp),'0','0','0','0',path,entity,'work']
    return '; '+' ; '.join(cells)+' ;'


class DiagnosisTests(unittest.TestCase):
    def fixture(self):
        return '\n'.join(['; Compilation Hierarchy Node ;']+
            [row('|','top',10,1,(5,1),100,2,1),
             row('a','ramwrapper',9,9,(4,4),100,2,1)])

    def test_inclusive_exclusive_and_memory_not_double_counted(self):
        n=d.parse(self.fixture())
        self.assertEqual(n['|']['inclusive']['needed_alms'],D(10))
        self.assertEqual(n['|']['exclusive']['needed_alms'],D(1))
        self.assertEqual(sum(x['exclusive']['block_bits'] for x in n.values()),D(100))
        self.assertEqual(sum(x['exclusive']['m20k'] for x in n.values()),D(2))
        self.assertEqual(sum(x['exclusive']['physical_dsp'] for x in n.values()),D(1))

    def test_duplicate_and_missing_parent_rejected(self):
        with self.assertRaisesRegex(ValueError,'UNIQUE_NODE'):
            d.parse(self.fixture()+'\n'+row('a','repeat',0,0,(0,0),0,0,0))
        with self.assertRaisesRegex(ValueError,'EXACT_PARENT'):
            d.parse(self.fixture()+'\n'+row('absent|leaf','leaf',0,0,(0,0),0,0,0))

    def test_negative_physical_memory_rejected(self):
        with self.assertRaisesRegex(ValueError,'NONNEGATIVE_MEMORY_DSP'):
            d.parse(self.fixture().replace('(4) ; 0 ; 100 ; 2', '(4) ; 0 ; 200 ; 2'))

    def test_boundary_embedded_digit_classification(self):
        text='\n'.join(['; Compilation Hierarchy Node ;',
            row('|','top',0,0,(0,0),0,0,0),
            row('front','genefer_stream27_signed_boundary_reduce27_pipe',0,0,(0,0),0,0,0),
            row('front|magnitude_path','genefer_digit_reduce27_pipe',0,0,(0,0),0,0,0)])
        n=d.parse(text)
        self.assertEqual(d.category(n['front|magnitude_path'],n),
                         'field_boundary_reducers_including_magnitude_path')

    def test_actual_hash_disjoint_closure_and_front_population(self):
        a=d.analyze();h=a['hierarchy']
        self.assertEqual(a['report_sha256'],d.REPORT_PIN)
        for k in ('registers','m20k','block_bits','physical_dsp'):
            self.assertEqual(h['root_minus_exclusive_sum'][k],0)
            self.assertEqual(sum(r['metrics'][k] for r in h['disjoint_categories']),h['root'][k])
        self.assertEqual(h['root_minus_exclusive_sum']['needed_alms'],D('341.9'))
        self.assertEqual(h['front_reducer_evidence']['actual_outer_lanes'],48)
        self.assertEqual(h['front_reducer_evidence']['actual_boundary_lanes'],48)
        cats={x['category']:x['metrics'] for x in h['disjoint_categories']}
        self.assertEqual(cats['field_root_ROM_and_prefetch']['m20k'],717)
        self.assertEqual(cats['field_commutator_data_storage']['m20k'],936)
        self.assertEqual(cats['field_factored_Montgomery_core']['registers'],168270)
        self.assertEqual(cats['field_lazy_butterfly_shell_payload_and_tags']['registers'],175176)
        self.assertEqual(len(a['unowned_recommendations']),1)
        self.assertFalse(a['contextual_same_stage_comparison']['causal_delta_allowed'])


if __name__=='__main__':unittest.main()
