"""Deterministic opaque-word route corpus, source expectations not HDL results."""
import hashlib
import random

from fpga.reference.track_a4_blockroute_model_v1 import Memory, geometry


def corpus(aw, random_events=1024):
    if aw not in (5, 8) or not 1 <= random_events <= 8192:
        raise ValueError("bounded AW5/AW8 route corpus")
    _, t = geometry(aw)
    memory = Memory(aw)
    rng = random.Random(0xA4B020261001+aw)
    rows = []
    counts = dict(errors=0, responses=0, writes=0, simultaneous=0, resets=0)

    def emit(**kwargs):
        args = dict(rst=1, enable=1, read_en=0, write_en=0, read_offset=0, write_offset=0,
                    read_mask=65535, write_mask=65535, write_words=tuple(rng.getrandbits(32) for _ in range(16)))
        args.update(kwargs)
        out = memory.edge(**args)
        rows.append(tuple(args[k] for k in ("rst", "enable", "read_en", "write_en", "read_offset", "write_offset", "read_mask", "write_mask"))
                    + args["write_words"] + (out["error"], out["read_valid"], out["read_offset"], out["read_mask"])
                    + out["read_words"])
        counts["errors"] += out["error"]
        counts["responses"] += out["read_valid"]
        counts["writes"] += bool(out["writes"])
        counts["simultaneous"] += bool(out["reads"] and out["writes"])
        counts["resets"] += not args["rst"]

    emit(rst=0)
    # Initialize all physical addresses before requesting any masked word.
    for offset in range(t):
        emit(write_en=1, write_offset=offset)
    for offset in range(t):
        emit(read_en=1, read_offset=offset)
    # Exhaust small-N concurrent offset pairs, including same-address reject.
    for ro in range(t):
        for wo in range(t):
            emit(read_en=1, write_en=1, read_offset=ro, write_offset=wo)
            emit(read_en=1, write_en=1, read_offset=ro, write_offset=wo, read_mask=0x5555, write_mask=0xaaaa)
    for i in range(random_events):
        emit(rst=int(i % 67 != 0), enable=int(i % 23 != 0),
             read_en=int(i % 3 != 0), write_en=int(i % 5 != 0),
             read_offset=rng.randrange(t+1), write_offset=rng.randrange(t+1),
             read_mask=rng.randrange(65536), write_mask=rng.randrange(65536))
    for offset in range(t):
        emit(read_en=1, read_offset=offset)
    emit()
    text = f"A4ROUTE1 {aw} {len(rows)}\n" + "\n".join(" ".join(map(str, row)) for row in rows) + "\n"
    return text, dict(aw=aw, events=len(rows), **counts, sha256=hashlib.sha256(text.encode()).hexdigest(),
                     scope="source expectations only, no native result")
