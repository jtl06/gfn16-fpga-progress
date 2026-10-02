"""Runner contracts only; no RTL simulation on the local host."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import tarfile

from reference import core27_prefetch_r2_regression as gate

ROOT=Path(__file__).resolve().parents[1]

def fixture(warm=False):
    n=32;ntt,setup=gate.ntt_schedule(5);words=12*257
    data=dict(cycles=0,conversion=8,roots=0 if warm else words+5,ntt=ntt,
        crt=64,carry=100,passes=2,base=97,profile_before=int(warm),
        profile_loads=int(not warm),profile_hits=int(warm),profile_words=0 if warm else words,
        seed_setup=setup,readback=1)
    data['cycles']=sum(data[k] for k in ('conversion','roots','ntt','crt','carry'))
    line='sample '+' '.join(f'{key}={data[key]}' for key in gate.FIELDS)
    return line+'\nPASS n=32 squares=1 readbacks=1 aborts=0\n','32\nRUN sample 0\n0\n'

class FusionGateTests(unittest.TestCase):
    def test_source_closure_and_no_duplicate_modules(self):
        sources=gate.check_sources(ROOT)
        self.assertEqual(len(sources),16)
        pins=gate.source_inputs(ROOT,sources)
        for name in ('reference/core27_prefetch_r2_regression.py',
                     'reference/core27_prefetch_r2_bench.py',
                     'reference/square_core27_stream_prefetch_regression.py',
                     'rtl/tb/square_core27_stream_prefetch_r2.cpp'):
            self.assertIn(name,pins)

    def test_known_prefetch_schedule(self):
        self.assertEqual(gate.ntt_schedule(1),(74,22))
        self.assertEqual(gate.ntt_schedule(5),(246,122))
        self.assertEqual(gate.ntt_schedule(7),(653,490))
        self.assertEqual(gate.ntt_schedule(16),(20558,815))

    def test_cold_and_warm_metadata(self):
        for warm in (False,True):
            output,vectors=fixture(warm)
            rows=gate.validate_output(output,vectors,5)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['profile_before'],int(warm))

    def test_wrong_latency_profile_count_and_footer_rejected(self):
        output,vectors=fixture()
        for bad in (output.replace('conversion=8','conversion=11'),
                    output.replace('profile_loads=1','profile_loads=0'),
                    output.replace('ntt=246','ntt=245'),
                    output.replace('crt=64','crt=65'),
                    output.replace('readbacks=1','readbacks=0'),
                    output.replace('sample cycles=','wrong cycles='),
                    output.replace('PASS n=32','FAIL n=32')):
            with self.assertRaises(ValueError):gate.validate_output(bad,vectors,5)

    def test_actual_vectors_have_profile_and_conversion_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'vectors.txt';info=gate.write_vectors(path,5,20260929,True)
            rows=path.read_text().splitlines()
            self.assertEqual(sum(row.startswith(('RUN ','RUN_NOREAD ')) for row in rows),info['squares'])
            for label in ('convert-m1','convert-0','convert-p1'):
                self.assertEqual(rows.count('ABORT '+label+' 1'),2)
            for label in ('lastavailable','consumed','commit','check'):
                self.assertIn('ABORT profile-'+label+' 1',rows)
            for index in (16,31):
                self.assertIn(f'BADDIGIT_AT 1000000000 1000000000 {index}',rows)
                self.assertIn(f'BADDIGIT_AT 69 69 {index}',rows)
            self.assertEqual(info['fusion_invalid_final_row_cases'],4)
            self.assertEqual(gate.sha(path),info['sha256'])

    def test_preparation_is_source_only_and_hash_bound(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            out=Path(tmp)/'snapshot';gate.prepare(out)
            report=json.loads((out/'manifest.json').read_text())
            self.assertEqual(report['status'],'prepared_not_executed')
            self.assertEqual(gate.sha(out/'source.tar.gz'),report['archive_sha256'])
            with tarfile.open(out/'source.tar.gz') as tar:
                self.assertEqual(set(tar.getnames()),{'fpga/'+p for p in report['sources']})
                self.assertTrue(all(p.isfile() for p in tar.getmembers()))

    def test_local_rtl_execution_refused_before_output_creation(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(gate.socket,'gethostname',return_value='local-mac'):
            out=Path(tmp)/'output'
            with self.assertRaises(ValueError):gate.execute(5,out)
            self.assertFalse(out.exists())

if __name__=='__main__':unittest.main()
