"""Exact subtractive Montgomery factorization, R=2^32; no domain change."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FIELDS={104857601:(22,25),69206017:(21,33),67239937:(17,513)}
RTL='rtl/kernel/genefer_stream27_montgomery_factored_v1.sv'
def need(value,message):
    if not value:raise ValueError(message)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def reduce_product(t,p):
    need(p in FIELDS and type(t) is int and 0<=t<2*p*p,'L3_LEGAL_PRODUCT')
    k,c=FIELDS[p];d=32-k;r=1<<32;mask=(1<<d)-1;lo=t&(r-1)
    mh=((lo>>k)-c*(lo&mask))&mask
    m=(mh<<k)|(lo&((1<<k)-1))
    need(m==(lo*((2-p)&(r-1)))&(r-1),'L3_INVERSE_FACTOR')
    carry=int((lo>>k)<mh)
    q=c*(m>>d)+((c*(m&mask))>>d)+carry
    need(q==(m*p)>>32 and m*p%r==lo and q<p,'L3_EXACT_QUOTIENT')
    raw=(t>>32)-q
    need(-p<raw<p,'L3_ONE_ADD_BOUND')
    return raw if raw>=0 else raw+p
def multiply(lhs,rhs,p,*,lazy=False):
    need(p in FIELDS and type(lhs) is int and type(rhs) is int and
         0<=lhs<(2*p if lazy else p) and 0<=rhs<p,'L3_INPUT_RANGE')
    return reduce_product(lhs*rhs,p)
def ledger():return dict(schema='stream27-L3-factored-v1',R=1<<32,latency=3,II=1,
 source_variable_product='27x27 plus outside-DSP high-bit correction for lazy lhs',additional_DSP_by_source=0,
 fields={str(p):dict(K=k,C=c,D=32-k,m_high_bits=32-k,quotient_high_bits=27,
   quotient_low_product_bits=(32-k)+c.bit_length()) for p,(k,c) in FIELDS.items()},
 canonical_domain='lhs/rhs<P',lazy_domain='lhs<2P,rhs<P',output_domain='canonical lhs*rhs*R^-1 modP',
 root_tables_changed=False,physical_mapping_measured=False,ALM_saving_claim=False)
