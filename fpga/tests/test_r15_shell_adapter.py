from dataclasses import replace
import unittest

from fpga.host.r15_arithmetic import HostFault
from fpga.host.r15_image_codec import ExportWord, CANONICAL_A, encode_signed96
from fpga.host.r15_shell_adapter import (CommittedRecord, ShellSnapshot, OwnedCanonicalWord,
    start_writes, FencedCanonicalExport)
from fpga.reference.stream27_r15_host_mmio_v1 import header, REG
from fpga.reference.stream27_r15_shell_mmio_v1 import STATUS_BITS


def flags(*names):
    return sum(1 << STATUS_BITS[name] for name in names)


class ShellAdapter(unittest.TestCase):
    def records(self):
        return (CommittedRecord(7, 3, header(256, 0, 599, 4, 3, 0,
                   core_next_epoch=65534, core_job_generation=0)),
                CommittedRecord(7, 4, header(256, 1, 600, 8, 7, 0,
                   core_next_epoch=2, core_job_generation=0)))

    def start_snapshot(self):
        return ShellSnapshot(7, 4, flags('LINK_READY', 'IDLE0', 'IDLE1', 'LOADED0', 'LOADED1'),
                             0, self.records(), True)

    def final_snapshot(self):
        # loaded is consumed by START; retained job record still owns export.
        return replace(self.start_snapshot(), status=flags('LINK_READY', 'IDLE0',
                       'IDLE1', 'CANONICAL0', 'CANONICAL1'))

    def test_start_latest_global_lease_and_joint_different_headers(self):
        snapshot = self.start_snapshot()
        writes = dict(start_writes(snapshot, self.records(), enabled=True))
        self.assertEqual(writes[REG['TOKEN_LEASE']], 4)
        self.assertNotEqual(writes[REG['TOKEN_LEASE']], self.records()[0].lease)
        self.assertEqual(writes[REG['START_MASK']], 3)
        with self.assertRaisesRegex(HostFault, 'OFF'):
            start_writes(snapshot, self.records())
        with self.assertRaisesRegex(HostFault, 'IDLE'):
            start_writes(replace(snapshot, status=snapshot.status ^ (1 << STATUS_BITS['IDLE1'])),
                         self.records()[:1], enabled=True)

    def fill(self):
        exporter = FencedCanonicalExport(self.records()[0], self.final_snapshot(), enabled=True)
        for index in range(256):
            exporter.accept(OwnedCanonicalWord(7, ExportWord(CANONICAL_A, 0,
                self.records()[0].header.owner, index, encode_signed96(1 if index == 0 else 0))))
        return exporter

    def test_retained_owner_after_start_and_final_error_fence(self):
        self.assertEqual(self.fill().finish(self.final_snapshot()).digits, (1,) + (0,)*255)
        for bad in (replace(self.final_snapshot(), error=1),
                    replace(self.final_snapshot(), committed=(replace(self.records()[0], lease=9),)),
                    replace(self.final_snapshot(), coherent_command_ack=False)):
            exporter = self.fill()
            with self.assertRaises(HostFault):
                exporter.finish(bad)
            self.assertTrue(exporter.failed)

    def test_old_session_is_not_accepted_even_if_full_owner_aliases(self):
        exporter = FencedCanonicalExport(self.records()[0], self.final_snapshot(), enabled=True)
        word = ExportWord(CANONICAL_A, 0, self.records()[0].header.owner, 0, encode_signed96(0))
        with self.assertRaisesRegex(HostFault, 'SESSION'):
            exporter.accept(OwnedCanonicalWord(6, word))
        with self.assertRaisesRegex(HostFault, 'POISONED'):
            exporter.accept(OwnedCanonicalWord(7, word))


if __name__ == '__main__':
    unittest.main()
