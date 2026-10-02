"""R85 exact legal ranges versus observable malformed-input and physical width.

Model/source/report inspection only. No truncation, RTL generation, numerical
full-N transform, or area credit. C1 localbase and C2 original carry/canonical
lineages are named separately; their shared numeric proofs are not source or
physical qualification inheritance.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PRIMES = (104857601, 69206017, 67239937)
M = PRIMES[0]*PRIMES[1]*PRIMES[2]
MAX_BASE = 1_000_000_000
SYN = 'queue/standing-fit-state/terminal/s4-p16-timing-whole-9000-high-effort-v1/evidence/project/output_files/probe.syn.rpt'
SYN_PIN = 'c9f9a929804541cf129eee4e4fa1ed85935fd8998defef7f44297e33b7071374'
LEAVES = {
    'genefer_crt3_27_mont_pipe.sv': '8bb5b62423c1f61e069f131b5d393dd3dbc84d05348fc1945f6e9c419c104c58',
    'genefer_div_recip_precision.sv': '832021ed0b3410dc867d92ac4436a725d5717f9630d233073e39896789ebbd7c',
    'genefer_stream27_blockcarry_lane_localbase_v1.sv': 'cb3fcd665036a1d9028bc2d7e33e96c2e5f57e3e95e16a25460173d32560b236',
    'genefer_stream27_blockcarry_small_cell_localbase_v1.sv': '2005d97a1b512c365b1b6494d8974d3f869d15ee7ce8713115eab8d713e69c1b',
    'genefer_stream27_canonical_image_localbase_v1.sv': '87264ca12a08cdf4b905ffdcc27d066b25333c0f0283904ac0cf9d36f707d70d',
    'genefer_track_a4_setup_v1.sv': '23d2a6832dc589fd8782cc7ed3f90980be1018b833d1a94714ab34058915da25',
    'genefer_stream27_blockcarry_setup_param_v1.sv': 'c9ba8163c8bb43afecf1afee07a8a55c4eb89539318cf235b83508ab692f4f26',
    'genefer_stream27_blockcarry_lane_param_v1.sv': '8a458519272e89e635eb5cd7e6b2d07c93c8d3b1fc0f44874ba67aeccca77d4b',
    'genefer_stream27_canonical_image_pipe_v1.sv': '763b069a9797b91c7122bdf30fe86879b8c34dd318613ec4e096797610a379a5',
}


def need(ok, why):
    if not ok:
        raise ValueError('R85_' + why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def ceildiv(a, b):
    return -((-a)//b)


@dataclass(frozen=True)
class Interval:
    low: int
    high: int

    def __post_init__(self):
        need(type(self.low) is int and type(self.high) is int and self.low <= self.high, 'INTERVAL')

    def signed_width(self):
        width = 1
        while self.low < -(1 << (width-1)) or self.high >= 1 << (width-1):
            width += 1
        return width

    def unsigned_width(self):
        need(self.low >= 0, 'UNSIGNED_INTERVAL')
        return max(1, self.high.bit_length())

    def record(self, signed=True):
        return dict(low=self.low, high=self.high, mathematical_bits=self.signed_width() if signed else self.unsigned_width(),
                    interpretation='signed' if signed else 'unsigned', no_physical_savings_claim=True)


def parameters(aw=16, p=16):
    need(type(aw) is int and 5 <= aw <= 16 and p in (8,16), 'AW5_16_P8_16_SCOPE')
    n = 1 << aw
    k, q = 2*n+24*p, 2*n+23*p
    return dict(aw=aw, p=p, n=n, k=k, q=q, base_min=max(2*n+5, (2*k+2)//3+1), base_max=MAX_BASE)


def coefficient_limit(base, aw=16, p=16):
    v = parameters(aw,p)
    need(type(base) is int and v['base_min'] <= base <= MAX_BASE, 'QUALIFIED_HOST_BASE')
    b = base-1
    return 2*((v['n']+3*p)*b*b + 4*p*b*v['k'] + p*v['k']*v['k'])


def prove_profile(aw=16, p=16):
    """Endpoint/monotonic proof covers EVERY integer base, not sampled bases.

    A/b² = alpha + beta/b + gamma/b² with beta,gamma>=0, decreasing.
    A/b = alpha*b + beta + gamma/b is convex; its maximum on a closed
    positive-base interval is at an endpoint. A itself increases for b>=1.
    """
    v = parameters(aw,p); n,k,q,b0 = (v[x] for x in ('n','k','q','base_min'))
    alpha, beta, gamma = 2*(n+3*p), -4*(n+3*p)+8*p*k, 2*(n+3*p)-8*p*k+2*p*k*k
    need(beta >= 0 and gamma >= 0, 'POSITIVE_RATIONAL_BOUND_COEFFICIENTS')
    a = coefficient_limit(MAX_BASE,aw,p)
    need(a < 1 << 77 and a <= M//2, '77BIT_A_AND_UNIQUE_CENTERED_CRT_HEADROOM')
    q2 = ceildiv(coefficient_limit(b0,aw,p),b0*b0)
    q1 = max(ceildiv(coefficient_limit(b,aw,p),b) for b in (b0,MAX_BASE))
    need(q2 <= q and q1 < 1 << 47, 'DIV77_THEN_DIV47_PROOF')
    # d,r0,r1 are0..b-1; q2 is within±Q. Six carry regions -2..3.
    y = Interval(-q,2*MAX_BASE-2+q)
    total = Interval(-q-2,2*MAX_BASE+1+q)
    need(q+2 <= 2*b0 and q+1 < 2*b0, 'SIX_REGION_TOTAL_RANGE')
    raw0 = Interval(-q-2,MAX_BASE-1+q+3)
    high = Interval(-q-2,q+3)
    need(q+3 < k, 'BOUNDARY_HIGH_K_HEADROOM')
    max_b = MAX_BASE-1
    term0 = (n+3*p)*max_b*max_b
    term1 = 4*p*max_b*k
    term2 = p*k*k
    need(2*(term0+term1+term2) == a, 'SETUP_EXACT_BOUND_SUM')
    setup = dict(base_minus_one=Interval(0,max_b).record(False),
        b_squared=Interval(0,max_b*max_b).record(False), bk=Interval(0,max_b*k).record(False),
        term0=Interval(0,term0).record(False), term1=Interval(0,term1).record(False),
        term2=Interval(term2,term2).record(False), bound=Interval(0,a).record(False),
        restoring_remainder=Interval(0,MAX_BASE-1).record(False),
        restoring_shift=Interval(0,2*(MAX_BASE-1)).record(False),
        source_storage_bits=dict(b_squared=64,bk=50,term0=81,term1=96,bound=96,reciprocal=96),
        full_base32_reject_before_begin=True, bound_high19_check_before_limit77_slice=True)
    return dict(**v, coefficient_limit_max=a, bound_polynomial=dict(alpha=alpha,beta=beta,gamma=gamma),
        legal_coefficient=Interval(-a,a).record(), legal_undoubled_coefficient=Interval(-(a//2),a//2).record(),
        q1_abs_upper=q1, q2_abs_upper=q2, proof='A/b2 decreasing and A/b convex; endpoints prove all legal bases',
        first_quotient=Interval(-q1,q1).record(), second_quotient=Interval(-q,q).record(),
        remainder=Interval(0,MAX_BASE-1).record(False), carry=Interval(-2,3).record(),
        carry_y=y.record(), carry_total=total.record(), raw0=raw0.record(), boundary_high=high.record(),
        canonical_value=Interval(-2*MAX_BASE,3*MAX_BASE-1).record(),
        canonical_c0=Interval(-(MAX_BASE-1),MAX_BASE-1).record(),
        canonical_c1=Interval(-k,k).record(), canonical_or_host_storage_bits=32,
        canonical_read_signed96_is_signextension_of32=True,
        exact_reciprocal=Interval((1 << 96)//MAX_BASE,(1 << 96)//b0).record(False), setup=setup,
        generic_divider_base2_reciprocal_bits=96, public_signed96_preserved=True)


def crt_bounds():
    p1,p2,p3 = PRIMES; p12=p1*p2; half=M//2
    return dict(primes=list(PRIMES), modulus=M,
        product_p1_t2=Interval(0,p1*(p2-1)).record(False),
        x12=Interval(0,p12-1).record(False),
        product_p12_t3=Interval(0,p12*(p3-1)).record(False),
        reconstructed_value=Interval(0,M-1).record(False),
        centered_coefficient=Interval(-half,half).record(),
        after_integer_doubling=Interval(-2*half,2*half).record(),
        malformed_residue_scope='Full32 canonical-input assertions are simulation-only in this CRT leaf; hardware proof requires the canonical upstream producer. Do not reinterpret truncated arbitrary32 inputs as admitted CRT residues.')


def reciprocal_divide(value, base, mag_w):
    """Independent exact model of estimated quotient +one correction/sign fold."""
    need(mag_w in (47,77) and type(value) is int and abs(value) < 1 << mag_w
         and type(base) is int and 2 <= base <= MAX_BASE, 'DIVIDER_LEGAL_INPUT')
    magnitude, d = abs(value), 1 << mag_w
    reciprocal = (1 << 96)//base
    short = reciprocal >> (96-mag_w)
    need(short == d//base, 'RECIPROCAL_HIGH_SLICE_IDENTITY')
    estimate = magnitude*short//d
    quotient, remainder = divmod(magnitude,base)
    need(quotient-1 <= estimate <= quotient, 'AT_MOST_ONE_ESTIMATE_UNDERFLOW')
    provisional = magnitude-estimate*base
    need(0 <= provisional < 2*base < 1 << 32, 'LOW32_PROVISIONAL_IS_EXACT')
    unsigned_q = estimate + (provisional >= base)
    unsigned_r = provisional-base if provisional >= base else provisional
    q = -unsigned_q-(unsigned_r != 0) if value < 0 else unsigned_q
    r = base-unsigned_r if value < 0 and unsigned_r else unsigned_r
    need((q,r) == divmod(value,base), 'EUCLIDEAN_NOT_TRUNCATING_DIVISION')
    return dict(quotient=q,remainder=r,reciprocal_short=short,estimate=estimate,
                product_bits=(magnitude*short).bit_length(),implementation_product_width=2*mag_w)


def small_carry(y, carry, base, aw=16, p=16, block_start=False):
    """Full signed33/3 input detector, then exact six-region Euclidean fold."""
    v=parameters(aw,p)
    need(-(1 << 32) <= y < 1 << 32 and -4 <= carry <= 3, 'PUBLIC_SMALL_INPUT_ENCODING')
    effective=0 if block_start else carry
    total=y+effective
    legal=(v['base_min'] <= base <= MAX_BASE and carry >= -2 and
           -v['q'] <= y <= 2*base-2+v['q'] and
           (not block_start or 0 <= y < base) and -2*base <= total < 4*base)
    if not legal:
        return dict(error=True,out_valid=False)
    q,r=divmod(total,base)
    need(-2 <= q <= 3 and 0 <= r < base,'SMALL_EUCLIDEAN_RESULT')
    return dict(error=False,out_valid=True,carry=q,digit=r)


def canonical_fold(value, base):
    """Legal PROCESS value domain; no malformed value is narrowed first."""
    need(type(value) is int and type(base) is int and 2 <= base <= MAX_BASE,
         'CANONICAL_SCALAR_DOMAIN')
    if not -2*base <= value < 3*base:
        return dict(error=True)
    q,r=divmod(value,base)
    need(-2 <= q <= 2 and 0 <= r < base,'FIVE_REGION_CANONICAL_RESULT')
    return dict(error=False,carry=q,digit=r)


def signed_truncate(value, width):
    value &= (1 << width)-1
    return value-(1 << width) if value & (1 << (width-1)) else value


def coefficient_admitted(value, base=MAX_BASE, aw=16, p=16):
    need(type(value) is int and -(1 << 95) <= value < 1 << 95, 'FULL_SIGNED96_DOMAIN')
    return abs(value) <= coefficient_limit(base,aw,p)


def malformed_counterexamples():
    # Both are representable public96 tokens. They alias legal3 after80-bit
    # truncation and must remain faults BEFORE any transport/divider cut.
    result=[]
    for value in ((1 << 80)+3,-(1 << 80)+3,-(1 << 95),(1 << 95)-1):
        result.append(dict(public_signed96=value, admitted_before_truncation=coefficient_admitted(value),
            narrowed80=signed_truncate(value,80), admitted_after_truncation=coefficient_admitted(signed_truncate(value,80))))
    need(not any(row['admitted_before_truncation'] for row in result) and
         all(row['admitted_after_truncation'] for row in result), 'PRETRUNCATION_GUARD_IS_OBSERVABLE')
    return result


def inspect_sources():
    values={}
    for name,pin in LEAVES.items():
        raw=(ROOT/'rtl/kernel'/name).read_bytes()
        need(sha(raw) == pin,'FROZEN_SOURCE '+name)
        values[name]=raw.decode()
    lane=values['genefer_stream27_blockcarry_lane_localbase_v1.sv']
    need('wire [95:0] magnitude=coefficient[95]' in lane and
         'magnitude<={19\'d0,limit_reg}' in lane and
         '.value(coefficient[77:0])' in lane and '.MAG_W(47)' in lane and
         'logic signed [32:0] y_reg;' in lane, 'FULL_GUARD_THEN_EXISTING_NARROW_DIVIDERS')
    return dict(pins=LEAVES,
        C1='localbase carry/smallcell/canonical; setup genefer_track_a4_setup_v1',
        C2='original param carry/smallcell and canonical_image_pipe_v1, setup_param; not a localbase source inheritance',
        effective_source_widths=dict(crt_unsigned_value=79,crt_product=80,divider_magnitudes=[77,47],
            carry_first_quotient=78,carry_second_quotient=48,carry_y_and_history=33,
            carry_token=3,canonical_math=34,canonical_RAM=32,public_read=96),
        profile_scope='Exact reciprocal/A supplied by qualified shared setup. Standalone lane only checks nonzero reciprocal/bounded limit; preserve its genuine later first/parts faults, not just legal-profile math.')


def physical_report():
    raw=(ROOT/SYN).read_bytes();need(sha(raw)==SYN_PIN,'EXACT_TIMING7_SYNTHESIS_REPORT')
    rows=raw.decode().splitlines();crt=[];double=[];read=[]
    for line_number,line in enumerate(rows,1):
        match=re.search(r'arithmetic\[(\d+)\]\.crt\|coefficient\[79\.\.94\].*Merged with.*coefficient\[95\]',line)
        if match:crt.append(dict(lane=int(match.group(1)),line=line_number,text=line.strip()))
        match=re.search(r'doubled_data\[(\d+)\.\.(\d+)\].*Merged with.*doubled_data\[(\d+)\]',line)
        if match:
            lo,hi,sign=map(int,match.groups())
            if lo%96==81 and hi-lo==14 and sign==lo-1:
                double.append(dict(lane=lo//96,line=line_number,text=line.strip()))
        if 'final_image|read_data[31..94]' in line and 'read_data[95]' in line:
            read.append(dict(line=line_number,text=line.strip()))
    need(sorted(v['lane'] for v in crt)==list(range(16)) and
         sorted(v['lane'] for v in double)==list(range(16)) and len(read)==1,'ALL_LANE_SIGNEXTENSION_MERGES')
    return dict(source=SYN,sha256=SYN_PIN,stage='actual synthesis register merging, not source bitcount',
        crt_merges=crt,double_merges=double,canonical_read_merges=read,
        register_representation_upper_bounds=dict(crt_per_lane=80,double_per_lane=81,canonical_read=32),
        interpretation='Already merged high sign-extension FFs:96-to80 CRT proposes no16-register saving; exact79 CRT and80 double might each remove at most one represented bit/lane before other pruning. This is not a LAB/ALM savings prediction.',
        unresolved='Reciprocal/setup/fault-path implementation widths and packing need targeted netlist/report evidence before an RTL candidate.',
        full_width_CRT_carry_multiplier_fabric_claim=False)


def report():
    profiles=[prove_profile(aw,p) for aw in range(5,17) for p in (8,16)]
    return dict(status='PASS_MODEL_SOURCE_AND_EXISTING_REPORT_ONLY',brief='R85',
        crt=crt_bounds(),profiles=profiles,malformed_counterexamples=malformed_counterexamples(),
        source=inspect_sources(),physical=physical_report(),
        verdict='NO_BLANKET_96_TO80_AREA_CREDIT; legal proof supports typed narrowing only after full-domain guards, but current CRT/double/canonical sign extension is already largely merged',
        legal_versus_detection='Legal math widths cannot replace full signed96 coefficient magnitude/limit guard, full32 residue/range checks, full48 first/parts quotient guards or canonical34 PROCESS fault domain before narrowing. Public signed96 ABI remains.',
        divider_products='Existing source77x77=154 and47x47=94 reconstruction already limb-products/DSPs. Narrowing by legal quotient correlations must preserve malformed nonzero reciprocal first/parts faults; no blanket80bit cut is valid.',
        no_RTL_change=True,no_native_run=True,no_fullN_numeric_NTT=True,no_physical_savings_claim=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    need(not args.output.exists(),'FRESH_RESULT')
    with args.output.open('x') as stream:
        json.dump(report(),stream,indent=2);stream.write('\n')
