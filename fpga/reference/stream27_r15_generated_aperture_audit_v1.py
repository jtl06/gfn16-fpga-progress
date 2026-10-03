"""Read-only scalar witness for the first actual generated DMA router.

This does not execute or repair vendor RTL. It establishes why generation-v1
cannot be promoted to a full-address-checked shell merely from successful Qsys.
"""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'results/throughput-20260929/r15-pcie-system-generation-v1-artifacts'
ROUTER = 'r15_pcie_system_v1/altera_merlin_router_1921/synth/r15_pcie_system_v1_altera_merlin_router_1921_bldtfhi.sv'


def audit():
    raw = (BASE/ROUTER).read_bytes()
    text = raw.decode()
    anchors = ["localparam ADDR_RANGE = 64'h1004000;",
               'address [REAL_ADDRESS_RANGE:0] = sink_data[OPTIMIZED_ADDR_H : PKT_ADDR_L];',
               'src_channel = default_src_channel;',
               "{address[24:22],{22 {1'b0}}} == 25'h0",
               '//    default_channel         0',
               '//    has_default_slave       0']
    if not all(a in text for a in anchors):
        raise ValueError('R15_APERTURE_CAPTURE_CHANGED')
    # log2ceil(0x1004000)=25. The first write mapping consumes bits24:22;
    # the cold agent receives only bits21:0. Thus this illegal full64 address
    # has exactly the same destination and local address as legal address0.
    invalid = 1 << 32
    optimized = invalid & ((1 << 25)-1)
    assert optimized == 0 and optimized >> 22 == 0
    return {'schema': 'r15-generated-aperture-audit-v1',
            'status': 'BLOCKED_FULL64_ADDRESS_ALIAS',
            'router_path': str((BASE/ROUTER).relative_to(ROOT)),
            'router_sha256': hashlib.sha256(raw).hexdigest(),
            'invalid_byte_address': invalid, 'optimized_address': optimized,
            'destination': 'app.cold', 'agent_byte_address': 0,
            'scalar_source_witness_only': True,
            'native_execution_claim': False,
            'required_repair': 'Check full64 aperture before generated narrowing; retain exact earlier generation.'}
