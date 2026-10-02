import copy
import hashlib
import json
import re
import unittest
from unittest.mock import patch
from fpga.reference import stream27_host_chain_diet_qualification as q


class DietQualificationSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.small = {n: q.prepare(n, paired=True) for n in (32, 256)}

    def test_full_defaults_match_immutable_fitted_maps(self):
        project = q.ROOT/'artifacts/s4-p16-diet-whole-full-flow-v1/project'
        m = json.loads((project/'manifest.json').read_text())
        normal = q.ROOT/'results/throughput-20260929/s4-p16-diet-whole-full9-normal-v1/input'
        for paired in (False, True):
            b = q.prepare(paired=paired)
            pins = {name: q.fitted.sha(text) for name, text in b['files'].items()}
            expected = json.loads((normal/'manifest.json').read_text())['full_host']['generated_sha256'] if paired else m['source_sha256']
            self.assertEqual(pins, expected)
            self.assertEqual(len(b['rtl_sources']), 69 if paired else 58)
            for name, pin in m['source_sha256'].items():
                self.assertEqual(hashlib.sha256((project/'rtl'/name).read_bytes()).hexdigest(), pin)
                self.assertEqual(b['files'][name], (project/'rtl'/name).read_text())

    def test_full_drift_is_rejected_without_output(self):
        wrong = {'files': {'changed.sv': 'changed'}}
        with patch.object(q.fitted, 'prepare', return_value=wrong):
            with self.assertRaisesRegex(ValueError, 'FULL_FITTED_RTL_DRIFT'):
                q.prepare()

    def test_small_actual_serial_calendar_and_preserved_arithmetic(self):
        for n, b in self.small.items():
            g = b['geometry']
            self.assertEqual({k: g[k] for k in q.SMALL[n]}, q.SMALL[n])
            self.assertEqual(g['feedback_fifo_rows'], g['feedback_delay'])
            self.assertEqual(g['warm_interval'], g['first_digit']+1+g['feedback_delay'])
            self.assertEqual(g['next_correction_accept'], g['carry_done'])
            self.assertEqual(g['next_cache_capture']+1, g['warm_interval']+g['pointwise_accept'])
            self.assertGreater(g['warm_interval'], g['carry_done']-g['first_digit'])
            self.assertEqual(b['cycle_contract'], q.fitted.parent.cycle_contract(n, g, canonical_pipe_stages=1))
            self.assertTrue(b['diet_binding']['whole_calendar_changed'])
            self.assertFalse(b['diet_binding']['whole_resource_go'])
            for name in q.fitted.PRESERVED:
                self.assertEqual(b['files'][name], (q.ROOT/'rtl/kernel'/name).read_text())
            self.assertIn('genefer_montgomery_mul27_sparse_pipe', b['files']['genefer_crt3_27_mont_pipe.sv'])
            modules = [name for text in b['files'].values() for name in re.findall(r'\bmodule\s+(\w+)\b', text)]
            self.assertEqual(len(modules), len(set(modules)))
            self.assertEqual(len(b['files']), 69)
            for root in b['diet_binding']['new_roots']:
                self.assertIn(root+'.sv', b['files'])
                self.assertIn('CORR_SERIAL_BFS=2', b['files'][root+'.sv'])

    def test_eighteen_delay_changes_only_counted_pipeline(self):
        g = self.small[256]['geometry']
        top, actual = q.chain_source(256, 'arithmetic_child', g)
        oldtop, old = q.chain.source(256, 'arithmetic_child', dict(g, feedback_delay=4))
        self.assertEqual(top, oldtop)
        start = actual.index(' // 18 explicit accepted-edge pipeline rows:')
        end = actual.index(' for(genvar lane=0;', start)
        restored = actual[start:end].replace('18 explicit accepted-edge pipeline rows: carry output k -> field accept k+19.',
            'Four explicit accepted-edge pipeline rows: carry output k -> field accept k+5.')
        for before, after in (('[17:0]', '[3:0]'), ('[0:17]', '[0:3]'), ('[17]', '[3]'),
                              ('[16:0]', '[2:0]'), ('d<18;', 'd<4;')):
            restored = restored.replace(before, after)
        self.assertEqual(actual[:start]+restored+actual[end:], old)
        _, unchanged = q.chain_source(32, 'arithmetic_child', self.small[32]['geometry'])
        self.assertEqual(unchanged, q.chain.source(32, 'arithmetic_child', self.small[32]['geometry'])[1])

    def test_source_derived_valid_start_payload_owner_reset_trace(self):
        for n, b in self.small.items():
            text = b['files'][f'genefer_stream27_warm_chain_aw{n.bit_length()-1}_p16_v1.sv']
            depth = int(re.search(r'for\(int d=1;d<(\d+);', text).group(1))
            last = int(re.search(r'assign feedback_slot=fifo_valid\[(\d+)\]', text).group(1))
            self.assertEqual(last, depth-1)
            self.assertIn(f'logic [{last}:0] fifo_valid,fifo_start;', text)
            self.assertIn('if(!rst_n)begin fifo_valid<=0;fifo_start<=0;end', text)
            self.assertIn('else if(local_error)begin fifo_valid<=0;fifo_start<=0;end', text)
            self.assertIn("fifo_owner[0]<={digit_epoch+16'd1,digit_generation}", text)
            for gaps in (0, 1, 3):
                # A carry row appears AFTER k; it enters the FIFO at k+1.
                issues = {1+i*(gaps+1): (i, i == 0, (65535+i+1) & 65535, 7) for i in range(8)}
                state = [None]*depth
                observed = []
                for edge in range(max(issues)+depth+2):
                    if state[-1] is not None:
                        observed.append((edge, state[-1]))
                    state = [issues.get(edge)]+state[:-1]
                self.assertEqual(observed, [(edge+depth, row) for edge, row in issues.items()])
                self.assertEqual(observed[0][0], depth+1)
                self.assertEqual(sum(row[1] for _, row in observed), 1)
            # Eligibility reset/error clears all in-flight tokens in one edge.
            for cleared_at in range(depth):
                state = [None]*depth
                for edge in range(depth+3):
                    if edge == cleared_at:
                        state = [None]*depth
                    else:
                        self.assertIsNone(state[-1])
                        state = [(0, True, 0, 7) if edge == 0 and cleared_at else None]+state[:-1]

    def test_reject_unqualified_geometry_flags_and_typed_booleans(self):
        for args in ({'n':64}, {'p':8}, {'contexts':2}, {'corr_serial_bfs':0},
                     {'canonical_pipe_stages':0}, {'mont_factored':False}, {'n':True},
                     {'paired':1}, {'allow_full_constants':1}):
            with self.assertRaises(ValueError):
                q.prepare(**args)

    def test_late_cache_and_wrong_field_calendar_reject(self):
        n = 32
        b = q.fitted.parent.prepare(n, 16, canonical_pipe_stages=1)
        kwargs = dict(mode='warm_signed', contexts=1, allow_full_constants=False)
        old = [q.fitted.old_fields.prepare(n, 16, f, **kwargs) for f in range(3)]
        new = [q.fitted.fields.prepare(n, 16, f, **kwargs, corr_serial_bfs=2,
            comm_stage_shared_mlab=1, mont_factored=1) for f in range(3)]
        late = copy.deepcopy(new)
        for field in late:
            field['geometry']['next_cache_capture'] += 1
        with self.assertRaisesRegex(ValueError, 'CACHE_BEFORE_POINTWISE'):
            q.bind_small(b, old, late)
        wrong = copy.deepcopy(new)
        wrong[1]['geometry']['warm_interval'] -= 1
        with self.assertRaisesRegex(ValueError, 'THREE_FIELD_CALENDAR'):
            q.bind_small(b, old, wrong)


if __name__ == '__main__':
    unittest.main()
