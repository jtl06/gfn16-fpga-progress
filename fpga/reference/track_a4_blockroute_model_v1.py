"""Block-route event model; data are opaque32-bit tags, never numeric NTT work."""
from dataclasses import dataclass, field


def geometry(aw):
    if type(aw) is not int or not 5 <= aw <= 16:
        raise ValueError("AW5..16")
    return 1 << aw, 1 << (aw-4)


def encode(aw, lane):
    return sum(((lane >> bit) & 1) << ((aw-4+bit) % 7) for bit in range(4))


def decode(aw, bank):
    return sum(((bank >> ((aw-4+bit) % 7)) & 1) << bit for bit in range(4))


def fold(aw, address):
    bank = 0
    for bit in range(aw):
        bank ^= ((address >> bit) & 1) << (bit % 7)
    return bank


def route(aw, offset, mask, words=None):
    """RTL factored permutation expressed independently from natural addresses."""
    _, t = geometry(aw)
    if not 0 <= offset < t or not 0 <= mask < 65536:
        raise ValueError("block descriptor")
    if words is None:
        words = tuple(range(16))
    base, lane_mask = fold(aw, offset), encode(aw, 15)
    result = {}
    for bank in range(128):
        if (bank ^ base) & ~lane_mask:
            continue
        lane = decode(aw, bank ^ base)
        if (mask >> lane) & 1:
            result[bank] = (((lane*t) | offset) >> 7, words[lane], lane)
    return result


@dataclass
class Memory:
    aw: int
    words: dict = field(default_factory=dict)
    q: list = field(default_factory=lambda: [0]*128)
    read_bank: int = 0
    read_offset: int = 0

    def edge(self, *, rst=1, enable=1, read_en=0, write_en=0, read_offset=0, write_offset=0,
             read_mask=65535, write_mask=65535, write_words=(0,)*16):
        _, t = geometry(self.aw)
        request = bool(read_en or write_en)
        legal = (enable and (not read_en or 0 <= read_offset < t)
                 and (not write_en or 0 <= write_offset < t)
                 and not (read_en and write_en and read_offset == write_offset and read_mask & write_mask))
        reads = route(self.aw, read_offset, read_mask) if rst and read_en and legal else {}
        writes = route(self.aw, write_offset, write_mask, write_words) if rst and write_en and legal else {}
        for bank, (row, _, _) in reads.items():
            assert bank not in writes or writes[bank][0] != row
            self.q[bank] = self.words.get((bank, row), 0)
        for bank, (row, word, _) in writes.items():
            self.words[bank, row] = word
        if not rst:
            self.read_bank = self.read_offset = 0
        elif read_en and legal:
            self.read_bank, self.read_offset = fold(self.aw, read_offset), read_offset
        values = tuple(self.q[self.read_bank ^ encode(self.aw, lane)] for lane in range(16))
        return dict(error=int(bool(rst and request and not legal)), read_valid=int(bool(rst and read_en and legal)),
                    read_mask=read_mask if rst and read_en and legal else 0,
                    read_offset=self.read_offset, read_words=values,
                    reads=reads, writes=writes)
