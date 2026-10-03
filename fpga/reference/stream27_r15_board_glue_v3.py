"""Same board wiring rebound to actual registered-credit system generation.

The generated top must remain byte-identical. A changed top requires a new
wiring analysis, never an assumed port-name match or a vendor simulation claim.
"""
import copy
import hashlib
import json
from . import stream27_r15_board_glue_v2 as parent

ROOT=parent.ROOT
BASE=ROOT/'results/throughput-20260929/r15-pcie-system-generation-v3-artifacts'
SYSTEM,TOP,GENERATED,PIN=parent.SYSTEM,parent.TOP,parent.GENERATED,parent.PIN
RECEIPT='results/throughput-20260929/r15-pcie-system-generation-v3.json'
RECEIPT_PIN='d2f0e2b60e7926186efdb4c9b3ffacfd8672c218378d507b4ab56dcf24906ef7'
INPUT_PIN='46eb0869ccc014ce5174bb9b5b36fe2fe6a8b868b6fb4fda44480fa3d9cf4a57'

def emit():
    text,prior=parent.emit()
    raw=(BASE/GENERATED).read_bytes();receipt=(ROOT/RECEIPT).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PIN or hashlib.sha256(receipt).hexdigest()!=RECEIPT_PIN:
        raise ValueError('R15_BOARD_V3_ACTUAL_GENERATED_IDENTITY')
    r=json.loads(receipt)
    if r['input_manifest_sha256']!=INPUT_PIN or type(r['returncode']) is not int or r['returncode']!=0:
        raise ValueError('R15_BOARD_V3_GENERATION_RESULT')
    for command in json.loads(r['stdout'])['results']:
        if type(command['returncode']) is not int or command['returncode']!=0:
            raise ValueError('R15_BOARD_V3_GENERATION_COMMAND')
    result=copy.deepcopy(prior)
    result.update(schema='r15-board-static-wiring-v3',
      generated_top_path=str((BASE/GENERATED).relative_to(ROOT)),
      generation_receipt=RECEIPT,generation_receipt_sha256=RECEIPT_PIN,
      generated_top_byte_identical_to_prior=True,
      scope='Actual generation3 source/wiring association only; no fit, clock or board qualification.')
    return text,result
