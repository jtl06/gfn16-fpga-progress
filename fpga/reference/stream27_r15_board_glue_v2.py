"""Source-bound board successor for the actually generated guarded system.

No new board ports: prove exact generated external-port equality, then reuse
the previous explicitly classified wiring with only system/top names changed.
"""
import copy
import hashlib
import re
from pathlib import Path
from . import stream27_r15_board_glue_v1 as parent

ROOT=parent.ROOT
BASE=ROOT/'results/throughput-20260929/r15-pcie-system-generation-v2-artifacts'
SYSTEM='r15_pcie_system_v2'
TOP='genefer_stream27_r15_pcie_board_v2'
GENERATED='r15_pcie_system_v2/synth/r15_pcie_system_v2.v'
PIN='b79316437846433d58e2d2c5155b54c07ddb2bf8d6d51f33501780fec7cd7082'
RECEIPT='results/throughput-20260929/r15-pcie-system-generation-v2.json'
RECEIPT_PIN='021faecadefe511c35bf277866006fb861d9079a950be3dbd30036e8f61d3fa4'


def emit():
    old,prior=parent.emit();raw=(BASE/GENERATED).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PIN or hashlib.sha256((ROOT/RECEIPT).read_bytes()).hexdigest()!=RECEIPT_PIN:
        raise ValueError('R15_BOARD_V2_GENERATED_IDENTITY')
    header=raw.decode().split('module '+SYSTEM+' (',1)[1].split('\n\t);',1)[0]
    ports=re.findall(r'\b(input|output)\s+wire\s*(?:\[(\d+):0\])?\s*(\w+)\s*[, ]',header)
    actual={name:(direction,int(hi)+1 if hi else 1) for direction,hi,name in ports}
    expected={name:(v['direction'],v['width']) for name,v in prior['ports'].items()}
    if len(ports)!=len(actual) or len(ports)!=header.count('//') or actual!=expected:
        raise ValueError('R15_BOARD_V2_EXTERNAL_PORT_DELTA')
    text=old.replace(parent.TOP,TOP).replace(parent.SYSTEM+' system_i',SYSTEM+' system_i')
    if text.replace(TOP,parent.TOP).replace(SYSTEM+' system_i',parent.SYSTEM+' system_i')!=old:
        raise ValueError('R15_BOARD_V2_WIRING_REVERSE')
    result=copy.deepcopy(prior)
    result.update(schema='r15-board-static-wiring-v2',top=TOP,system_top=SYSTEM,
      generated_top_path=str((BASE/GENERATED).relative_to(ROOT)),generated_top_sha256=PIN,
      generation_receipt=RECEIPT,generation_receipt_sha256=RECEIPT_PIN,
      source_sha256=hashlib.sha256(text.encode()).hexdigest(),
      predecessor_wiring_sha256=prior['source_sha256'],external_ports_exactly_unchanged=True,
      automatic_link_retrain_or_FLR_reset_claim=False,
      reconnect_contract='Explicit common reset plus both-domain drain and DMA arena teardown; hardware reset delivery not bound to VFIO/FLR/software.')
    return text,result
