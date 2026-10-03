"""Private default-OFF registered-value FOLD edge; no whole integration."""
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SELF='reference/stream27_r15_canonical_foldstage_bind.py'
CAPTURE='results/throughput-20261003/trackS-r15-storage-ram-v1/aw8-normal/source/fpga/rtl/genefer_stream27_canonical_image_foldpayload100_v1.sv'
PARENT_SHA256='e07ccea57740154b803d9b4c4e85e456e280d61ca6f24d455834413dee02a234'
OLD='genefer_stream27_canonical_image_foldpayload100_v1'
NEW='genefer_stream27_canonical_image_foldstage_r15_v1'

def sha(text):return hashlib.sha256(text.encode()).hexdigest()
def need(ok,label):
    if not ok:raise ValueError('R15_CANON_FOLDSTAGE_'+label)

def parent():
    text=(ROOT/CAPTURE).read_text();need(sha(text)==PARENT_SHA256,'EXACT_CAPTURE');return text

def edits(text):
    start='        // Compute the complete next PROCESS payload in the existing VALUE edge.\n'
    end='        fold_q=fold_q_payload;remainder=fold_remainder_payload;\n'
    need(text.count(start)==1 and text.count(end)==1,'FOLD_REGION')
    block=text[text.index(start):text.index(end)]
    newblock=block.replace(start,'        // FOLD consumes only the registered VALUE token.\n').replace('value_next','value')
    oldvalue='''                VALUE_WORD:begin
                    value<=value_next;stored_digit_bad<=pass_index==0 && ram_q[bank]>=base_reg;
                    fold_q_payload<=fold_q_pre;fold_remainder_payload<=fold_remainder_pre;
                    fold_range_payload<=fold_range_pre;
                    state<=PROCESS_WORD;
                end
'''
    newvalue='''                VALUE_WORD:begin
                    value<=value_next;stored_digit_bad<=pass_index==0 && ram_q[bank]>=base_reg;
                    state<=FOLD_WORD;
                end
                FOLD_WORD:begin
                    fold_q_payload<=fold_q_pre;fold_remainder_payload<=fold_remainder_pre;
                    fold_range_payload<=fold_range_pre;
                    state<=PROCESS_WORD;
                end
'''
    return [('module '+OLD+' #','module '+NEW+' #'),
      ('// Registered value boundary: three edges/digit, 9N normal / 10N special.','// Registered VALUE then FOLD: four edges/digit, 12N normal / 13N special.'),
      ('{IDLE,READ_WORD,VALUE_WORD,PROCESS_WORD,SPECIAL_WRITE,FAILED}',
       '{IDLE,READ_WORD,VALUE_WORD,PROCESS_WORD,SPECIAL_WRITE,FAILED,FOLD_WORD}'),
      (block,newblock),(oldvalue,newvalue)]

def bind_leaf(text,*,enabled=0):
    need(type(enabled) is int and enabled in (0,1),'BOOLEAN')
    if not enabled:return text
    need(sha(text)==PARENT_SHA256,'PARENT_PIN')
    original=text
    for before,after in edits(original):
        need(text.count(before)==1,'UNIQUE_ANCHOR');text=text.replace(before,after,1)
    need(reverse_leaf(text)==original,'EXACT_REVERSE')
    return text

def reverse_leaf(text):
    original=parent()
    for before,after in reversed(edits(original)):
        need(text.count(after)==1,'REVERSE_ANCHOR');text=text.replace(after,before,1)
    return text

def service(n,special=False,enabled=1):
    need(n in (256,65536) and enabled in (0,1),'SERVICE_GEOMETRY')
    return ((12 if enabled else 9)+int(special))*n
