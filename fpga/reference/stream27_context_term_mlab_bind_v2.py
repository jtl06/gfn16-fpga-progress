"""MLAB numeric write guard successor: explicit original reset-ELSE hold.

V1 snapshots/results preserved. Same RAM/read/E4/owner/row/valid/A/B logic;
only numeric write_enable includes rst_n for simultaneous reset/clock edges.
"""
import hashlib
from . import stream27_context_term_mlab_bind as parent

ROOT=parent.ROOT
SELF='reference/stream27_context_term_mlab_bind_v2.py'
RAM,TERM,NEW=parent.RAM,parent.TERM,parent.NEW
captured=parent.captured
PARENT_PIN='bf8a3c99329871e7764dc04cce4bb8d2580372232e38594867ef6a21601fa0d4'
sha=parent.sha


def term(text):
    captured.need(hashlib.sha256((ROOT/parent.SELF).read_bytes()).hexdigest()==PARENT_PIN,'MLAB_V2_FROZEN_BINDER')
    return captured.binder.parent.once(parent.term(text),
        'wire payload_write=!stop && product_slot && bank_owner[prod_bank]==product_owner;',
        'wire payload_write=rst_n && !stop && product_slot && bank_owner[prod_bank]==product_owner;')


def bind(bundle,*,enabled=0):
    result=parent.bind(bundle,enabled=enabled)
    if not enabled:return result
    result['files'][NEW+'.sv']=captured.binder.parent.once(result['files'][NEW+'.sv'],
        'wire payload_write=!stop && product_slot && bank_owner[prod_bank]==product_owner;',
        'wire payload_write=rst_n && !stop && product_slot && bank_owner[prod_bank]==product_owner;')
    result['generated_sha256']={name:sha(text) for name,text in result['files'].items()}
    result['term_mlab'].update(write_reset_else_exact=True,version=2,
        eligible_write='rst_n && !stop && product_slot && bank_owner[prod_bank]==product_owner',
        preserved_unqualified_v1=True)
    return result
