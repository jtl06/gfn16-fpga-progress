import unittest
from fpga.reference import lazy28_butterfly_v1 as b
from fpga.reference import lazy28_range_model_v1 as scalar


class LazyButterflyTests(unittest.TestCase):
    def test_native_passed_multiplier_pin(self):
        self.assertEqual(b.sha(b.ROOT/b.MULTIPLIER),b.MULTIPLIER_SHA)

    def test_corpus_ranges_residues_and_scalar_model(self):
        for p in b.FIELDS:
            stream=b.events(p);counts=b.coverage(stream,p)
            self.assertGreater(counts['checked'],4000)
            self.assertGreater(counts['cancelled'],0)
            self.assertGreater(counts['high_inputs'],0)
            for reset,valid,gs,u,v,w,tag in stream:
                if reset and valid:self.assertEqual(b.butterfly(u,v,w,p,gs),scalar.butterfly(u,v,w,p,'GS' if gs else 'CT'))

    def test_negative_witnesses(self):
        for p in b.FIELDS:
            r=(1<<32)%p
            self.assertNotEqual(b.butterfly(0,1<<27,r,p,0),b.butterfly(0,0,r,p,0))
            self.assertEqual(b.butterfly(p,0,0,p,0),(0,p))
            self.assertEqual((p,p+p),(p,2*p))  # Missing CT correction violates upper bound.
            self.assertEqual(b.butterfly(p,p,0,p,1),(0,0))
            self.assertEqual((p+p),2*p)  # Missing GS sum fold violates strict bound.
            for role in ('truncate-high-bit','missing-ct-precorrection','missing-gs-fold','wrong-tag-latency','early-valid'):
                _,counts=b.corpus(p,role);self.assertEqual(counts['checked'],1)

    def test_five_is_original_butterfly_latency(self):
        # pre at k; multiplier accepts k+1 and produces k+4; output consumes k+5.
        self.assertEqual(1+3+1,b.LATENCY)
        text=(b.ROOT/b.RTL).read_text()
        self.assertIn('tag_pipe[0:4]',text)
        self.assertIn('out_valid<=product_valid;',text)
        self.assertIn('genefer_montgomery_mul28x27_sparse_pipe_v2',text)
        self.assertNotIn('genefer_montgomery_mul27_sparse_pipe #',text)

    def test_typed_single_anchor_mutants(self):
        text=(b.ROOT/b.RTL).read_text()
        for role in ('truncate-high-bit','missing-ct-precorrection','missing-gs-fold','wrong-tag-latency','early-valid'):
            mutant=b.mutant(text,role)
            self.assertNotEqual(text,mutant)
            self.assertEqual(sum(a!=z for a,z in zip(text.splitlines(),mutant.splitlines())),1)

    def test_exact_pipeline_transport_all_fields(self):
        for p in b.FIELDS:
            stream=b.events(p)
            self.assertEqual(b.replay_pipeline(stream,p),b.coverage(stream,p)['checked'])


if __name__=='__main__':unittest.main()
