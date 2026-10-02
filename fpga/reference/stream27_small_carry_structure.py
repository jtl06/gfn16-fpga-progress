"""Pinned source/proof contract for S3 small-carry cell; never invokes HDL."""
import hashlib
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RTL='rtl/kernel/genefer_stream27_blockcarry_small_cell.sv'
PINS={
    RTL:'eafee617681cbd84cedfe90874938f63bf5ae84123ba1c914410785b44a3e74f',
    'reference/stream27_small_carry_oracle.py':'24e8005d5447c7b5584d740c4b9b253d15965e4cb4ee40ab8ba0c17b8581d709',
    'reference/stream_ntt_blockwrap2_proposal.py':'b6f94debf66b07aa118ab7e82be6802fd5a81cbc8c41a99cb79f65f91726e255',
    'reference/stream_ntt_blockcarry_schedule.py':'eca87517cada3413f18313d447b76e1fcf3c3826e70391f3baf39561ab23b632',
    'docs/briefs/2026-09-30-answers-B20260930-r6.md':'6f3fcc726ae6e2d41733fc80afff3422c9d4ecc9fc449f6a74c400d3bbc8fafb',
    'docs/STREAM27-BLOCKCARRY-PROFILE.md':'c3c3fbe371de9bcaf1781b8175dc53c5615393c8a63c62783e81527c822c449c',
}


def validate(root=ROOT):
    root=Path(root)
    for name,digest in PINS.items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('S3 small-carry pinned source changed: '+name)
    source=(root/RTL).read_text()
    registers=set(re.findall(r'\b(\w+)\s*<=',source[source.index('always_ff'):source.index('// synthesis translate_off')]))
    if source.count('always_ff')!=2 or registers!={'out_valid','out_error','carry_out','payload_out','digit'}:
        raise ValueError('extra small-carry input/feedback stage')
    return dict(status='source_only_not_native_or_physical_qualified',source_sha256=PINS,
                register_stages=1,acceptance_to_registered_output_edge_offset=0,
                producer_to_consumer_edge_spacing=1,initiation_interval=1,
                native_first_profiles=[dict(aw=5,p=8),dict(aw=16,p=8)],
                outer_owner=['base/generation coherence','per-lane carry feedback','quarantine/reload'])


def proof_statement():
    return {
        'definitions':'N=2^AW; B=b-1; K=2N+24P; Q=2N+23P=K-P',
        'domain':'AW5..16; power-of-two P<=N/2; max(2N+5,ceil(2K/3)+1)<=b<=1e9',
        'coefficient':'A=2*((N+3P)*B^2+4P*B*K+P*K^2), including doubling',
        'q2':'2K<=3B gives ceil(A/b^2)<=2N+23P=Q<K',
        'y':'-Q<=y=r0+r1_previous+q2_previous_previous<=2B+Q; block_start requires0<=y<=B',
        'feedback':'With c in[-2,3], -Q-2<=y+c<=2B+Q+3; Q<=1.5B-P gives -2b<=y+c<4b',
        'selection':'Six half-open intervals [-2b,-b),[-b,0),[0,b),[b,2b),[2b,3b),[3b,4b) select q=-2..3 and d=(y+c)-q*b in[0,b)',
        'width':'4b<=4000000000<2^32, so signed33 represents all admitted totals, thresholds and corrections; no full-word input truncation',
        'scope':'Local normalization guarantee only. Wider-P cell arithmetic tests do not adopt a wider-P whole streaming profile; upstream coefficient/CRT/frame eligibility remains controller-owned.',
    }
