"""Once-chain actual canonical image, qualified by full32bit result ordinal."""
import hashlib
from . import stream27_host_core_v1 as host
from . import stream27_warm_canonical_v1 as base
from . import stream27_warm_canonical_v2 as parent
from .stream27_warm_chain_v1 import prepare as compile_warm

ROOT=host.ROOT


def source(n,child,text):
    top,s=parent.source(n,child,text);newtop=top.replace('warm_canonical','chain_canonical').replace('_v2','_v1')
    changes=[('module '+top+' #','module '+newtop+' #'),
        ('output logic [63:0] canonical_cycles);',
         'output logic final_load_valid,output logic [31:0] final_load_sequence,\n output logic [63:0] canonical_cycles);'),
        ('wire canonical_request=warm_done',
         'assign final_load_valid=final_row && !out_error;\n assign final_load_sequence=digit_sequence;\n wire canonical_request=warm_done'),
        ('logic [15:0] final_epoch;', 'logic [31:0] final_sequence;logic [15:0] final_epoch;'),
        ('digit_eligible && digit_epoch==final_epoch', 'digit_eligible && digit_sequence==final_sequence && digit_epoch==final_epoch'),
        ('final_epoch<=0;chain_generation<=0;', 'final_sequence<=0;final_epoch<=0;chain_generation<=0;'),
        ('final_epoch<=epoch_in+16\'(square_count-32\'d1);',
         "final_sequence<=square_count-32'd1;final_epoch<=epoch_in+16'(square_count-32'd1);"),
        ('if(boundary_valid && next_epoch==final_epoch+16\'d1',
         "if(boundary_valid && boundary_sequence==final_sequence && next_epoch==final_epoch+16'd1")]
    for old,new in changes:
        if s.count(old)!=1:raise ValueError('S4_FULL_FINAL_SELECTOR_ANCHOR:'+old)
        s=s.replace(old,new)
    return newtop,s


def prepare(n=32,p=16,*,contexts=1,allow_full_constants=False):
    compiler=host.bind(base,compile_warm=compile_warm,source=source)
    b=compiler(n,p,paired=False,contexts=contexts,allow_full_constants=allow_full_constants)
    for path in ('reference/stream27_warm_canonical_v2.py','reference/stream27_chain_canonical_v1.py'):
        b['source_dependencies'].append(path);b['source_sha256'][path]=host.sha(path)
    b['scope']='Full32bit true-last operation selector plus once-chain hardware canonical image; not epoch-only/premature image and not standalone host completion.'
    return b
