"""Scalar generic carry bounds and exact P16-source equivalence, not HDL validation.

Only P8/default P16 are qualified here. The geometric power-of-two predicate
does not grant additional numeric-width support. No full-N transform executes.
"""
import hashlib
from pathlib import Path
from .stream_ntt_blockwrap2_proposal import bound_proof

ROOT = Path(__file__).resolve().parents[1]
SETUP = 'rtl/kernel/genefer_stream27_blockcarry_setup_param_v1.sv'
LANE = 'rtl/kernel/genefer_stream27_blockcarry_lane_param_v1.sv'
PARENTS = {
    'rtl/kernel/genefer_track_a4_setup_v1.sv': '23d2a6832dc589fd8782cc7ed3f90980be1018b833d1a94714ab34058915da25',
    'rtl/kernel/genefer_track_a4_blockcarry_lane_v1.sv': '07be83b090375ddb721b00c3effe5b44e81dd89fb174708a52a14bfdcc816b02',
    'rtl/kernel/genefer_stream27_blockcarry_small_cell.sv': 'eafee617681cbd84cedfe90874938f63bf5ae84123ba1c914410785b44a3e74f',
}

def need(ok, tag):
    if not ok: raise ValueError(tag)

def minimum_base(n, p):
    return max(2*n+5, (2*(2*n+24*p)+2)//3+1)

def bounds(n, p, base):
    need(type(n) is int and n in [1 << aw for aw in range(5,17)] and
         type(p) is int and p in (8,16) and p <= n//2, 'S4_PARAM_QUALIFIED_GEOMETRY')
    result = dict(bound_proof(n, p, base))
    result['A']=result['doubled_coefficient_bound']
    result['serial_carry_bound']=result['serial_carry_abs_bound']
    # Preserve exactly the frozen implementation widths and proof guards.
    need(result['A'] < 1 << 77, 'S4_PARAM_A77')
    need(result['serial_carry_bound'] < 1 << 47, 'S4_PARAM_FIRST_Q47')
    return result

def parent_identity():
    for name, pin in PARENTS.items():
        need(hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == pin,
             'S4_PARAM_FROZEN_PARENT_DRIFT '+name)
    old_setup = (ROOT/'rtl/kernel/genefer_track_a4_setup_v1.sv').read_text()
    old_lane = (ROOT/'rtl/kernel/genefer_track_a4_blockcarry_lane_v1.sv').read_text()
    expected_setup = '// Generic-P isolated setup successor; P16 parent stays frozen.\n'+old_setup
    setup_changes = [
        ('genefer_track_a4_setup_v1 #(parameter int AW=16)', 'genefer_stream27_blockcarry_setup_param_v1 #(parameter int AW=16,P=16)'),
        ('K=2*N+384', 'K=2*N+24*P'),
        ("96'd16*96'(K)*96'(K)", "96'(P)*96'(K)*96'(K)"),
        ("81'(N+48)", "81'(N+3*P)"),
        ("96'(bk)<<6", "96'(bk)*96'(4*P)"),
        ('AW<5 || AW>16)', 'AW<5 || AW>16 || P<1 || P>N/2 || (P&(P-1))!=0)'),
    ]
    for old,new in setup_changes:
        need(expected_setup.count(old)==1, 'S4_PARAM_SETUP_ANCHOR'); expected_setup=expected_setup.replace(old,new)
    expected_lane = old_lane.replace('// One contiguous block, P=16.',
        '// Generic-P isolated successor; only P8/defaultP16 qualified by this task.\n// One contiguous block, T=N/P.',1)
    lane_changes = [
        ('genefer_track_a4_blockcarry_lane_v1 #(\n    parameter int AW=16', 'genefer_stream27_blockcarry_lane_param_v1 #(\n    parameter int AW=16,P=16'),
        ('BLOCKS=16', 'BLOCKS=P'),
        ('AW<5 || AW>16)', 'AW<5 || AW>16 || P<1 || P>N/2 || (P&(P-1))!=0)'),
    ]
    for old,new in lane_changes:
        need(expected_lane.count(old)==1, 'S4_PARAM_LANE_ANCHOR'); expected_lane=expected_lane.replace(old,new)
    actual_lane=(ROOT/LANE).read_text()
    # Strip only the additive first comment, then insist on byte-exact body.
    if actual_lane.startswith('// Generic-P isolated lane successor; qualification P8/default P16 only.\n'):
        actual_lane=actual_lane.split('\n',1)[1]
    need((ROOT/SETUP).read_text()==expected_setup, 'S4_PARAM_SETUP_SOURCE_DELTA')
    need(actual_lane==expected_lane, 'S4_PARAM_LANE_SOURCE_DELTA')
    checks=[]
    for aw in range(5,17):
        n=1<<aw
        for p in (8,16):
            for base in (minimum_base(n,p),1000000000):
                r=bounds(n,p,base); checks.append(dict(aw=aw,p=p,base=base,A=r['A'],q=r['serial_carry_bound']))
        # P16 scalar formula equals the parent constants exactly, not by sampling RTL.
        for base in (minimum_base(n,16),1000000000):
            B=base-1; K=2*n+384
            need(bounds(n,16,base)['A']==2*((n+48)*B*B+64*B*K+16*K*K),'S4_PARAM_P16_EXACT_BOUND')
    return dict(status='PASS_source_scalar_equivalence', checked=checks,
                P16_identity='Exact source delta; at P16 all constants match and 96-bit multiply64 equals shift6 modulo2^96.',
                native_run_performed=False, full_N_numeric_NTT_performed=False)
