import unittest
from fpga.reference import a10_whole_geometry_gates_v1 as gates

class WholeGeometryTests(unittest.TestCase):
    def test_exact_driver_delta_and_actual_thread_probe(self):
        gates.source_guard();source=gates.bench_source()
        self.assertEqual((gates.ROOT/gates.BENCH).read_text(),source)
        self.assertIn('context.threads(1)',source)
        self.assertIn('d.threads()==1',source)
        self.assertIn('const unsigned profile_words=4',source)
        self.assertIn('expected_seed_setup=0',source)
        self.assertIn('point+2*uint64_t(lg)*((n+127)/128+9)+6',source)
        parent=(gates.ROOT/gates.PARENT).read_text()
        # Everything after tick (including bus/latched mutation, digit guards,
        # error quarantine and every ordered output comparison) remains exact.
        tail=parent[parent.index('        auto tick=[&]()'):]
        self.assertTrue(source.endswith(tail))

    def test_full_asset_parse_is_metadata_only(self):
        combined=[]
        for number,expected in [(0,(5,5,1,4)),(1,(7,5,1,6))]:
            text=(gates.ROOT/gates.VECTORS/f'segment{number}.txt').read_text()
            r=gates.corpus_metadata(text)
            self.assertEqual(tuple(r[k] for k in ('operations','readbacks','cold','warm')),expected)
            self.assertEqual(r['n'],65536);self.assertFalse(r['full_N_numeric_arithmetic_performed'])
            combined.extend(r['runs'])
        self.assertEqual(len(combined),12)
        self.assertEqual(sum(r['readback'] for r in combined),10)

    def test_small_metadata_negative_order_and_extent(self):
        digits=' '.join(['0']*32)
        valid='32\nLOAD a 97\n'+digits+'\nRUN a-s0-d0 0\n'+digits+'\nRUN_NOREAD a-s1-d1 1\n'+digits+'\n'
        r=gates.corpus_metadata(valid);self.assertEqual(r['operations'],2);self.assertEqual(r['warm'],1)
        for text in [valid.replace('RUN a-s0-d0 0','RUN a-s0-d0 2'),valid.replace(digits,digits+' 0',1),
                     '32\nRUN a 0\n'+digits+'\n',valid+'EXEC unknown\n']:
            with self.assertRaises(ValueError):gates.corpus_metadata(text)

if __name__=='__main__':unittest.main()
