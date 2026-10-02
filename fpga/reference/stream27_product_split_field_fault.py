"""Exploration-only typed witness for the one-site product carry deletion."""
import re

def validate(stdout,stderr,rc,config,assets):
    # Normal is an automatic prerequisite. Only actual in-harness data
    # comparison rejects this mutant; lint/build/crash/reset errors do not.
    if config or assets or type(rc) is not int or rc!=1 or stdout or not re.fullmatch(
        r'S4_DATA case=[0-9]+ tick=[0-9]+ lane=[0-9]+ expected=[0-9]+ actual=[0-9]+\n',stderr):
        raise ValueError('PRODUCT_SPLIT_FIELD_TYPED_FAULT')
    values=re.findall(r'(expected|actual)=([0-9]+)',stderr)
    if len(values)!=2 or values[0][1]==values[1][1]:raise ValueError('PRODUCT_SPLIT_FIELD_DISTINCT_VALUE')
    return dict(status='PASS_expected_contracts',typed_marker='S4_DATA',mutant='overlap-carry-zero',
        scope='One field arithmetic witness; not arbitrary fault or ownership coverage.',promotion_allowed=False)
