"""Private CT-only fused reduction on the composed P16 factored donor.

Zero is a complete exact deep copy. One changes only forward CT instances;
the current GS/final-pair, correction, square, roots, arithmetic domain and
all calendars stay byte-exact. No shared-generator writer or area credit.
"""
from copy import deepcopy
import hashlib
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_l3b_ct_bind.py'
OLD='genefer_ntt_lazy28_butterfly_v1'
OLD_FILE=OLD+'.sv'
OLD_SOURCE='rtl/kernel/'+OLD_FILE
OLD_PIN='ade6280dd1dac0fe3049ac2860dea7bbc7db292b634368e12f557b63865aa00d'
FROZEN='rtl/kernel/genefer_stream27_fused_sign_lazy28_butterfly_v1.sv'
FROZEN_PIN='65b78b58f68dbf18d857707c4ea00b573989ed13a845dffd14e51fdf8b6720b3'
NEW='rtl/kernel/genefer_stream27_l3b_ct_fused_v1.sv'
TOP='genefer_stream27_l3b_ct_fused_v1'
RAW='genefer_stream27_l3b_ct_raw_v1'
DIET=dict(CORR_SERIAL_BFS=2,COMM_STAGE_SHARED_MLAB=1,MONT_FACTORED=1)


def sha(raw):return hashlib.sha256(raw).hexdigest()
def need(ok,label):
    if not ok:raise ValueError('L3B_CT_'+label)


def verify_leaf():
    old=(ROOT/FROZEN).read_bytes()
    need(sha(old)==FROZEN_PIN,'FROZEN_SIGN_LEAF')
    raw=(ROOT/NEW).read_bytes()
    expected=old.decode().replace('genefer_stream27_fused_sign_lazy28_butterfly_v1',TOP).replace(
        'genefer_stream27_montgomery28x27_raw_sign_pipe_v1',RAW)
    need(raw.decode()==expected,'PRIVATE_LEAF_IDENTIFIER_ONLY')
    return raw


def bind(bundle,*,enabled=0):
    need(type(enabled) is int and enabled in (0,1),'LITERAL_ENABLE')
    b=deepcopy(bundle)
    if not enabled:return b
    need(not b.get('l3b_ct_fused'),'NOT_ALREADY_BOUND')
    need(b['parameters']['P']==16 and b['parameters']['CONTEXTS']==1 and
         all(b['parameters'].get(key)==value for key,value in DIET.items()),'EXACT_COMPOSED_DONOR')
    need(set(b['rtl_sources'])=={name for name in b['files'] if name.endswith('.sv')} and
         b['generated_sha256']=={name:sha(text.encode()) for name,text in b['files'].items()},'CLOSED_PARENT')
    old=(ROOT/OLD_SOURCE).read_bytes()
    need(sha(old)==OLD_PIN,'FROZEN_NORMALIZED_BUTTERFLY')
    normalized=old.decode().replace('genefer_montgomery_mul28x27_sparse_pipe_v2',
        'genefer_stream27_montgomery28x27_factored_v1')
    need(b['files'].get(OLD_FILE)==normalized,'EXACT_FACTORED_NORMALIZED_BUTTERFLY')
    matches=[name for name in b['files'] if re.fullmatch(
        r'genefer_stream28_merged_ct_aw(?:5|8|16)_p16_f[012]_v1_shared_comm_mlab_v1\.sv',name)]
    need(len(matches)==1,'ONE_MAIN_CT_TRANSFORM')
    name=matches[0];before=b['files'][name]
    count=len(re.findall(r'\b'+OLD+r'\b',before))
    need(count>0 and before.count(".gs(1'b0)")==count and ".gs(1'b1)" not in before,'ALL_LITERAL_CT_INSTANCES')
    after=re.sub(r'\b'+OLD+r'\b',TOP,before)
    need(re.sub(r'\b'+TOP+r'\b',OLD,after)==before,'CT_IDENTIFIER_ONLY_REVERSE')
    b['files'][name]=after
    leaf=verify_leaf();b['files'][Path(NEW).name]=leaf.decode()
    need(all(b['files'][key]==value for key,value in bundle['files'].items() if key!=name),'ALL_NON_CT_BYTES_PRESERVED')
    b['rtl_sources']=[key for key in b['files'] if key.endswith('.sv')]
    b['generated_sha256']={key:sha(text.encode()) for key,text in b['files'].items()}
    b['source_dependencies']=list(dict.fromkeys(b['source_dependencies']+[SELF,NEW,FROZEN]))
    b['source_sha256']={**b['source_sha256'],**{path:sha((ROOT/path).read_bytes()) for path in (SELF,NEW,FROZEN)}}
    b['l3b_ct_fused']=dict(enabled=1,forward_module=name,instances=count,
        parent_sha256=sha(before.encode()),candidate_sha256=sha(after.encode()),
        frozen_scalar_leaf_sha256=FROZEN_PIN,private_leaf_sha256=sha(leaf),
        R=1<<32,latency_edges=5,II=1,public_range='unsigned28<2P; modP equality, lazy representative may differ byP',
        GS_changed=False,final_normalization_changed=False,point_changed=False,correction_changed=False,
        reset_policy_changed=False,roots_changed=False,calendar_changed=False,
        scalar_area_not_field_credit=True,field_LAB_measured=False,whole_GO=False,
        scope='CT-only current composed-diet field experiment; prior GS area loser is not bound. Native and matched field resources required.')
    return b
