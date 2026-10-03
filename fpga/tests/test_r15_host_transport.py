import unittest
from xml.etree import ElementTree as ET

from fpga.host.r15_arithmetic import HostFault
from fpga.host.r15_transport import (MockBar, VfioPlan, DirectColdClient, DescriptorStream,
                                    anonymous_platform_xml, cold_words)
from fpga.reference.stream27_host_offload_model_v1 import profile
from fpga.reference.stream27_r15_host_link_model_v1 import DirectWrite, field100_routes, Word, LinkFault


class R15HostTransport(unittest.TestCase):
    def endpoint(self):
        m = DirectWrite(32, lambda context, index: field100_routes(32, context, index))
        m.drain_ack(0)
        return m

    def test_cold_raw32_exact_not_residue_planes(self):
        words = cold_words(32, 1000000, [-1]+[0]*31, [-1]*16, [448]*16)
        self.assertEqual(len(words), 64)
        self.assertEqual(words[0], 0xffffffff)
        with self.assertRaises(HostFault):
            cold_words(32, 1000000, [1000000]*32, [0]*16, [0]*16)
        with self.assertRaises(HostFault):
            cold_words(32, 1000000, [0]*32, [0]*16, [449]*16)

    def test_direct_load_backpressure_peer_and_atomic_commit(self):
        m = self.endpoint()
        peer = ('published-peer',)
        m.published[1] = peer
        client = DirectColdClient(m, enabled=True)
        words = cold_words(32, 1000000, list(range(32)), [0]*16, [0]*16)
        def grants(edge, s, lease, target):
            self.assertNotIn(0, m.published)
            return ((s, lease, target) if edge % 3 else None, frozenset())
        result = client.load(0, 1, profile(32, 16, 1000000, 1), words,
                             grant=grants, idle=lambda:True, lease_safe=True)
        self.assertEqual(result[0], 1)
        self.assertEqual(m.published[1], peer)
        self.assertEqual(len(m.writes), 64)
        self.assertTrue(all('contexts[0]' in target.bank or 'context[0]' in target.bank
                            for _, target in m.writes))

    def test_partial_abort_no_payload_rollback_or_publication(self):
        m = self.endpoint(); client = DirectColdClient(m, enabled=True)
        words = cold_words(32, 1000000, [3]*32, [0]*16, [0]*16)
        def grant(edge, session, lease, target):
            return ((session, lease, target) if edge < 2 else None, frozenset())
        with self.assertRaisesRegex(HostFault, 'TIMEOUT'):
            client.load(0, 1, profile(32, 16, 1000000, 1), words,
                        grant=grant, idle=lambda:True, lease_safe=True, maximum_edges=5)
        self.assertEqual(len(m.memory), 2)
        self.assertNotIn(0, m.published)
        self.assertIsNone(m.tx)

    def test_stale_reset_tokens_never_write(self):
        m=self.endpoint()
        s, lease=m.begin(0, 1, profile(32, 16, 1000000, 1), core_idle=True, lease_safe=True)
        old=Word(s, lease, 0, 1, 0, 2)
        m.reset(); m.drain_ack(m.session)
        m.begin(0, 1, profile(32, 16, 1000000, 1), core_idle=True, lease_safe=True)
        with self.assertRaisesRegex(LinkFault, 'STALE'):
            m.accept(old)
        self.assertFalse(m.memory)

    def test_descriptor_backpressure_not_active_stall(self):
        q=DescriptorStream(1, enabled=True)
        self.assertIsNone(q.launch(1, due=False))
        self.assertTrue(q.push(1, 0, False))
        self.assertFalse(q.push(1, 1, True))
        self.assertEqual(q.launch(1, due=True), (1, 0, False))
        with self.assertRaisesRegex(HostFault, 'UNDERFLOW'):
            q.launch(1, due=True)
        with self.assertRaises(HostFault):
            q.push(1, 1, True)

    def test_vfio_is_inert_and_mmio_is_bounds_checked(self):
        plan=VfioPlan('0000:01:00.0', 1, 0, 4096)
        with self.assertRaisesRegex(HostFault, 'OFF'):plan.requests()
        self.assertIn('GROUP_GET_STATUS_VIABLE', plan.requests(enabled=True))
        with self.assertRaisesRegex(HostFault, 'UNIMPLEMENTED'):plan.execute()
        bar=MockBar(); bar.write32(4, 0x12345678)
        self.assertEqual(bar.read32(4), 0x12345678)
        for offset in (-4, 1, 4096):
            with self.assertRaises(HostFault):bar.read32(offset)

    def test_boinc_scaffold_no_project_or_process_operations(self):
        with self.assertRaisesRegex(HostFault, 'OFF'):
            anonymous_platform_xml('fixture', 1, 'worker')
        root=ET.fromstring(anonymous_platform_xml('fixture', 1, 'worker', enabled=True))
        self.assertEqual(root.findtext('app_version/app_name'), 'fixture')
        self.assertIsNotNone(root.find('file_info/executable'))
        with self.assertRaises(HostFault):
            anonymous_platform_xml('fixture', 1, '../worker', enabled=True)


if __name__ == '__main__':unittest.main()
