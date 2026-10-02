"""Exact representative harness reuse; only generated model/header names change."""
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PARENT='rtl/tb/track_a4_core_representative_v2.cpp'
PIN='b4a5c29e9927fc22f3e49dabfd1506fce7829d12ffc381003bf9d5aeb562b565'
CHILD='rtl/tb/track_anext_core_representative_v1.cpp'

def expected():
    raw=(ROOT/PARENT).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('frozen A4b representative harness drift')
    return raw.decode().replace('genefer_track_a4_core_v4','genefer_anext_core_v1')

def verify():
    if (ROOT/CHILD).read_text()!=expected():raise ValueError('A-next representative exact top-only delta')
    return dict(recipe_changes=0,arithmetic_checks_changed=False,top='genefer_anext_core_v1')
