"""R87B bounded ingress graph/algebra study, not an RTL binding.

The existing CT upper branch has no multiplier. A direct wide REDC may replace
the lower branch's pre-reduction, but it does not eliminate the upper reduction
or preserve the signed -1/fault/calendar contract by itself.
"""
import hashlib
from .stream_ntt_model import FIELDS

R = 1 << 32
RAW_MAX = 999999999


def redc_unsigned(product, prime):
    if not 0 <= product < prime * R:
        raise ValueError('R87B_REDC_BOUND')
    m = product * pow(prime,-1,R) % R
    difference = product - m * prime
    assert difference % R == 0
    signed = difference // R
    assert -prime < signed < prime
    return signed + prime if signed < 0 else signed


def split30(value, rhs):
    if not 0 <= value < (1 << 30) or not 0 <= rhs < (1 << 27):
        raise ValueError('R87B_PARTIAL_PRODUCT_RANGE')
    return (value & ((1 << 27)-1)) * rhs + ((value >> 27) * rhs << 27)


def current_ct_bypass_counterexample(prime):
    raw_upper = 3 * prime
    assert raw_upper <= RAW_MAX
    represented = raw_upper & ((1 << 28)-1)
    upper = represented - prime if represented >= prime else represented
    return dict(raw_upper=raw_upper,lower=0,
                expected=(0,prime),bypass=(upper,upper+prime),
                truncated=represented!=raw_upper,
                residue_mismatch=upper%prime!=0,
                lazy_range_failure=upper>=2*prime or upper+prime>=2*prime)


def graph(bundle, field=0):
    """Inspect already-emitted C2 production bytes; no new emitter/HDL run."""
    if bundle['parameters']['P']!=16 or bundle['parameters']['CONTEXTS']!=2:
        raise ValueError('R87B_EXACT_C2_P16_GRAPH')
    files=bundle['files']
    field_name=next(n for n in files if n.startswith('genefer_stream27_shared_warm_')
                    and '_f'+str(field)+'_' in n)
    field_text=files[field_name]
    ct_name=next(n for n in files if n.startswith('genefer_stream28_merged_ct_')
                 and '_f'+str(field)+'_' in n)
    ct=files[ct_name]
    first=ct[ct.index(' if(1)begin: stage0'):ct.index(' if(1)begin: stage1')]
    bf=files['genefer_ntt_lazy28_butterfly_v1.sv']
    assert '.data_in(input_wide)' in field_text
    assert 'digit_residue[26:0]' in field_text
    # The correction twist is not a second multiplier for each input digit.
    twist=field_text[field_text.index(' small_twist ('):]
    twist=twist[:twist.index(');')]
    assert '.lhs(boundary_data)' in twist
    assert first.count(".gs(1'b0)")==8
    assert 'pre_v<=gs ? gs_diff_fold : v;' in bf
    assert "ct_u=u>=28'(P) ? u-28'(P) : u;" in bf
    assert 'lhs(pre_v)' in bf and 'rhs(pre_w)' in bf
    return dict(field=field,field_source=field_name,ct_source=ct_name,
                field_sha256=hashlib.sha256(field_text.encode()).hexdigest(),
                first_pair_count=8,upper_multipliers=0,lower_multipliers=8,
                input='raw32 -> digit reducer -> canonical27 -> CT28',
                correction_twist_only=True,current_mont_product_bits=55,
                public_calendar_or_fault_change=False)


def study():
    return dict(status='MODEL_ONLY_LITERAL_REDUCER_DELETION_REJECTED',
                primes=[dict(prime=p,raw30_product_bits=(RAW_MAX*(p-1)).bit_length(),
                             counterexample=current_ct_bypass_counterexample(p),
                             minus_one_unsigned_alias=(R-1)%p,
                             minus_one_expected=p-1)
                        for p,_ in FIELDS],
                lower_reduction='Unsigned raw30 times canonical root satisfies t<P*2^32; exact27low+3high partial products need56–57 product bits.',
                missing='Current first CT multiplies only lower input. Upper branch needs a proved reduction or new identity multiply; -1 classification/full input errors and original tags/calendar must remain.',
                claim='No RTL/native/area saving or automatic digit-reducer bypass.')
