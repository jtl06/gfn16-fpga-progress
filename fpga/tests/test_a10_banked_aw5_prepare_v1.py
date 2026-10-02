import gzip
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from fpga.reference import a10_banked_aw5_prepare_v1 as prep
from fpga.reference import a10_banked_engine_generate_v1 as gen

class PreparationTests(unittest.TestCase):
    def test_source_admission_and_cycle_separation(self):
        prep.source_guard()
        s=prep.symbolic_ledger(16)
        self.assertEqual(s['ntt_cycles'],17709)
        self.assertEqual(s['cold_root_phase_cycles'],9)
        self.assertEqual(20558-s['ntt_cycles'],2849)
        self.assertEqual(s['normalization_extra_pipes_three_fields'],192)
        self.assertTrue(s['no_physical_fit_clock_or_native_cycle_promotion'])

    def test_source_typed_mutants_exact_one_change(self):
        binding=gen.lookup_binding()
        files={prep.LOOKUP_SV:'\n'.join(c['source'] for c in binding['compiled'])+'\n'+binding['source'],
               'rtl/kernel/'+gen.ENGINE+'.sv':gen.engine_source()}
        for kind in ['root','normalization','form']:
            mutated,delta=prep.mutate(kind,files)
            self.assertEqual(sum(mutated[k]!=v for k,v in files.items()),1)
            self.assertEqual(mutated[delta['file']],gen.once(files[delta['file']],delta['before'],delta['after']))
            self.assertNotEqual(delta['before'],delta['after'])
        with self.assertRaisesRegex(ValueError,'A10_MUTANT_KIND'):prep.mutate('bad',files)
        self.assertEqual(prep.predict_typed_negative('root'),'A10_NUMERIC_ROOT_MISMATCH phase=forward index=0\n')
        self.assertEqual(prep.predict_typed_negative('form'),'A10_NUMERIC_FORM_MISMATCH phase=forward index=1\n')
        self.assertEqual(prep.predict_typed_negative('normalization'),'A10_NUMERIC_NORMALIZATION_MISMATCH phase=inverse index=0\n')

    def test_packet_archive_manifest_closure(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'fresh';r=prep.prepare(out)
            self.assertEqual(len(r['packets']),7)
            self.assertFalse(r['HDL_or_native_performed']);self.assertFalse(r['promotion_allowed'])
            for packet in r['packets']:
                case=out/packet['case'];source=case/'source/fpga'
                m=json.loads((case/'manifest.json').read_text())
                self.assertEqual(prep.sha(case/'manifest.json'),packet['manifest_sha256'])
                self.assertEqual(prep.sha(case/'source.tar.gz'),packet['archive_sha256'])
                self.assertEqual(set(m['sources']),{str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()})
                with tarfile.open(case/'source.tar.gz','r:gz') as tar:
                    self.assertEqual({x.name for x in tar.getmembers()},{'fpga/'+x for x in m['sources']})
                    for x in tar.getmembers():
                        self.assertTrue(x.isfile());self.assertEqual(x.mode,0o644)
                        self.assertEqual(hashlib.sha256(tar.extractfile(x).read()).hexdigest(),m['sources'][x.name[5:]])
                self.assertTrue(set(m['build']['sv_sources']).issubset(m['sources']))
                self.assertNotIn('rtl/kernel/genefer_root_recurrence27.sv',m['build']['sv_sources'])
                self.assertIn('-Werror=return-type',m['build']['cflags'])
                self.assertIn('tools/native_source_gate_v1.py',m['sources'])
            with self.assertRaisesRegex(ValueError,'A10_FRESH_OUTPUT_ONLY'):prep.prepare(out)

    def test_no_host_shape_profile_misuse(self):
        m=prep.native_manifest('engine-f0',{'tools/native_source_gate_v1.py':'0'*64})
        self.assertEqual(m['host'],'aethia');self.assertNotIn('aws',m['source_root'])
        self.assertEqual(m['profile']['format'],3)
        self.assertEqual(m['profile']['input_domain'],'ordinary/R^0')
        self.assertEqual(m['profile']['output_domain'],'ordinary/R^0')
        self.assertIn('after centered CRT',m['profile']['integer_doubling'])

if __name__=='__main__':unittest.main()
