import random
import unittest

from fpga.reference.stream27_host_offload_model_v1 import profile
from fpga.reference.stream27_r15_host_link_model_v1 import DirectWrite, FixedOutput, LinkFault, Target, Word, field100_routes, raw_word_ok, encode_word, decode_word


def routes(context, index):
    # TEST FIXTURE only. Shared physical bank/port, disjoint address region:
    # peer writes still collide on the port despite nonoverlapping addresses.
    return Target(f'bank{index % 16}', 'A', context*1024 + index//16)


class Contract(unittest.TestCase):
    def begin(self, n=32):
        m = DirectWrite(n, routes)
        m.drain_ack(0)
        s, l = m.begin(0, 0x120001, profile(n, 16, 1000000, 1), core_idle=True, lease_safe=True)
        return m, s, l

    def word(self, m, s, l, i):
        return Word(s, l, 0, 0x120001, i, i)

    def test_normal_atomic_with_random_backpressure(self):
        m,s,l = self.begin(256); rng=random.Random(15); i=0
        for _ in range(30000):
            if i < m.words and m.accept(self.word(m,s,l,i)): i += 1
            if m.queue:
                target=m.tx['route'][m.queue[0].index]
                m.step(grant=(s,l,target) if rng.randrange(3) else None)
            self.assertNotIn(0,m.published)
            if m.tx['applied']==m.words: break
        self.assertEqual(m.tx['applied'],m.words)
        m.commit(session=s,lease=l,context=0,owner=0x120001,core_idle=True,profile_ok=True)
        self.assertEqual(len(m.memory),m.words)
        self.assertEqual(len(m.writes),m.words)

    def test_idle_address_does_not_free_peer_port(self):
        m,s,l=self.begin(); w=self.word(m,s,l,0);m.accept(w);t=routes(0,0)
        self.assertNotEqual(t.address,routes(1,0).address)
        self.assertIsNone(m.step(grant=(s,l,t),busy_ports={(t.bank,t.port)}))
        self.assertEqual(m.queue[0],w);self.assertFalse(m.memory)
        self.assertEqual(m.step(grant=(s,l,t)),w)

    def test_no_idle_or_no_bank_lease(self):
        for idle,safe in ((False,True),(True,False)):
            m=DirectWrite(32,routes);m.drain_ack(0)
            with self.assertRaisesRegex(LinkFault,'NO_PHYSICAL_LEASE'):
                m.begin(0,1,profile(32,16,1000000,1),core_idle=idle,lease_safe=safe)

    def test_partial_commit_and_cdc_not_ram_ack(self):
        m,s,l=self.begin();m.accept(self.word(m,s,l,0))
        with self.assertRaisesRegex(LinkFault,'PARTIAL'):
            m.commit(session=s,lease=l,context=0,owner=0x120001,core_idle=True,profile_ok=True)
        self.assertFalse(m.published)

    def test_cancel_and_stale_replay(self):
        m,s,l=self.begin();w=self.word(m,s,l,0);m.accept(w);m.cancel()
        _,new=m.begin(0,0x120001,profile(32,16,1000000,1),core_idle=True,lease_safe=True)
        self.assertNotEqual(l,new)
        with self.assertRaisesRegex(LinkFault,'STALE_AUTHORITY'):m.accept(w)
        self.assertFalse(m.memory)

    def test_reset_requires_two_domain_drain_and_new_session(self):
        m,s,l=self.begin();w=self.word(m,s,l,0);m.accept(w);m.reset()
        with self.assertRaisesRegex(LinkFault,'RESET_DRAIN'):
            m.begin(0,0x120001,profile(32,16,1000000,1),core_idle=True,lease_safe=True)
        m.drain_ack(m.session)
        m.begin(0,0x120001,profile(32,16,1000000,1),core_idle=True,lease_safe=True)
        with self.assertRaisesRegex(LinkFault,'STALE_AUTHORITY'):m.accept(w)

    def test_range_order_never_write(self):
        for index,value in ((0,1000000),(1,0),(0,-1),(0,True)):
            m,s,l=self.begin()
            with self.assertRaises(LinkFault):m.accept(Word(s,l,0,0x120001,index,value))
            self.assertFalse(m.memory)

    def test_revoked_lease_no_side_effect(self):
        m,s,l=self.begin();m.accept(self.word(m,s,l,0))
        m.step(grant=(s,l,routes(0,0)),context_still_idle=False)
        self.assertEqual(m.tx['fault'],'LEASE_REVOKED');self.assertFalse(m.memory)

    def test_alias_map_rejected(self):
        m=DirectWrite(32,lambda c,i:Target('same','A',0));m.drain_ack(0)
        with self.assertRaisesRegex(LinkFault,'ROUTE_ALIAS'):
            m.begin(0,1,profile(32,16,1000000,1),core_idle=True,lease_safe=True)

    def test_fixed_output_stall_cannot_silently_drop(self):
        o=FixedOutput(2);o.tick(10);o.tick(11)
        self.assertEqual(o.tick(12,ready=True),10)
        self.assertFalse(o.error);o.tick(13)
        self.assertTrue(o.error);self.assertEqual(list(o.queue),[11,12])

    def test_actual_shadow_context_leaves_are_disjoint(self):
        for n in (32,256,65536):
            a={field100_routes(n,0,i) for i in range(n+32)}
            b={field100_routes(n,1,i) for i in range(n+32)}
            self.assertFalse(a & b)
            self.assertEqual(len(a),n+32)

    def test_raw_boundaries_are_not_residue_planes(self):
        self.assertTrue(raw_word_ok(256,1000000,0,0xffffffff))
        self.assertFalse(raw_word_ok(256,1000000,0,0xfffffffe))
        self.assertTrue(raw_word_ok(256,1000000,256+16,896))
        self.assertFalse(raw_word_ok(256,1000000,256+16,897))

    def test_dma_records_explicit_tokens_exact_little_endian(self):
        w=Word(0x01020304,0x11223344,1,0x123456789abcde,77,0xffffffff)
        raw=encode_word(w)
        self.assertEqual(raw[4:8],bytes.fromhex('04030201'))
        self.assertEqual(decode_word(raw),w)
        for broken in (raw[:-1],raw+b'\0',raw[:-1]+b'\1',b'\xff'+raw[1:]):
            with self.assertRaises(LinkFault):decode_word(broken)


if __name__ == '__main__': unittest.main()
