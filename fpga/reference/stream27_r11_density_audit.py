"""R11 source-specific metadata-density screen/model, not native or fit proof."""
from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import json
import random

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / 'results/throughput-20260929/trackS-c2-storage-combo-timing10-native-v1/full-normal/production-bundle.json'


@dataclass
class DelayModel:
    width: int
    old: list = field(default_factory=lambda: [None] * 16)
    memory: list = field(default_factory=lambda: [None] * 16)
    held: int | None = None
    prefetched: int | None = None
    pointer: int = 0
    filled: int = 0
    valid: list = field(default_factory=lambda: [False] * 16)
    comparisons: int = 0
    collisions: int = 0

    def reset(self):
        # Asynchronous eligibility/address reset. All payload remains unreset.
        self.pointer = self.filled = 0
        self.valid = [False] * 16

    def tick(self, joined, word, rst_n=True, stop=False):
        eligible = self.valid[-1] and rst_n
        head = self.prefetched if self.filled == 16 else 0
        if eligible:
            assert head == self.old[-1], 'eligible preedge metadata differs'
            self.comparisons += 1
        next_pointer = (self.pointer + 1) & 15
        assert next_pointer != self.pointer
        self.collisions += next_pointer == self.pointer
        incoming = word & ((1 << self.width) - 1) if joined else self.held
        # NBA semantics: read preedge memory, then update memory/shift/held.
        self.prefetched = self.memory[next_pointer]
        self.memory[self.pointer] = incoming
        self.old = [incoming] + self.old[:-1]
        if joined:
            self.held = incoming
        if rst_n:
            self.pointer = next_pointer
            self.filled = min(16, self.filled + 1)
            self.valid = [bool(joined and not stop)] + self.valid[:-1]
        else:
            self.reset()
        return eligible, head


def model_checks(cycles=10000):
    rng = random.Random(0xC2711)
    counts = []
    for width in (30, 38):
        model = DelayModel(width)
        model.reset()
        for cycle in range(cycles):
            reset = cycle % 257 in (0, 1, 2) or cycle % 509 == 31
            if reset:
                model.reset()
            word = rng.getrandbits(width)
            # Dense spans, isolated impulses, bubbles, malformed owners, stop
            # and writes held under reset all preserve the payload-only seam.
            joined = cycle % 97 < 35 or rng.randrange(4) == 0
            model.tick(joined, word, not reset, cycle % 113 in (12, 13))
        counts.append(dict(width=width, comparisons=model.comparisons,
                           cycles=cycles, address_collisions=model.collisions))
    return counts


def audit():
    from fpga.reference.stream27_crt_tag_delay_bind import bind_arithmetic
    raw = CAPTURE.read_bytes()
    bundle = json.loads(raw)
    roots = [(name, text) for name, text in bundle['files'].items()
             if 'logic [TAG_W-1:0] crt_tag[0:15]' in text]
    assert len(roots) == 1
    name, text = roots[0]
    changed = bind_arithmetic(text)
    row_w = bundle['parameters']['AW'] - 4
    width = 25 + row_w + 1
    measured = ROOT / 'results/throughput-20260929/trackS-p16-packed-delay-v1/field-result.json'
    return dict(schema='stream27-r11-density-source-model-v1', evidence='source/model only',
        captured_bundle=str(CAPTURE.relative_to(ROOT)), captured_bundle_sha256=hashlib.sha256(raw).hexdigest(),
        exact_top=bundle['top'], lean_production=bundle['parameters']['LEAN_PRODUCTION'],
        arithmetic_root=name, parent_root_sha256=hashlib.sha256(text.encode()).hexdigest(),
        candidate_root_sha256=hashlib.sha256(changed.encode()).hexdigest(),
        candidate='shared CRT tag/double D16 qualified MLAB delay with held stage0',
        declared_ff=dict(old=16*width, held=width, prefetch=width, pointer=4, filled=5,
                         reduction_upper_bound=16*width-2*width-9),
        field_to_crt_added_declared_ff=16*(81+25+row_w+2),
        complete_r11_added_ff='pending exact R11 source; core provisional total about5600',
        model=model_checks(), no_rw_check_proof='For every pointer in Z/16, (pointer+1)mod16 != pointer, including reset-held writes.',
        lifetime='Input stage0 updates only joined; delay advances every clock, unreset payload; first eligible CRT consume after16 fresh clocks.',
        authority='No admission, validator, full owner, valid, stop, error or publication change; invalid payload not compared.',
        measured_prior_field=dict(path=str(measured.relative_to(ROOT)),lab_delta=-397,
                                  scope='packed commutator only, ALREADY composed in R10; not a new saving'),
        parked=['Term payload MLAB OLD_DATA mapping failures', 'full feedback FIFO depth0',
                'already optimized96-bit CRT/canonical widths'],
        native_qualified=False, physical_measured=False, whole_lab_saving=None, clock_claim=None)


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
