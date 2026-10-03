"""Private optional R10 payload-enable split; no shared generator mutation."""
import hashlib

OLD='genefer_stream27_canonical_image_directbound_v1'
NEW='genefer_stream27_canonical_image_begin_split_v1'
PARENT_PIN='f855269ace437fff2ebcfd0e7048f8aadc0dadcbe7836a4ca1e4213ccda17402'
CAPTURE='''            // Speculative payload only: rejected BEGIN enters sticky FAILED.
            // Fault/control authority remains exclusively legal_begin/idle_reject.
            if(state==IDLE && !error && begin_canonical)base_reg<=base;
'''


def once(text,old,new):
    if text.count(old)!=1:
        raise ValueError('CANON_BEGIN_SPLIT_EXACT_ANCHOR '+repr(old))
    return text.replace(old,new)


def reverse_leaf(text):
    text=once(text,'module '+NEW+' #','module '+OLD+' #')
    text=once(text,CAPTURE,'')
    return once(text,'                        address<=0;pass_index<=0;carry<=0;all_zero<=1;all_max<=1;state<=READ_WORD;',
                '                        base_reg<=base;address<=0;pass_index<=0;carry<=0;all_zero<=1;all_max<=1;state<=READ_WORD;')


def bind_leaf(text,*,enabled=0):
    if type(enabled) is not int or enabled not in (0,1):
        raise ValueError('CANON_BEGIN_SPLIT_BOOLEAN')
    if not enabled:
        return text
    if hashlib.sha256(text.encode()).hexdigest()!=PARENT_PIN:
        raise ValueError('CANON_BEGIN_SPLIT_EXACT_R9_LEAF')
    original=text
    text=once(text,'                        base_reg<=base;address<=0;pass_index<=0;carry<=0;all_zero<=1;all_max<=1;state<=READ_WORD;',
              '                        address<=0;pass_index<=0;carry<=0;all_zero<=1;all_max<=1;state<=READ_WORD;')
    text=once(text,'            if(idle_reject)begin\n',CAPTURE+'            if(idle_reject)begin\n')
    text=once(text,'module '+OLD+' #','module '+NEW+' #')
    if reverse_leaf(text)!=original:
        raise ValueError('CANON_BEGIN_SPLIT_REVERSE')
    return text
