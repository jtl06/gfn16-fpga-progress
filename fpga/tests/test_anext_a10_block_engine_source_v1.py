import unittest
from fpga.reference import anext_a10_block_engine_source_v1 as source
from fpga.reference import track_a4_blockroute_model_v1 as route


class AnextBlockEngineTests(unittest.TestCase):
    def test_source_guard(self):
        wanted=source.expected()
        self.assertEqual((source.ROOT/source.TARGET).read_text(),wanted)
        self.assertFalse(source.verify()['native_qualified'])
        parent=(source.ROOT/source.PARENT).read_text()
        # All arithmetic, root delivery, stage order and work-counter source
        # remains exact; changes occur only at host/profile admission boundaries.
        for first,last in [('    function automatic logic [KW-1:0] bank_of',
                            '    for(genvar bank=0;bank<BANKS;bank=bank+1)begin: memories'),
                           ('            pairing_d<=pairing;', '                IDLE:if(start)begin'),
                           ('                    else begin\n                        n<=32', '    // synthesis translate_off\n    initial begin')]:
            self.assertEqual(parent.split(first,1)[1].split(last,1)[0],wanted.split(first,1)[1].split(last,1)[0])
        self.assertIn('block_request || block_read_valid || block_error',wanted)
        self.assertIn('if(state!=IDLE || start || block_request ||',wanted)
        self.assertNotIn('profile_format!=8\'d2',wanted)

    def test_atomic_conflicts_and_canonical_mask(self):
        base=dict(aw=8,p=104857601,size_log2=8,read_en=True,write_en=True,
                  read_offset=0,write_offset=1,words=tuple(range(16)))
        self.assertEqual(source.block_legal(**base),dict(error=0,read_accept=True,write_accept=True))
        for fault in [dict(state='BF_READ'),dict(start=True),dict(external_conflict=True),
            dict(scalar_request=True),dict(vector_request=True),dict(profile_request=True),
            dict(profile_loading=True),dict(profile_error=True),dict(size_log2=7),
            dict(read_offset=16),dict(write_offset=16),dict(write_offset=0),
            dict(words=(104857601,)+(0,)*15)]:
            self.assertEqual(source.block_legal(**(base|fault)),dict(error=1,read_accept=False,write_accept=False))
        self.assertEqual(source.block_legal(**(base|dict(write_offset=0,read_mask=0x5555,write_mask=0xaaaa)))['error'],0)
        self.assertEqual(source.block_legal(**(base|dict(words=(0xffffffff,)+(0,)*15,write_mask=0xfffe)))['error'],0)
        self.assertEqual(source.block_legal(**(base|dict(rst=False,state='BF_READ'))),dict(error=0,read_accept=False,write_accept=False))

    def test_small_geometry_independent_mapping_and_edge(self):
        for aw in (5,8):
            n,t=route.geometry(aw);memory=route.Memory(aw)
            for offset in range(t):
                words=tuple(lane*t+offset for lane in range(16))
                accept=source.block_legal(aw=aw,p=104857601,size_log2=aw,write_en=True,
                    write_offset=offset,words=words)
                out=memory.edge(enable=accept['write_accept'],write_en=True,write_offset=offset,write_words=words)
                self.assertFalse(out['error'])
            for offset in range(t):
                out=memory.edge(read_en=True,read_offset=offset)
                self.assertTrue(out['read_valid'])
                self.assertEqual(out['read_offset'],offset)
                self.assertEqual(out['read_words'],tuple(lane*t+offset for lane in range(16)))
            self.assertEqual(len(memory.words),n)
            # No extra hidden response stage: descriptor and synchronous RAM q
            # are observable after E0; the caller captures them on E1.
            self.assertEqual(out['read_mask'],65535)


if __name__=='__main__':unittest.main()
