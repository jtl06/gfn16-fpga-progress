"""Private product-register split; never edits the shared field generator."""
from copy import deepcopy
import hashlib
from pathlib import Path
from . import stream27_l3_factored_model_v1 as model

ROOT=model.ROOT
PARENT=model.RTL
PARENT_PIN='866c2b19c9e6afbbb56ce71089288334579f90e977ca139b41097d0f9191c690'
RTL='rtl/kernel/genefer_stream27_product_split_v1.sv'
SELF='reference/stream27_product_split.py'
NAMES={
    'genefer_stream27_montgomery_factored_core_v1':'genefer_stream27_product_split_core_v1',
    'genefer_stream27_montgomery_factored_v1':'genefer_stream27_product_split_v1',
    'genefer_stream27_montgomery28x27_factored_v1':'genefer_stream27_product_split_lazy_v1',
}

def need(ok,label):
    if not ok:raise ValueError('PRODUCT_SPLIT_'+label)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def reconstruct(lhs,rhs,p):
    need(p in model.FIELDS and type(lhs) is int and type(rhs) is int and 0<=lhs<2*p and 0<=rhs<p,'RANGE')
    product=(lhs&((1<<27)-1))*rhs
    high_rhs=rhs if lhs>>27 else 0
    overlap=((product>>27)&31)+(high_rhs&31)
    low=(product&((1<<27)-1))|((overlap&31)<<27)
    high=(product>>32)+(high_rhs>>5)+(overlap>>5)
    need(0<=low<1<<32 and 0<=high<1<<23 and low+(high<<32)==lhs*rhs,'IDENTITY')
    return low,high

def multiply(lhs,rhs,p):
    low,high=reconstruct(lhs,rhs,p)
    return model.reduce_product(low+(high<<32),p)

def verify_source():
    """Reverse every declared product delta; untouched REDC/reset/API exact."""
    parent=(ROOT/PARENT).read_text();text=(ROOT/RTL).read_text()
    need(sha(parent.encode())==PARENT_PIN,'FROZEN_PARENT')
    for old,new in NAMES.items():text=text.replace(new,old)
    start=text.index('module ');text=parent[:parent.index('module ')]+text[start:]
    replacements=[
        ('    logic [53:0] product_s1;\n    logic [26:0] high_rhs_s1;','    logic [54:0] ab_s1;'),
        ("    // Only five overlapping low bits; carry crosses the 32-bit boundary.\n    wire [5:0] overlap_sum={1'b0,product_s1[31:27]}+{1'b0,high_rhs_s1[4:0]};\n    wire [31:0] lo={overlap_sum[4:0],product_s1[26:0]};\n    wire [22:0] reconstructed_hi={1'b0,product_s1[53:32]}+\n        {1'b0,high_rhs_s1[26:5]}+23'(overlap_sum[5]);",
         "    wire [54:0] high_product=lhs[27] ? {1'b0,rhs,27'b0} : 55'b0;\n    wire [54:0] full_product={1'b0,low_product}+high_product;\n    wire [31:0] lo=ab_s1[31:0];"),
        ('product_s1<=0;high_rhs_s1<=0;','ab_s1<=0;'),
        ("            if(in_valid)begin\n                product_s1<=low_product;\n                high_rhs_s1<=lhs[27] ? rhs : 27'b0;\n            end",'            if(in_valid)ab_s1<=full_product;'),
        ('hi_s2<=reconstructed_hi;','hi_s2<=ab_s1[54:32];'),
        ('// Same exact overflow compare as the factored parent.','// m and lo have identical lowK bits, so the overflow compare is D bits.'),
    ]
    for old,new in replacements:
        need(text.count(old)==1,'REVERSE_SITE');text=text.replace(old,new)
    need(text==parent,'REVERSE_FULL_SOURCE')
    return {'parent_sha256':PARENT_PIN,'candidate_sha256':sha((ROOT/RTL).read_bytes()),
        'latency':3,'II':1,'reset':'unchanged async numeric+valid/output resets',
        'declared_product_storage_bits':81,'declared_parent_product_bits':55,
        'mapping_or_savings_claim':False}

def bind(bundle,*,enabled=0):
    need(type(enabled) is int and enabled in (0,1),'ENABLE');b=deepcopy(bundle)
    if not enabled:return b
    need(not b.get('product_split') and b['parameters']['P']==16 and b['parameters']['CONTEXTS']==1
         and all(b['parameters'].get(k)==v for k,v in
             dict(CORR_SERIAL_BFS=2,COMM_STAGE_SHARED_MLAB=1,MONT_FACTORED=1).items()),'EXACT_COMPOSED_FIELD')
    need(b['generated_sha256']=={n:sha(t.encode()) for n,t in b['files'].items()},'CLOSED_PARENT')
    need(b['files'].get(Path(PARENT).name)==(ROOT/PARENT).read_text(),'PARENT_LEAF_BYTES')
    proof=verify_source();leaf=Path(RTL).name;changed=[]
    lazy='genefer_stream27_montgomery28x27_factored_v1'
    for name,text in list(b['files'].items()):
        if name==Path(PARENT).name:continue
        # Canonical root/square/CRT/general callers remain the original leaf.
        replacement=text.replace(lazy,NAMES[lazy])
        if replacement!=text:changed.append(name);b['files'][name]=replacement
    need(changed,'REAL_CONSUMERS')
    # Preserve original definitions for CRT/general callers: no global leaf overwrite.
    b['files'][leaf]=(ROOT/RTL).read_text();b['rtl_sources'].append(leaf)
    b['generated_sha256']={n:sha(t.encode()) for n,t in b['files'].items()}
    b['source_dependencies']=list(dict.fromkeys(b['source_dependencies']+[SELF,RTL]))
    b['source_sha256']={**b['source_sha256'],SELF:sha((ROOT/SELF).read_bytes()),RTL:sha((ROOT/RTL).read_bytes())}
    b['product_split']={**proof,'enabled':1,'changed_consumers':changed,'lazy_only':True,
        'canonical_consumers_unchanged':True,'calendar_or_reset_changed':False}
    return b
