"""Private C2 shared-stage owner dictionary, zero public edge change."""
from copy import deepcopy
import hashlib,re
from pathlib import Path
from .stream27_comm_packed_bind import PARENT
ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_context_tagcompact_bind.py'
LEAF='rtl/kernel/genefer_stream27_mdc_commutator_tagcompact_v1.sv'
OLD='genefer_stream27_mdc_commutator_shared_mlab_v1'
NEW='genefer_stream27_mdc_commutator_tagcompact_v1'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def bind(bundle,enabled=1):
    assert type(enabled) is int and enabled in (0,1)
    b=deepcopy(bundle)
    if not enabled:return b
    assert b['parameters'].get('CONTEXTS')==2
    assert b['files'][OLD+'.sv']==(ROOT/PARENT).read_text()
    parent_files=deepcopy(b['files']);parent_pins=deepcopy(b.get('generated_sha256',{}))
    b['files'].pop(OLD+'.sv')
    changed=[]
    for n,s in list(b['files'].items()):
        t=re.sub(r'\b'+OLD+r'\b',NEW,s)
        if t!=s:changed.append(n);b['files'][n]=t
    assert len(changed) in (2,6)
    b['files'][NEW+'.sv']=(ROOT/LEAF).read_text()
    reverse={n:re.sub(r'\b'+NEW+r'\b',OLD,s) for n,s in b['files'].items() if n!=NEW+'.sv'}
    reverse[OLD+'.sv']=parent_files[OLD+'.sv']
    assert reverse==parent_files
    b['rtl_sources']=[n for n in b['files'] if n.endswith('.sv')]
    b['generated_sha256']={n:sha(s.encode()) for n,s in b['files'].items()}
    b['source_dependencies']=list(dict.fromkeys(b['source_dependencies']+[SELF,LEAF]))
    b['source_sha256']={n:sha((ROOT/n).read_bytes()) for n in b['source_dependencies']}
    b['context_tagcompact']=dict(changed=changed,parent_generated_sha256=parent_pins,
        reverse_source_exact=True,public_parameters_unchanged=True,full_tuple_bits=25,delay_tag_bits=2,local_owner_slots=2,
        added_edges=0,global_lease_reconstruction=False,native_qualification_inherited=False)
    return b
