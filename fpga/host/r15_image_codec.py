# SPDX-License-Identifier: Apache-2.0
"""Default-OFF retained canonical export adapter, not a hardware DMA ABI.

Format A contains the already materialized canonical signed96 words. It must
NOT pass through the raw carry finalizer. Format B is deliberately refused:
the requested pre-canonical raw endpoint has not been source-qualified yet.
Twelve-byte LE words below are a software serialization, not a vendor BAR or
DMA packet assignment. Full owner/context come from one publication snapshot.
"""
from dataclasses import dataclass

from .r15_arithmetic import need

CANONICAL_A = 'canonical96-natural-image-v1'
RAW_B = 'raw32-natural-carry-c0-c1-v1'


@dataclass(frozen=True)
class Publication:
    n: int
    base: int
    context: int
    owner: int
    completed: int
    coherent_ack: bool


@dataclass(frozen=True)
class ExportWord:
    format: str
    context: int
    owner: int
    index: int
    data: bytes


@dataclass(frozen=True)
class CanonicalImage:
    publication: Publication
    digits: tuple
    special: bool
    format: str = CANONICAL_A


def validate_publication(snapshot):
    need(type(snapshot) is Publication and snapshot.coherent_ack is True,
         'COHERENT_PUBLICATION_ACK')
    need(type(snapshot.n) is int and snapshot.n in (32, 256, 65536) and
         type(snapshot.base) is int and 2 <= snapshot.base <= 1000000000,
         'CANONICAL_PROFILE')
    need(type(snapshot.context) is int and snapshot.context in (0, 1) and
         type(snapshot.owner) is int and 0 <= snapshot.owner < 1 << 56,
         'CANONICAL_FULL56_OWNER')
    need(type(snapshot.completed) is int and 1 <= snapshot.completed < 1 << 32 and
         snapshot.owner >> 24 == snapshot.completed - 1,
         'CANONICAL_COMPLETED_SEQUENCE')
    return snapshot


def encode_signed96(value):
    need(type(value) is int and -(1 << 95) <= value < 1 << 95, 'SIGNED96_VALUE')
    return value.to_bytes(12, 'little', signed=True)


def decode_signed96(data):
    need(type(data) is bytes and len(data) == 12, 'SIGNED96_EXACT_BYTES')
    # Inspect ALL 96 bits; never discard high limbs before the canonical gate.
    return int.from_bytes(data, 'little', signed=True)


class CanonicalCollector:
    def __init__(self, snapshot, *, enabled=False, format=CANONICAL_A):
        need(enabled is True, 'CANONICAL_EXPORT_OFF')
        need(format in (CANONICAL_A, RAW_B), 'UNKNOWN_EXPORT_FORMAT')
        need(format == CANONICAL_A, 'RAW_B_ENDPOINT_UNQUALIFIED')
        self.snapshot = validate_publication(snapshot)
        self._digits = []
        self.failed = False
        self.published = False

    def accept(self, word):
        need(not self.failed and not self.published, 'EXPORT_NOT_WRITABLE')
        # A rejected record poisons this software transaction until full reload,
        # rather than letting a caller remove the record and silently continue.
        self.failed = True
        need(type(word) is ExportWord and word.format == CANONICAL_A,
             'EXPORT_FORMAT_MIXED_OR_UNKNOWN')
        need(type(word.context) is int and word.context == self.snapshot.context and
             type(word.owner) is int and word.owner == self.snapshot.owner,
             'EXPORT_CONTEXT_FULL_OWNER')
        need(type(word.index) is int and word.index == len(self._digits) and
             word.index < self.snapshot.n, 'EXPORT_ROW_ORDER_COUNT')
        value = decode_signed96(word.data)
        need(value == -1 or 0 <= value < self.snapshot.base, 'CANONICAL_DIGIT_NO_TRIM')
        self._digits.append(value)
        self.failed = False

    def finish(self):
        need(not self.failed and not self.published and
             len(self._digits) == self.snapshot.n, 'COMPLETE_CANONICAL_IMAGE')
        digits = tuple(self._digits)
        special = digits[0] == -1
        self.failed = True
        need((special and digits == (-1,) + (0,) * (self.snapshot.n - 1)) or
             (not special and all(0 <= d < self.snapshot.base for d in digits)),
             'EXACT_CANONICAL_SPECIAL_IMAGE')
        self.failed = False
        self.published = True
        return CanonicalImage(self.snapshot, digits, special)


def load_software_backend(image, backend):
    """Use canonical A directly as a residue; do not run the B finalizer."""
    need(type(image) is CanonicalImage and image.format == CANONICAL_A,
         'TYPED_CANONICAL_IMAGE')
    validate_publication(image.publication)
    need(backend.n == image.publication.n and backend.base == image.publication.base,
         'BACKEND_CANONICAL_PROFILE')
    # Revalidate because dataclasses can be constructed without the collector.
    check = CanonicalCollector(image.publication, enabled=True)
    for index, value in enumerate(image.digits):
        check.accept(ExportWord(CANONICAL_A, image.publication.context,
                                image.publication.owner, index, encode_signed96(value)))
    need(check.finish() == image, 'CANONICAL_IMAGE_PROVENANCE')
    if image.special:
        value = int(backend.modulus - 1)
    else:
        value = 0
        for digit in reversed(image.digits):
            value = value * backend.base + digit
    backend.load(value)
    return value
