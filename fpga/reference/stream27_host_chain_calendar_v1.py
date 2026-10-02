"""Source-pinned modular calendar proof; event arithmetic, never a numeric NTT."""
import hashlib
from .stream27_shared_field_v2 import ROOT,geometry

PROTOCOL='rtl/kernel/genefer_stream27_epoch_protocol_v5.sv'
PIN='a01f6b93200d4ee5d1eb7e81664cfd89e373a447e9cbf5173387188f1212df45'


def check(n,p):
    if hashlib.sha256((ROOT/PROTOCOL).read_bytes()).hexdigest()!=PIN:raise ValueError('PROTOCOL_SOURCE_DRIFT')
    g=geometry(n,p);modulus=1<<32;rows=n//p
    horizon=g['sink_accept']+rows-1
    if not 0<rows<modulus//2 or not 0<horizon<modulus//2:raise ValueError('LEASE_HORIZON')
    # Before its deadline the modular age is M-distance, never a small row.
    # During the window, both ordinary and modulo32 differences equal row.
    # The owner is retired intrinsically on its actual last sink row.
    starts=(0,modulus-horizon-1,modulus-g['pointwise_accept']+1,modulus-1,modulus+7,3*modulus-1)
    witnesses=0
    for start in starts:
        for first in (g['pointwise_accept'],g['sink_accept']):
            deadline=start+first
            for delta in (-first,-1,0,1,rows-1,rows):
                edge=deadline+delta;age=((edge%modulus)-(deadline%modulus))%modulus
                expected=0<=delta<rows
                if (age<rows)!=expected:raise ValueError('CALENDAR_COUNTEREXAMPLE')
                witnesses+=1
    return dict(n=n,p=p,lease_horizon=horizon,witnesses=witnesses,
      modulo32_reason='For active owner age interval[-first,rows-1], future negative ages map to M-first..M-1>=rows; due rows map exactly0..rows-1. Last actual sink retires owner before stale age could repeat.',
      maximum_job_cycles=102+(0xffffffff-1)*g['warm_interval']+g['carry_done']+2+7*n+n+4,
      protocol_sha256=hashlib.sha256((ROOT/PROTOCOL).read_bytes()).hexdigest(),scope='Source/event math only, not native wrap or fullN numeric evidence')
