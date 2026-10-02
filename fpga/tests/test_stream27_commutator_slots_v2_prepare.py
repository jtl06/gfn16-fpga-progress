import unittest
from fpga.reference.stream27_commutator_slots_v2_vectors import corpus
from fpga.reference.stream27_commutator_slots_v2_prepare import negative_signatures


class SlotsV2Corpus(unittest.TestCase):
    def test_independent_frame_corpus_and_typed_mutations(self):
        text,metadata=corpus()
        self.assertEqual(metadata['sha256'],'26aef76de482198d80538850cc1142e8f82be64f43d7f06c39b3a086e9bb4b71')
        self.assertEqual(len(metadata['cases']),281)
        self.assertEqual(metadata['events'],35192)
        self.assertEqual(metadata['before_checks'],2*metadata['events'])
        self.assertGreater(metadata['slots'],metadata['commits'])
        negatives=negative_signatures(text)
        self.assertEqual(negatives['filtered_link'],'SLOTS_FLAG_MISMATCH tick=36 port=0\n')
        self.assertEqual(negatives['stale_commit'],'SLOTS_COMMIT_FLAG_MISMATCH tick=347 port=11\n')


if __name__=='__main__':unittest.main()
