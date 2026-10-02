import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fpga.reference import track_a4_post_ntt_aethia_prepare_v1 as prepare
from fpga.tools import native_source_gate_v1 as policy


class PostPreparationTests(unittest.TestCase):
    def test_frozen_ticket_and_original_sources_match(self):
        pins, ticket = prepare.pins()
        self.assertEqual(prepare.sha(prepare.ROOT/prepare.TICKET), prepare.TICKET_SHA)
        self.assertEqual(len(ticket['native_sources']),13)
        self.assertEqual(len([name for name in ticket['native_sources'] if name.endswith('.sv')]),12)
        self.assertEqual(pins[prepare.LAUNCHER], prepare.FIXED[prepare.LAUNCHER])

    def test_snapshot_only_corpus_exact_manifest_and_freshness(self):
        with tempfile.TemporaryDirectory() as name:
            output = Path(name).resolve()/'stage'; receipt = prepare.prepare(output)
            manifest = json.loads((output/'aw5-manifest.json').read_text())
            policy.check_sources(output/'snapshot/source/fpga',manifest['sources'])
            self.assertEqual(manifest['host'],'aethia'); self.assertEqual(manifest['build']['parameters'],{'AW':5})
            self.assertIn('-DA4_POST_AW=5',manifest['build']['cflags'])
            self.assertEqual(receipt['corpus']['sha256'],'e8a499238c6a52813f33262c101d981ebad1e4a9e1777e8dd2878ae286993d06')
            self.assertEqual(manifest['steps'][0]['expected_stdout'],
                'A4_POST_NTT_PASS aw=5 cases=20 post_clocks=60 field_words=1920 image_words=640\n')
            self.assertEqual((output/'snapshot/approved-manifest.json').read_bytes(),(output/'aw5-manifest.json').read_bytes())
            self.assertTrue(all(manifest['sources'][path]==digest for path,digest in receipt['imported_snapshot_sources'].items()))
            with self.assertRaisesRegex(ValueError,'fresh'):prepare.prepare(output)

    def test_wrong_ticket_and_aw_scope_rejected(self):
        with patch.object(prepare,'TICKET_SHA','0'*64):
            with self.assertRaisesRegex(ValueError,'ticket identity'):prepare.pins()
        metadata=json.loads((prepare.ROOT/prepare.TICKET).read_text())['corpora'][1]
        with self.assertRaisesRegex(ValueError,'AW5'):prepare.expected_footer(metadata)


if __name__=='__main__':unittest.main()
