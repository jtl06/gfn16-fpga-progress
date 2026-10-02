"""Bounded scalar final-GS proof and frozen source guard. No HDL execution."""
from pathlib import Path
import hashlib
from fpga.reference import merged_negacyclic27_model as math

ROOT=Path(__file__).resolve().parents[1]
PINS={'rtl/kernel/genefer_montgomery_mul28x27_sparse_pipe_v2.sv':
      'a93cb002eb08e585e62a847ef4b070175ae8108919da30ea5bf67dad3a597026',
      'rtl/kernel/genefer_ntt_lazy28_butterfly_v1.sv':
      'ade6280dd1dac0fe3049ac2860dea7bbc7db292b634368e12f557b63865aa00d',
      'results/throughput-20260929/lazy28-native-v2-gcp/independent-review-v1.json':
      '7fd1528af95771c7616dbbe6ac9bc28b503cfecc11816cb67df0875c069e2b55'}

def need(ok,message):
    if not ok:raise ValueError(message)

def source_guard():
    for name,pin in PINS.items():
        need(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==pin,'FINAL_GS28_SOURCE_DRIFT '+name)
    return dict(PINS)

def mont_lazy(lhs,rhs,field):
    need(type(lhs) is int and 0<=lhs<2*field.p and type(rhs) is int and 0<=rhs<field.p,'FINAL_GS28_DOMAIN')
    # Independent modular definition, NOT a transcription of sparse shifts.
    return lhs*rhs*pow(field.r,-1,field.p)%field.p

def pair(u,v,w,normalization,field,*,mutant=None):
    p=field.p
    need(type(u) is int and type(v) is int and 0<=u<2*p and 0<=v<2*p,'FINAL_GS28_DOMAIN')
    total=u+v;difference=u+2*p-v
    need(0<=total<4*p and 0<difference<4*p,'FINAL_GS28_29BIT_BOUND')
    upper=total-2*p if total>=2*p else total
    lower=difference-2*p if difference>=2*p else difference
    need(0<=upper<2*p and 0<=lower<2*p and total<(1<<29) and difference<(1<<29),'FINAL_GS28_FOLD_BOUND')
    if mutant=='truncate27':upper&=(1<<27)-1;lower&=(1<<27)-1
    elif mutant=='truncate_sum28':upper=total&((1<<28)-1)
    y0=mont_lazy(upper,normalization,field)
    y1=mont_lazy(lower,w,field)
    if mutant=='upper-unscaled':y0=total%p
    return y0,y1

def contract():
    return dict(input_domain='lazy [0,2P) residues, inverse-square R^-1 exponent preserved',
        root_domain='normalized lower psi^-e*R²/N; upper R²/N, both canonical27',
        output_domain='canonical<P ordinary residues',accepted_to_output_edges=5,
        II=1,tag='unchanged lower BF k+5 tag',upper_multiplier_latency=3,upper_payload_delay=2,
        sum_diff_width=29,fold_modulus='2P before multiplier, NOT truncate27/28',
        extra_pipes_per_final_pair=1,pointwise_28x28_admitted=False,
        native_multiplier_reviewed=True,native_BF_composition_or_final_pair_reviewed=False,
        dispatch_or_fit=False)
