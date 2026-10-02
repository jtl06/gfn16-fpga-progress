"""Small-N A10 merged fields + centered CRT + exact A4 blockcarry composition.

Only N<=256 numerical work is permitted here. Reuses the frozen arithmetic;
independent signed-schoolbook and whole-integer oracles live in the tests.
"""
from fpga.reference import merged_negacyclic27_model as field
from fpga.reference import merged_negacyclic27_issue_model_v1 as banked
from fpga.reference import track_a4_blockcarry_model as carry


def square(state,double_bit=0):
    n=len(state.digits)
    if n not in (32,64,128,256):raise ValueError('ANEXT_SMALL_NUMERIC_ONLY')
    if type(double_bit) is not int or double_bit not in (0,1):raise ValueError('ANEXT_DOUBLE_BIT')
    proof=carry.bounds(n,state.base)
    # Equivalent to separate digit/c0/c1 reduction and modular patch addition.
    planes=carry.patch_residues(state)
    residues=[banked.banked_square(values,prime,lanes=64,input_exponent=0)
              for values,prime in zip(planes,field.FIELDS)]
    coefficients=[]
    for triple in zip(*residues):
        value=sum(r*w for r,w in zip(triple,field.CRT_WEIGHTS))%field.MODULUS
        centered=value-field.MODULUS if value>field.HALF else value
        coefficients.append(centered<<double_bit)
    if any(abs(x)>proof['doubled_coefficient_bound'] for x in coefficients):
        raise ValueError('ANEXT_CENTERED_COEFFICIENT_BOUND')
    result,statistics=carry.arithmetic.proposal.carry_split(coefficients,state.base,16)
    return result,dict(coefficients=coefficients,statistics=statistics,
        domain='ordinary residues -> centered signed CRT -> integer doubling -> redundant block digits',
        native_validated=False)
