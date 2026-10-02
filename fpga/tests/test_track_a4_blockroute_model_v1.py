import random
import unittest

from fpga.reference import track_a4_blockroute_model_v1 as m
from fpga.reference.track_a4_blockroute_source_v1 import verify
from fpga.reference.track_a4_blockcarry_model import bank_of


class BlockrouteTests(unittest.TestCase):
    def test_exact_parent_diff_guard(self):
        self.assertEqual(len(verify()), 2)

    def test_all_addresses_and_factored_permutations(self):
        for aw in range(5, 17):
            n, t = m.geometry(aw)
            seen = set()
            for offset in range(t):
                actual = m.route(aw, offset, 65535)
                expected = {bank_of(lane*t+offset): ((lane*t+offset) >> 7, lane, lane) for lane in range(16)}
                self.assertEqual(actual, expected)
                seen.update((bank, item[0]) for bank, item in actual.items())
            self.assertEqual(len(seen), n)

    def test_parent_scalar_layout_identity_and_masked_read_write(self):
        rng = random.Random(0xA4B4)
        for aw in (5, 8, 12, 16):
            n, t = m.geometry(aw)
            # Initialize exactly as the parent's scalar RAM path: bank_of(a),a>>7.
            flat = [rng.getrandbits(32) for _ in range(n)]
            memory = m.Memory(aw, {(bank_of(a), a >> 7): value for a, value in enumerate(flat)})
            for _ in range(1000):
                ro, wo = rng.randrange(t), rng.randrange(t)
                rm, wm = rng.randrange(65536), rng.randrange(65536)
                words = tuple(rng.getrandbits(32) for _ in range(16))
                enable = rng.randrange(8) != 0
                collision = ro == wo and bool(rm & wm)
                expected = [flat[k*t+ro] for k in range(16)]
                before = memory.words.copy()
                out = memory.edge(enable=enable, read_en=1, write_en=1, read_offset=ro,
                                  write_offset=wo, read_mask=rm, write_mask=wm, write_words=words)
                self.assertEqual(out["error"], int(not enable or collision))
                if enable and not collision:
                    self.assertEqual(out["read_offset"], ro)
                    self.assertEqual(out["read_mask"], rm)
                    for k in range(16):
                        if rm >> k & 1:
                            self.assertEqual(out["read_words"][k], expected[k])
                        if wm >> k & 1:
                            flat[k*t+wo] = words[k]
                else:
                    self.assertEqual(memory.words, before)
                    self.assertFalse(out["read_valid"])
            self.assertEqual(memory.words, {(bank_of(a), a >> 7): value for a, value in enumerate(flat)})

    def test_48_edge_prefill_overlap(self):
        for aw in range(5, 17):
            _, t = m.geometry(aw)
            for offset in range(48, t):
                reads, writes = m.route(aw, offset, 65535), m.route(aw, offset-48, 65535)
                self.assertFalse(any(reads[b][0] == writes[b][0] for b in reads.keys() & writes.keys()))

    def test_reset_and_atomic_bad_descriptor(self):
        memory = m.Memory(8)
        memory.edge(write_en=1, write_offset=0, write_words=tuple(range(16)))
        before = memory.words.copy()
        for args in (dict(read_offset=16), dict(write_offset=16), dict(enable=0), {}):
            result = memory.edge(read_en=1, write_en=1, **args)
            self.assertTrue(result["error"])
            self.assertEqual(memory.words, before)
        result = memory.edge(rst=0, read_en=1, write_en=1)
        self.assertEqual((result["error"], result["read_valid"], result["read_mask"]), (0, 0, 0))
        self.assertEqual(memory.words, before)
        # Same offset is legal with disjoint masks (different block addresses).
        result = memory.edge(read_en=1, write_en=1, read_mask=0x5555, write_mask=0xaaaa)
        self.assertFalse(result["error"])
        self.assertTrue(result["read_valid"])

    def test_native_corpus_against_independent_flat_memory(self):
        from fpga.reference.track_a4_blockroute_vectors_v1 import corpus
        for aw in (5, 8):
            text, _ = corpus(aw)
            n, t = m.geometry(aw)
            flat, tag = [0]*n, 0
            for line in text.splitlines()[1:]:
                row = list(map(int, line.split()))
                rst, enable, re, we, ro, wo, rm, wm = row[:8]
                words = row[8:24]
                error, valid, actual_tag, mask = row[24:28]
                expected = row[28:44]
                legal = bool(enable and (not re or ro<t) and (not we or wo<t)
                             and not (re and we and ro==wo and rm & wm))
                self.assertEqual(error, int(bool(rst and (re or we) and not legal)))
                self.assertEqual(valid, int(bool(rst and re and legal)))
                self.assertEqual(mask, rm if valid else 0)
                if not rst:
                    tag = 0
                elif valid:
                    tag = ro
                    for lane in range(16):
                        if rm >> lane & 1:
                            self.assertEqual(expected[lane], flat[lane*t+ro])
                self.assertEqual(actual_tag, tag)
                if rst and we and legal:
                    for lane in range(16):
                        if wm >> lane & 1:
                            flat[lane*t+wo] = words[lane]


if __name__ == "__main__":
    unittest.main()
