"""Default-OFF fold payload partition in the existing VALUE edge.

Only exact protected timing10 canonical source is accepted. No address,
public port, rejection priority, state transition or external edge changes.
PROCESS consumes one coherent fold/remainder/range tuple captured by VALUE.
"""
import hashlib
from . import stream27_canonical_fold_payload_model as model

SELF='reference/stream27_canonical_fold_payload_bind.py'
MODEL='reference/stream27_canonical_fold_payload_model.py'
PARENT_SHA256='15ff49bc9542b4cb63393d73e76c8e10e0b2a8791d677dda7fdad6f1c567e2d4'
OLD='genefer_stream27_canonical_image_timing10_v1'
NEW='genefer_stream27_canonical_image_foldpayload100_v1'


def sha(text):return hashlib.sha256(text.encode()).hexdigest()
def need(ok,label):
    if not ok:raise ValueError('CANONICAL_FOLD_PAYLOAD_'+label)


def edits():
    return [
        ('module '+OLD+' #','module '+NEW+' #'),
        ('    logic stored_digit_bad; // Payload need not reset; PROCESS follows VALUE eligibility.\n',
         '    logic stored_digit_bad; // Payload need not reset; PROCESS follows VALUE eligibility.\n'
         '    logic signed [2:0] fold_q_pre,fold_q_payload;\n'
         '    logic signed [33:0] fold_remainder_pre,fold_remainder_payload;\n'
         '    logic fold_range_pre,fold_range_payload;\n'),
        ('''        if(value>=two_base)begin fold_q=3'sd2;remainder=value-two_base;end
        else if(value>=base_ext)begin fold_q=3'sd1;remainder=value-base_ext;end
        else if(value>=0)begin fold_q=3'sd0;remainder=value;end
        else if(value>=negative_base)begin fold_q=-3'sd1;remainder=value+base_ext;end
        else begin fold_q=-3'sd2;remainder=value+two_base;end
''',
         '''        // Compute the complete next PROCESS payload in the existing VALUE edge.
        if(value_next>=two_base)begin fold_q_pre=3'sd2;fold_remainder_pre=value_next-two_base;end
        else if(value_next>=base_ext)begin fold_q_pre=3'sd1;fold_remainder_pre=value_next-base_ext;end
        else if(value_next>=0)begin fold_q_pre=3'sd0;fold_remainder_pre=value_next;end
        else if(value_next>=negative_base)begin fold_q_pre=-3'sd1;fold_remainder_pre=value_next+base_ext;end
        else begin fold_q_pre=-3'sd2;fold_remainder_pre=value_next+two_base;end
        fold_range_pre=value_next<negative_two_base || value_next>=three_base ||
            fold_remainder_pre<0 || fold_remainder_pre>=base_ext ||
            (pass_index!=0 && (fold_q_pre< -3'sd1 || fold_q_pre>3'sd1));
        fold_q=fold_q_payload;remainder=fold_remainder_payload;
'''),
        ('''        else if(value<negative_two_base || value>=three_base || remainder<0 || remainder>=base_ext ||
            (pass_index!=0 && (fold_q< -3'sd1 || fold_q>3'sd1)) ||
''',
         '''        else if(fold_range_payload ||
'''),
        ('''                    value<=value_next;stored_digit_bad<=pass_index==0 && ram_q[bank]>=base_reg;
                    state<=PROCESS_WORD;
''',
         '''                    value<=value_next;stored_digit_bad<=pass_index==0 && ram_q[bank]>=base_reg;
                    fold_q_payload<=fold_q_pre;fold_remainder_payload<=fold_remainder_pre;
                    fold_range_payload<=fold_range_pre;
                    state<=PROCESS_WORD;
''')]


def reverse_leaf(text):
    for before,after in reversed(edits()):
        need(text.count(after)==1,'REVERSE_ANCHOR')
        text=text.replace(after,before,1)
    return text


def bind_leaf(text,*,enabled=0):
    need(type(enabled) is int and enabled in (0,1),'BOOLEAN')
    if not enabled:return text
    need(sha(text)==PARENT_SHA256,'EXACT_PROTECTED_TIMING10_ONLY')
    proof=model.prove()
    need(proof['new_external_edges']==0,'PHASE_MODEL')
    original=text
    for before,after in edits():
        need(text.count(before)==1,'UNIQUE_ANCHOR:'+before[:70])
        text=text.replace(before,after,1)
    need(reverse_leaf(text)==original,'ALL_BYTES_REVERSE')
    for state in ('READ_WORD:state<=VALUE_WORD;','state<=PROCESS_WORD;'):
        need(text.count(state)==original.count(state),'STATE_EDGE_LITERAL')
    for authority in ('wire legal_load=','wire legal_begin=','wire legal_read=',
                      'if(stored_digit_bad)begin process_bad=1;process_code=DIGIT_RANGE;end',
                      'if(idle_reject)begin','if(process_bad)begin'):
        need(text.count(authority)==original.count(authority),'AUTHORITY_LITERAL')
    return text
