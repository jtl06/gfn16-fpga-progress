"""Shared C2 API seam only: no HDL/native or resource claim."""
import hashlib
import re
import unittest

from fpga.reference import stream27_host_contexts as host
from fpga.reference import stream27_context_tagcompact_bind as tags


FLAGS = dict(corr_serial_bfs=2, mont_factored=1, cold_launch_fence=1,
             explicit_net_declarations=1)
FROZEN_FULL_ROOT = 'cb734faeef4ebe4e95d8a6924e8467253d66e686a0aaa5ec13b2c2cca8bd9e3b'


class CompactTagApiTests(unittest.TestCase):
    def test_compact_transport_is_shared_once_per_stage(self):
        text=(tags.ROOT/tags.LEAF).read_text()
        lanes=text.index(' for(genvar lane=0;lane<PAIRS;lane=lane+1)')
        self.assertEqual(text.count('.WORD_W(2)'),2)
        self.assertLess(text.index(' upper_tags\n'),lanes)
        self.assertLess(text.index(' lower_tags\n'),lanes)
        self.assertEqual(text.count('logic [GEN_W:0] owner_dictionary[0:1];'),1)
        self.assertLess(text.index('logic [GEN_W:0] owner_dictionary[0:1];'),lanes)
        self.assertNotIn('compact_',text[lanes:])

    def test_disabled_default_bundle_exact(self):
        old = host.prepare(32,16,**FLAGS)
        self.assertEqual(host.prepare(32,16,comm_tag_compact=0,**FLAGS),old)
        self.assertNotIn('context_tagcompact',old)
        self.assertEqual(tags.bind(old,0),old)

    def test_only_six_stage_consumers_change_and_reverse(self):
        for n in (32,256):
            parent = host.prepare(n,16,**FLAGS)
            bound = host.prepare(n,16,comm_tag_compact=1,**FLAGS)
            self.assertEqual(bound,tags.bind(parent))
            self.assertEqual(bound['geometry'],parent['geometry'])
            self.assertEqual(bound['parameters'],parent['parameters'])
            self.assertEqual(bound['two_context_schedule'],parent['two_context_schedule'])
            self.assertEqual(len(bound['context_tagcompact']['changed']),6)
            for name in bound['context_tagcompact']['changed']:
                self.assertTrue('_merged_ct_' in name or '_merged_gs_' in name,name)
            reverse = {
                name: re.sub(r'\b'+tags.NEW+r'\b',tags.OLD,text)
                for name,text in bound['files'].items() if name!=tags.NEW+'.sv'
            }
            reverse[tags.OLD+'.sv'] = parent['files'][tags.OLD+'.sv']
            self.assertEqual(reverse,parent['files'])
            self.assertEqual(len(bound['rtl_sources']),53)
            for name,text in bound['files'].items():
                self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),
                                 bound['generated_sha256'][name])
            self.assertEqual(bound['files'][bound['top']+'.sv'],
                             parent['files'][parent['top']+'.sv'])

    def test_full_emission_still_joins_frozen_corrected_host(self):
        parent = host.prepare(65536,16,allow_full_constants=True,**FLAGS)
        self.assertEqual(hashlib.sha256(parent['files'][parent['top']+'.sv'].encode()).hexdigest(),
                         FROZEN_FULL_ROOT)
        bound = host.prepare(65536,16,allow_full_constants=True,comm_tag_compact=1,**FLAGS)
        self.assertEqual(bound,tags.bind(parent))
        self.assertEqual(bound['geometry']['warm_interval'],8459)
        self.assertEqual(bound['context_tagcompact']['full_tuple_bits'],25)
        self.assertEqual(bound['context_tagcompact']['delay_tag_bits'],2)
        self.assertFalse(bound['context_tagcompact']['global_lease_reconstruction'])
        self.assertFalse(bound['context_tagcompact']['native_qualification_inherited'])
        self.assertEqual(bound['files'][bound['top']+'.sv'],parent['files'][parent['top']+'.sv'])

    def test_literal_flag_and_qualified_lineage_guards(self):
        for flag in (True,-1,2,'1'):
            with self.assertRaisesRegex(ValueError,'COMM_TAG_COMPACT_FLAG'):
                host.prepare(32,16,comm_tag_compact=flag,**FLAGS)
        for missing in ('corr_serial_bfs','mont_factored','cold_launch_fence',
                        'explicit_net_declarations'):
            flags=dict(FLAGS);flags[missing]=0
            with self.assertRaisesRegex(ValueError,'REQUIRES_EXPLICIT_P16_DIET'):
                host.prepare(32,16,comm_tag_compact=1,**flags)
        with self.assertRaisesRegex(ValueError,'REQUIRES_EXPLICIT_P16_DIET'):
            host.prepare(32,8,comm_tag_compact=1,**FLAGS)


if __name__=='__main__':
    unittest.main()
