"""A4b/v4 representative harness: exact v3 bench with top/header rename only."""
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PARENT='rtl/tb/track_a4_core_representative_v1.cpp'
PIN='897e1ffd8edc174cc9ce60eccb211d3540d749b78cabfd43cca7c0cacb12f206'
CHILD='rtl/tb/track_a4_core_representative_v2.cpp'

def successor():
    raw=(ROOT/PARENT).read_bytes();assert hashlib.sha256(raw).hexdigest()==PIN
    return raw.decode().replace('genefer_track_a4_core_v3','genefer_track_a4_core_v4')

def verify():
    assert (ROOT/CHILD).read_text()==successor()
    return dict(arithmetic_or_recipe_change=False,top='genefer_track_a4_core_v4',
        model_threads=1,native_only_AW16=True)
