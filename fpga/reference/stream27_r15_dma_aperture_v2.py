"""Additive guard credit repair for the actual registered endpoint composition.

Downstream responses require a previously clocked rd_expected credit. No same
edge response is supported; unexpected/zero-latency RV is a terminal fault.
This removes downstream WAITREQUEST from the combinational fault cone, without
withdrawing any offered request or changing the existing bounded-tail contract.
"""
from pathlib import Path
import hashlib

ROOT=Path(__file__).resolve().parents[1]
RTL='rtl/kernel/genefer_stream27_r15_dma_aperture_v1.sv'
PARENT=ROOT/'results/throughput-20260929/trackS-r15-dma-aperture-native-v1/normal-v1/source/fpga'/RTL
PARENT_SHA='244ec8e67e8f61dddc3cb7c91f82ebe17fb92de2252a13fd3e55fccbc90fd644'
BEFORE=b' wire response_credit=(rd_expected!=0) || down_rd_fire;'
AFTER=b''' // Actual endpoint/CDC has registered nonzero response latency. A
 // same-edge/uncredited RV is unexpected: never infer credit from WAITREQUEST.
 // Thus fault_valid/current_error have no combinational down_rd_fire fan-in.
 wire response_credit=(rd_expected!=0);'''


def source():
    raw=PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('R15_APERTURE_V2_FROZEN_PARENT')
    if raw.count(BEFORE)!=1:raise ValueError('R15_APERTURE_V2_CREDIT_ANCHOR')
    return raw.replace(BEFORE,AFTER,1)
