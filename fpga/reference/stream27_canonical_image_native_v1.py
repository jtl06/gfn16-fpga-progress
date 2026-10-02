"""Exact source and typed finite contracts for standalone S4 readback barrier."""
import hashlib
from pathlib import Path

from fpga.reference import stream27_canonical_image_model_v1 as model

ROOT = Path(__file__).resolve().parents[1]
TOP = 'genefer_stream27_canonical_image_v1'
SV = 'rtl/kernel/' + TOP + '.sv'
CPP = 'rtl/tb/stream27_canonical_image_v1.cpp'
RAM = 'rtl/kernel/genefer_sdp_ram32.sv'
PINS = {
    SV: 'c6e59a385ed187dceb9b392c096cc1d7cfc5a71ba820326b9b441f1df8093e74',
    CPP: '231ac7755294923f5dfa5b43631226a8907e1c87d049381200c068b45e9ef8e0',
    RAM: '993567fb68fdc216b9ff04489d1810f743b86564434e4b48261ad606b25d53b0',
    'reference/stream27_canonical_image_model_v1.py': '291fe38581d39b2a84c76384c677c7f4e0f9f2626bf7e56139a86238f500c095',
}


def sha(raw):return hashlib.sha256(raw).hexdigest()


def verify(root=ROOT):
    for name,pin in PINS.items():
        path=Path(root)/name
        model.need(path.is_file() and not path.is_symlink() and sha(path.read_bytes())==pin,
                   'CANON_SOURCE_DRIFT '+name)
    return dict(PINS)


def contracts(aw,p):
    model.need(aw in (5,8) and type(aw) is int and p in (8,16) and type(p) is int,'CANON_NATIVE_SMALL_GEOMETRY')
    g=model.geometry(aw,p);n=g['n'];extra=int(g['t']>2)
    counts=dict(cases=173+2*extra,reads=(112+extra)*n+2,normal=108+extra,special=4,
                cycles=(676+6*extra)*n)
    positive=f'CANON_IMAGE_PASS aw={aw} p={p} '+ ' '.join(f'{k}={v}' for k,v in counts.items())+'\n'
    # The native negative changes just the expected middle digit of the first
    # natural-order trial. Raw RAM/corrections/DUT arithmetic are unchanged.
    j=n//2;base=g['minimum_base'];actual=(j*104729+(j//g['t'])*31+17)%base
    negative=(f'CANON_IMAGE_NEGATIVE_ORACLE_REJECT aw={aw} p={p} '
              f'case=natural_block_order_b{base} address={j} expected={actual+1} actual={actual}\n')
    return dict(counts=counts,normal=dict(returncode=0,stdout=positive,stderr=''),
                negative=dict(returncode=1,stdout='',stderr=negative))


def validate(stdout,stderr,returncode,config,assets):
    model.need(set(config)=={'aw','p','negative'} and type(config['negative']) is bool and assets=={},'CANON_NATIVE_CONFIG')
    expected=contracts(config['aw'],config['p'])['negative' if config['negative'] else 'normal']
    model.need((stdout,stderr,returncode)==(expected['stdout'],expected['stderr'],expected['returncode']),
               'CANON_NATIVE_TYPED_OUTPUT')
    return dict(status='PASS_expected_contracts',aw=config['aw'],p=config['p'],
                negative=config['negative'],promotion_allowed=False)
