"""Separate simulation-only row-tag reset and shadow-coverage derivatives.

No normal snapshot is changed. Observation ports are explicit read-only wires;
no blanket public-flat access. Counters are inside the existing shadow guard,
excluded from synthesis. The targeted top is not a physical implementation.
"""
from pathlib import Path
import hashlib

ENGINE='genefer_ntt_banked27_prefetch_r2_orient8_rowcompact_engine'
HOST='genefer_ntt_banked27_prefetch_r2_host_broadcast_orient8_rowcompact_engine'
CORE='genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rowcompact'
TOP='rowcompact_reset_probe'
PINS={ENGINE:'604dc89eb87c8126372e468d7a9e130e8cc483a4c02e8f3e3b9ac189e230e6a9',
      HOST:'446e9878d69e6b3d2237b714dc141b6bdaf04439664022f3b17afe32ae1106ac',
      CORE:'5199a28f5a739fe007172a9a1d206406d7c41103bcadac854993583f1d96d01a'}
NAMES={name:name+'_resetprobe' for name in PINS}
VECTOR='results/throughput-20260929/core27-prefetch-r2-aw16-v1/vectors-aw16.txt'
VECTOR_SHA='3449c1e3e1d7c0820842ecb30295b963b4aa81af6b27be8e38b7c87f2bd39f3d'
COUNTERS=('shadow_bf_checks','shadow_mul_checks','shadow_bf_nonzero','shadow_mul_nonzero')


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(text):return hashlib.sha256(text.encode()).hexdigest()


def once(text,old,new):
    require(text.count(old)==1,'ambiguous reset-probe source anchor')
    return text.replace(old,new)


def derivative(name,original):
    require(name in PINS and sha(original)==PINS[name],'frozen rowcompact identity')
    text=once(original,'module '+name+' #(','module '+NAMES[name]+' #(')
    if name!=ENGINE:
        child=ENGINE if name==HOST else HOST
        return once(text,child+' #(',NAMES[child]+' #(')
    old='    logic [RW-1:0] legacy_row_tag [0:6][0:BANKS-1];\n'
    new=old+'    logic [63:0] '+','.join(COUNTERS)+';\n'
    new+='    integer check_bf,check_mul,nonzero_bf,nonzero_mul;\n'
    text=once(text,old,new)
    old='            for(int t=0;t<7;t=t+1) for(int b=0;b<BANKS;b=b+1) legacy_row_tag[t][b]<=0;'
    text=once(text,old,old+'\n            '+''.join(name+'<=0;' for name in COUNTERS))
    old='''        end else begin
            for(int b=0;b<BANKS;b=b+1) begin
                legacy_row_tag[0][b]<=data_ra[b];'''
    new=old.replace('            for(int b=',
        '            check_bf=0;check_mul=0;nonzero_bf=0;nonzero_mul=0;\n            for(int b=')
    text=once(text,old,new)
    old='''                if(data_we[b] && (state==BF_READ || state==BF_DRAIN || state==MUL_READ || state==MUL_DRAIN) &&
                   data_wa[b]!==legacy_row_tag[6][b]) $fatal(1,"compact row write address mismatch");
            end
        end
    end
    // synthesis translate_on'''
    new='''                if(data_we[b] && (state==BF_READ || state==BF_DRAIN || state==MUL_READ || state==MUL_DRAIN)) begin
                    if(state==BF_READ || state==BF_DRAIN) begin
                        check_bf=check_bf+1;
                        if(data_wa[b]!=0)nonzero_bf=nonzero_bf+1;
                    end else begin
                        check_mul=check_mul+1;
                        if(data_wa[b]!=0)nonzero_mul=nonzero_mul+1;
                    end
                    if(data_wa[b]!==legacy_row_tag[6][b]) $fatal(1,"compact row write address mismatch");
                end
            end
            shadow_bf_checks<=shadow_bf_checks+64'(check_bf);
            shadow_mul_checks<=shadow_mul_checks+64'(check_mul);
            shadow_bf_nonzero<=shadow_bf_nonzero+64'(nonzero_bf);
            shadow_mul_nonzero<=shadow_mul_nonzero+64'(nonzero_mul);
        end
    end
    // synthesis translate_on'''
    return once(text,old,new)


def probe_top(original):
    require(sha(original)==PINS[CORE],'frozen core identity')
    header=original[original.index('module '):original.index(');')+2]
    header=once(header,'module '+CORE+' #(','module '+TOP+' #(')
    header=once(header,'    output logic [63:0] seed_setup_cycles\n',
        '''    output logic [63:0] seed_setup_cycles,
    input logic [6:0] probe_bank,
    output logic [3:0] probe_state [0:2],
    output logic [1:0] probe_op [0:2],probe_phase [0:2],
    output logic [31:0] probe_group [0:2],
    output logic [4:0] probe_stage [0:2],
    output logic [2:0] probe_pairing [0:2],
    output logic [2:0] probe_issue,probe_orientation,probe_half,probe_read,probe_write,probe_any_write,
    output logic [2:0] probe_bf_in,probe_mul_in,probe_bf_valid,probe_mul_valid,probe_tag_nonzero,
    output logic [8:0] probe_ra [0:2],probe_wa [0:2],probe_legacy [0:2],
    output logic [8:0] probe_base [0:2][0:7][0:6],probe_toggle [0:2][0:7][0:6],
    output logic [2:0] probe_pair [0:2][0:7][0:6],
    output logic [6:0] probe_orient [0:2][0:7],
    output logic [63:0] probe_bf_checks [0:2],probe_mul_checks [0:2],
                        probe_bf_nonzero [0:2],probe_mul_nonzero [0:2]
''')
    ports=('clk','rst_n','load_we','read_en','start','host_addr','write_data','base','double_bit',
           'read_valid','read_data','busy','done','error','cycles','conversion_cycles','root_cycles',
           'ntt_cycles','crt_cycles','carry_cycles','carry_passes','profile_cache_valid','profile_loads',
           'profile_hits','profile_words_loaded','seed_setup_cycles')
    text='// Simulation-only top. Do not synthesize or use as a hardware candidate.\n'+header+'\n'
    text+='    '+NAMES[CORE]+' #(.AW(AW),.NTT_LANES(NTT_LANES)) dut ('+','.join('.'+p for p in ports)+');\n'
    text+='    initial if(AW!=16 || NTT_LANES!=64)$fatal(1,"reset probe requires AW16/L64");\n'
    for field in range(3):
        h=f'dut.field_lane[{field}].engine.child'
        simple={'state':'state','op':'active_op','phase':'phase_reg','group':'group_index','stage':'stage_bit',
                'pairing':'pairing','issue':'issue_fire','orientation':'orientation','half':'point_half',
                'read':'data_re[probe_bank]','write':'data_we[probe_bank]','any_write':'|'+h+'.data_we',
                'bf_in':'bf_in_valid[0]','mul_in':'mul_in_valid[0]','bf_valid':'bf_valid[0]',
                'mul_valid':'mul_valid[0]','ra':'data_ra[probe_bank]','wa':'data_wa[probe_bank]',
                'legacy':'legacy_row_tag[6][probe_bank]','bf_checks':'shadow_bf_checks',
                'mul_checks':'shadow_mul_checks','bf_nonzero':'shadow_bf_nonzero','mul_nonzero':'shadow_mul_nonzero'}
        for output,source in simple.items():
            text+=f'    assign probe_{output}[{field}]='+ (source if source.startswith('|') else h+'.'+source)+';\n'
        nonzero=[]
        for group in range(8):
            tag=f'{h}.row_tags[{group}]'
            text+=f'    assign probe_orient[{field}][{group}]={tag}.orientation_pipe;\n'
            nonzero.append(f'(|{tag}.orientation_pipe)')
            for age in range(7):
                for output,signal in (('base','base_pipe'),('toggle','toggle_pipe'),('pair','pairing_pipe')):
                    text+=f'    assign probe_{output}[{field}][{group}][{age}]={tag}.{signal}[{age}];\n'
                    nonzero.append(f'(|{tag}.{signal}[{age}])')
        text+=f'    assign probe_tag_nonzero[{field}]='+' | '.join(nonzero)+';\n'
    return text+'endmodule\n'


def mutant(text,kind):
    """Return a separate source payload; never mutate a frozen/live file."""
    require(kind in ('bad-age','bad-address'),'named shadow mutant')
    old='data_wa[bank]=row_tags[bank/ROW_TAG_BANKS].base_pipe[6];data_w[bank]=product[bank%LANES];'
    new=old.replace('base_pipe[6]','base_pipe[5]' if kind=='bad-age' else "base_pipe[6]^RW'(1)")
    return once(text,old,new)


def matrix():
    return [dict(kind=kind,variant=variant,age=age,bit=bit)
            for kind in ('bf','mul') for variant in (0,1) for age in range(8) for bit in (0,1)]


def target(case):
    require(case in matrix(),'reviewed single reset case')
    bf=case['kind']=='bf';variant=case['variant']
    return dict(group=variant if bf else 2+variant,bank=(2 if variant==0 else 0) if bf else 64*variant,
                row=256 if bf else 1,orientation=variant if bf else None,half=variant if not bf else None)


def expected_counts():
    return dict(bf=2*16*65536,mul=3*65536,bf_nonzero=2*16*(65536-128),mul_nonzero=3*(65536-128))


def timing_model(age):
    require(type(age) is int and 0<=age<=7,'target age')
    # Token enters slot0 at E0; pre-E7 write consumes slot6. Reset is between edges.
    return dict(slot=age if age<7 else None,committed=age==7,cancelled=age<7,
                write_edge=7,quiet_edges=8)


def validate_files(root):
    root=Path(root);result={}
    for old,new in NAMES.items():
        path='rtl/tb/'+new+'.sv';want=derivative(old,(root/'rtl/kernel'/(old+'.sv')).read_text())
        require((root/path).read_text()==want,'unreviewed reset instrumentation: '+new);result[path]=sha(want)
    path='rtl/tb/'+TOP+'.sv';want=probe_top((root/'rtl/kernel'/(CORE+'.sv')).read_text())
    require((root/path).read_text()==want,'unreviewed selective observation top');result[path]=sha(want)
    return result
