"""Stdlib-only source-pinned numeric witness for the one zero-CT mutant."""
import re


def need(ok,label):
    if not ok:raise ValueError('L3B_CT_FAULT_'+label)


def validate(stdout,stderr,returncode,config,assets):
    need(type(config) is dict and config==dict(aw=8,p=16,field=0,mutant='zero-ct-sum')
         and all(type(config[key]) is int for key in ('aw','p','field')) and assets=={},'CONFIG')
    need(type(returncode) is int and returncode==1 and stdout=='' and type(stderr) is str,'TYPED_EXIT')
    match=re.fullmatch(r'S4_DATA case=([0-6]) tick=([0-9]+) lane=([0-9]+) expected=([0-9]+) actual=([0-9]+)\n',stderr,re.ASCII)
    need(match is not None,'NUMERIC_WITNESS')
    case,tick,lane,expected,actual=map(int,match.groups())
    # Exact N256 composed-diet calendar: physical150/sink151/interval212.
    need(0<=lane<16 and 150<=tick<3*212+151+16 and
         0<=expected<104857601 and 0<=actual<104857601 and expected!=actual,'VALUE_RANGE')
    return dict(status='PASS_expected_contracts',case=case,tick=tick,lane=lane,
        expected=expected,actual=actual,mutant='zero-ct-sum',promotion_allowed=False)
