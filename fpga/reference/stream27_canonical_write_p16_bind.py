"""Private zero-edge LOAD eligibility factoring; no shared compiler edits."""
import copy
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OLD='genefer_stream27_canonical_image_localbase_v1'
NEW='genefer_stream27_canonical_image_write_local_v1'
PARENT='87264ca12a08cdf4b905ffdcc27d066b25333c0f0283904ac0cf9d36f707d70d'
READY='2026-10-02T02:44:02Z'
def sha(raw):return hashlib.sha256(raw).hexdigest()

def bind(bundle,enabled=1):
    assert enabled in (0,1)
    b=copy.deepcopy(bundle)
    if not enabled:return b
    assert sha(b['files'][OLD+'.sv'].encode())==PARENT
    old=b['files'].pop(OLD+'.sv')
    new=(ROOT/'rtl/kernel'/f'{NEW}.sv').read_text()
    for name,s in list(b['files'].items()):b['files'][name]=s.replace(OLD,NEW)
    b['files'][NEW+'.sv']=new
    b['rtl_sources']=[NEW+'.sv' if n==OLD+'.sv' else n for n in b['rtl_sources']]
    b['generated_sha256']={n:sha(s.encode()) for n,s in b['files'].items()}
    b['canonical_write_local']=dict(parent_sha256=sha(old.encode()),added_edges=0,
        private_leaf=NEW,authoritative_fault_priority_unchanged=True)
    return b
