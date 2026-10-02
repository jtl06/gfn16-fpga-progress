"""Exact paired component harness derivatives; no HDL execution."""
from pathlib import Path
from . import prefetch_r2_periodmask_structure as s

TOP='root_recurrence27_periodmask_pair'
CPP=TOP+'_v2.cpp'
WRAPPER=TOP+'_v2_threaded.cpp'
PORTS=('clk','rst_n','seed_we','seed_clear','seed_bank','seed_context','seed_lane','seed_data',
       'start','config_bank','config_groups','config_period','config_active_lanes','config_step',
       'request_valid','request_ready','request_tag','root_valid','roots','root_mask','root_tag',
       'root_group','busy','done','error','seed_error','cycles')
OUTPUTS=('request_ready','root_valid','roots','root_mask','root_tag','root_group',
         'busy','done','error','seed_error','cycles')


def expected_top(original):
    s.require(s.sha(original)==s.ANCESTORS[s.RECURRENCE],'frozen recurrence identity')
    header=original[original.index('module '):original.index(');')+2]
    header=s.once(header,'module '+s.RECURRENCE+' #(','module '+TOP+' #(')
    header=s.once(header,'    output logic [63:0] cycles\n',
        '    output logic [63:0] cycles,\n    output logic pair_mismatch,\n'
        '    output logic [31:0] probe_lanes,probe_p,probe_q\n')
    text='// Paired component equivalence probe; no integration or physical claim.\n'+header+'\n'
    text+='    logic baseline_request_ready,baseline_root_valid,baseline_busy,baseline_done,baseline_error,baseline_seed_error;\n'
    text+='    logic [LANES*32-1:0] baseline_roots;\n    logic [LANES-1:0] baseline_root_mask;\n'
    text+='    logic [TAG_W-1:0] baseline_root_tag;\n    logic [16:0] baseline_root_group;\n'
    text+='    logic [63:0] baseline_cycles;\n'
    text+='    assign probe_lanes=LANES;assign probe_p=P;assign probe_q=Q;\n'
    for instance,module in (('baseline',s.RECURRENCE),('candidate',s.NAMES[s.RECURRENCE])):
        text+='    '+module+' #(.LANES(LANES),.TAG_W(TAG_W),.P(P),.Q(Q)) '+instance+' (\n'
        text+='        '+',\n        '.join('.'+port+'('+('baseline_' if instance=='baseline' and port in OUTPUTS else '')+port+')' for port in PORTS)+'\n    );\n'
    text+='    assign pair_mismatch=\n        '+' ||\n        '.join('('+port+' !== baseline_'+port+')' for port in OUTPUTS)+';\nendmodule\n'
    return text


def expected_cpp(original):
    text=s.expected_bench(original).replace('V'+s.NAMES[s.RECURRENCE],'V'+TOP)
    text=s.once(text,'V'+TOP+' d;','V'+TOP+' d{Verilated::threadContextp()};')
    text=s.once(text,'    auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};',
        '    uint64_t pair_checks=0;\n'
        '    auto compare=[&](){pair_checks++;if(d.pair_mismatch)throw std::runtime_error("baseline/candidate port mismatch");};\n'
        '    auto tick=[&](){d.clk=0;d.eval();compare();d.clk=1;d.eval();compare();};')
    text=s.once(text,'                d.clk=0;d.eval();','                d.clk=0;d.eval();compare();')
    text=s.once(text,'                d.clk=1;d.eval();elapsed++;checks++;','                d.clk=1;d.eval();compare();elapsed++;checks++;')
    text=s.once(text,'if(c.groups>=8 && cases%17==0){',
        'if(c.groups>=8 && (cases%17==0 || c.name.rfind("period-",0)==0)){')
    text=s.once(text,'<<" aborts="<<aborts<<" rejects="<<rejects<<"\\n";',
        '<<" aborts="<<aborts<<" rejects="<<rejects<<" pair_checks="<<pair_checks<<"\\n";')
    # The wrapper renames main, so its special implicit success return no
    # longer applies. This explicit return is the only v2 bench change.
    text=s.once(text,'\n}catch(const std::exception& e)',
                '\n    return 0;\n}catch(const std::exception& e)')
    return text


def expected_wrapper():
    return '''// Explicit context and runtime probe around the separately pinned pair bench.
#define main periodmask_pair_main
#include "root_recurrence27_periodmask_pair_v2.cpp"
#undef main
int main(int argc,char** argv) {
    VerilatedContext* const context=Verilated::threadContextp();
    context->threads(1);
    context->commandArgs(argc,argv);
    if(argc==2 && std::string(argv[1])=="--runtime-probe") {
        Vroot_recurrence27_periodmask_pair dut{context};
        dut.eval();
        std::cout<<"{\\"context_threads\\":"<<context->threads()
            <<",\\"model_threads\\":"<<dut.threads()
            <<",\\"lanes\\":"<<dut.probe_lanes<<",\\"p\\":"<<dut.probe_p
            <<",\\"q\\":"<<dut.probe_q<<"}\\n";
        return context->threads()==1 && dut.threads()==1 ? 0 : 2;
    }
    const int result=periodmask_pair_main(argc,argv);
    return context->threads()==1 ? result : 97;
}
'''


def validate_files(root):
    root=Path(root);s.validate_files(root)
    originals=(root/'rtl/kernel'/(s.RECURRENCE+'.sv')).read_text()
    bench=(root/'rtl/tb'/s.BENCH).read_text()
    expected={'rtl/tb/'+TOP+'.sv':expected_top(originals),
              'rtl/tb/'+CPP:expected_cpp(bench),'rtl/tb/'+WRAPPER:expected_wrapper()}
    for name,text in expected.items():s.require((root/name).read_text()==text,'unreviewed paired gate delta: '+name)
    return {name:s.sha(text) for name,text in expected.items()}
