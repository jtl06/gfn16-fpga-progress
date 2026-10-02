"""Optional CT-only fusion fragment; sole shared-generator writer is stream_core.

Apply to the qualified normalized-factored bundle. Only merged forward CT
instantiation identifiers change; GS, point/correction arithmetic, roots,
canonical spectrum boundary and both final normalization branches stay exact.

R=2^32 is unchanged. For prefix=u modP and raw in(-P,P), prefix±raw
lies(-P,2P); sign-only+P yields unsigned28<2P, congruent to old CT.
Thus stage induction preserves legal lazy inputs, and one existing subtractP
at the spectrum boundary recovers the identical canonical residue. Scalar
acceptance remains E0->E5/II1. No component-times-count field credit.
"""
from copy import deepcopy
import hashlib
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1];SELF='reference/stream27_montgomery_fused_ct_bind.py'
NEW='rtl/kernel/genefer_stream27_fused_sign_lazy28_butterfly_v1.sv';NEW_NAME='genefer_stream27_fused_sign_lazy28_butterfly_v1'
NEW_PIN='65b78b58f68dbf18d857707c4ea00b573989ed13a845dffd14e51fdf8b6720b3'
OLD='genefer_ntt_lazy28_butterfly_v1';OLD_FILE=OLD+'.sv'
OLD_PIN='ade6280dd1dac0fe3049ac2860dea7bbc7db292b634368e12f557b63865aa00d'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def need(value,why):
    if not value:raise ValueError(why)
def bind(bundle,*,CT_FUSED_REDUCTION=1):
    need(type(CT_FUSED_REDUCTION) is int and CT_FUSED_REDUCTION in (0,1),'CT_FUSED_LITERAL_FLAG')
    out=deepcopy(bundle)
    if CT_FUSED_REDUCTION==0:return out
    need('montgomery_fused_ct' not in out,'CT_FUSED_NOT_ALREADY_BOUND')
    previous=out.get('montgomery_factored',{})
    need(previous.get('flag')==1 and previous.get('R')==1<<32 and not previous.get('calendar_changed',True),'CT_FUSED_NORMALIZED_FACTORED_BASELINE')
    files=out['files'];need(type(files) is dict and all(type(t) is str for t in files.values()),'CT_FUSED_TEXT_BUNDLE')
    need(set(out['rtl_sources'])=={name for name in files if name.endswith('.sv')},'CT_FUSED_COMPILED_CLOSURE')
    need(out['generated_sha256']=={name:sha(text.encode()) for name,text in files.items()},'CT_FUSED_PARENT_HASHES')
    frozen=(ROOT/'rtl/kernel'/OLD_FILE).read_text();need(sha(frozen.encode())==OLD_PIN,'CT_FUSED_FROZEN_BF_PIN')
    needle='genefer_montgomery_mul28x27_sparse_pipe_v2'
    need(frozen.count(needle)==1,'CT_FUSED_ONE_NORMALIZED_LEAF_BINDING')
    normalized=frozen.replace(needle,'genefer_stream27_montgomery28x27_factored_v1',1)
    need(files.get(OLD_FILE)==normalized,'CT_FUSED_EXACT_NORMALIZED_BASELINE_BF')
    raw=(ROOT/NEW).read_bytes();need(sha(raw)==NEW_PIN,'CT_FUSED_QUALIFIED_LEAF_PIN')
    forward=[name for name in files if re.fullmatch(r'genefer_stream28_merged_ct_aw\d+_p\d+_f[012]_v1\.sv',name)]
    need(len(forward)==1,'CT_FUSED_ONE_FORWARD_MODULE')
    changes={};instances=0
    for name in forward:
        old=files[name];count=len(re.findall(r'\b'+OLD+r'\b',old))
        need(count>0 and old.count(".gs(1'b0)")==count and ".gs(1'b1)" not in old,'CT_FUSED_LITERAL_FORWARD_FORM')
        updated=re.sub(r'\b'+OLD+r'\b',NEW_NAME,old)
        need(re.sub(r'\b'+NEW_NAME+r'\b',OLD,updated)==old,'CT_FUSED_IDENTIFIER_ONLY_REVERSE')
        files[name]=updated;instances+=count
        changes[name]=dict(parent_sha256=sha(old.encode()),bound_sha256=sha(updated.encode()))
    # Everything else, including the normalized GS definition and last-GS
    # canonicalization/scale consumers, remains byte-identical by construction.
    files[Path(NEW).name]=raw.decode()
    out['rtl_sources']=[name for name in files if name.endswith('.sv')]
    out['source_dependencies']=list(dict.fromkeys(out['source_dependencies']+[NEW,SELF]))
    out['source_sha256']={**out['source_sha256'],NEW:NEW_PIN,SELF:sha((ROOT/SELF).read_bytes())}
    out['generated_sha256']={name:sha(text.encode()) for name,text in files.items()}
    out['montgomery_fused_ct']=dict(flag=1,leaf_sha256=NEW_PIN,identifier_changes=changes,forward_instances=instances,
      scalar_latency_edges=5,II=1,R=1<<32,public_range='unsigned28<2P; modP identical, representatives may differ byP',
      DSP_input_range='27x27 low product plus outside-DSP lazy highbit correction; rhs<P',
      GS_changed=False,point_boundary_changed=False,final_normalization_changed=False,root_tables_changed=False,
      integer_post_CRT_doubling_changed=False,calendar_changed=False,source_multiplier_delta=0,
      measured_scope='Static CT scalar component win only; no field area/timing credit or wholeP16 GO')
    return out
