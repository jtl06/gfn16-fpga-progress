"""Additive width-explicit export span over immutable endpoint v7.

Only operand zero extension changes; unsigned mathematical bounds are identical.
"""
import hashlib
from . import stream27_r15_pcie_avmm_v7 as parent

PARENT_SHA='f17f3fe1aa25d52d7577fb1a223de8a001fbcdea59613aedf2aa0f951bf1ea2e'
BEFORE="({1'b0,export_address[21:5]}+{13'b0,export_burstcount})>N"
AFTER="({15'b0,export_address[21:5]}+{27'b0,export_burstcount})>N"


def source():
    raw=parent.source()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('R15_AVMM_V8_FROZEN_PARENT')
    text=raw.decode()
    if text.count(BEFORE)!=1:raise ValueError('R15_AVMM_V8_UNIQUE_ANCHOR')
    return text.replace(BEFORE,AFTER,1).encode()
