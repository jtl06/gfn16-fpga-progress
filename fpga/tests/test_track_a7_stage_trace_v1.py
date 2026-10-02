"""Small geometry/event and source-only harness tests; no numeric NTT or HDL."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from fpga.reference import track_a7_stage_trace_v1 as a
from fpga.reference import track_a7_trace_prepare_v1 as p


def events(n=256):
    result=[];edge=10;aw=n.bit_length()-1;count=max(1,n//128)
    for run in (1,2):
        for phase in (1,3):
            for stage in (range(aw-1,-1,-1) if phase==1 else range(aw)):
                for group in range(count):
                    rows=a.stage_rows(n,stage,group)
                    for kind,delay in (('R',0),('W',7)):
                        result.append(dict(kind=kind,edge=edge+group+delay,run=run,phase=phase,
                                           stage=stage,group=group if kind=='R' else -1,rows=rows))
                edge+=count+10
    return sorted(result,key=lambda e:(e['edge'],e['kind']))


class A7Trace(unittest.TestCase):
    def test_small_geometry_complete_bank_rows_and_stage_orders(self):
        for n in (32,64,128,256):
            es=events(n);report=a.analyze(n,es)
            self.assertEqual(len(report['transitions']),4*(n.bit_length()-2))
            self.assertFalse(report['threshold_met'])
            self.assertEqual({a.check_stage(n,[e for e in es if (e['run'],e['phase'],e['stage'])==(1,1,s)])[3]
                             for s in range(n.bit_length()-1)},{7})
        with self.assertRaisesRegex(ValueError,'SMALL_GEOMETRY_ONLY'):a.stage_rows(65536,15,0)

    def test_strict_same_edge_hazard_and_missing_interlock_witness(self):
        es=events();prior=a.check_stage(256,[e for e in es if (e['run'],e['phase'],e['stage'])==(1,1,7)])
        current=a.check_stage(256,[e for e in es if (e['run'],e['phase'],e['stage'])==(1,1,6)])
        start,witness=a.earliest(prior,current,[0,1])
        self.assertIsNotNone(witness)
        self.assertEqual(start+witness['next_issue_offset'],witness['prior_write']+1)
        bad=a.missing_interlock_witness()
        self.assertEqual(bad['kind'],'A7_MISSING_INTERLOCK_RAW')
        self.assertLessEqual(bad['read_edge'],bad['required_after'])
        self.assertEqual((bad['from_stage'],bad['to_stage']),(7,6))

    def test_trace_coverage_and_native_footer_fail_closed(self):
        es=events();lines=['A7_HEADER 256']
        for e in es:
            fields=[e['kind'],e['edge'],e['run'],e['phase'],e['stage'],e['group'],sum(x>=0 for x in e['rows']),*e['rows']]
            lines.append('A7 '+' '.join(map(str,fields)))
        lines+=['PASS n=256 squares=2 readbacks=2 aborts=0',f'A7_TRACE_PASS n=256 runs=2 records={len(es)}']
        n,decoded=a.parse('\n'.join(lines));self.assertEqual(n,256);self.assertEqual(decoded,es)
        with self.assertRaisesRegex(ValueError,'COMPLETE_NATIVE_TRACE'):a.parse('\n'.join(lines[:-1]))
        with self.assertRaisesRegex(ValueError,'STAGE_ACCESS_COUNT'):a.analyze(256,es[:-1])
        bad=[dict(e) for e in es];bad[0]['rows']=(99,)+bad[0]['rows'][1:]
        with self.assertRaisesRegex(ValueError,'ROW_RANGE'):a.analyze(256,bad)

    def test_source_wrapper_and_bench_only_add_observation(self):
        root=Path(__file__).resolve().parents[1]
        core=(root/('rtl/kernel/'+p.PARENT+'.sv')).read_text()
        sv=p.wrapper(core);self.assertIn(p.PARENT+' #(.AW(AW),.NTT_LANES(NTT_LANES)) core (.*);',sv)
        self.assertEqual(sv.count('.data_re['),384);self.assertEqual(sv.count('.data_wa['),384)
        original=(root/p.OLD_BENCH).read_text();thread=(root/p.THREAD_BENCH).read_text()
        body,cpp=p.bench(original,thread)
        for guard in ('square mismatch','phase cycle accounting mismatch','prefetch NTT counter mismatch',
                      'backpressure reservation mismatch','profile contract mismatch'):
            self.assertIn(guard,body)
        self.assertIn('A7_FIELD_PHYSICAL_SKEW',body)
        self.assertLess(body.index('const unsigned st=d.trace_state'),body.index('d.clk=1;d.eval();++a7_edge;'))
        self.assertIn('threads(requested)',cpp)

    def test_archived_subset_is_only_two_original_runs(self):
        root=Path(__file__).resolve().parents[1]
        for aw in (5,16):
            text,lineage=p.select_vectors(root,aw)
            self.assertEqual(len(text.splitlines()),7)
            self.assertEqual(len(lineage['labels']),2)
            self.assertEqual(len(lineage['metrics']),2)
            native='\n'.join(m['case']+' '+' '.join(f'{k}={m[k]}' for k in
                ('cycles','conversion','roots','ntt','crt','carry','passes','base','profile_before',
                 'profile_loads','profile_hits','profile_words','seed_setup','readback')) for m in lineage['metrics'])
            self.assertTrue(a.verify_native_metrics(native,lineage))
            with self.assertRaisesRegex(ValueError,'COUNTER_MISMATCH'):
                a.verify_native_metrics(native.replace('cycles=','cycles=9',1),lineage)


if __name__=='__main__':unittest.main()
