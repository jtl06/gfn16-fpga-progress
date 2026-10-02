// AW5-first targeted T5 qualification; explicit context, bounded event waits.
#include "Vcore27_prefill_tail_probe.h"
#include "verilated.h"
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

static void need(bool v,const std::string& why){if(!v)throw std::runtime_error(why);}
template<class T> static __int128 signed96(const T& a){
    __uint128_t x=__uint128_t(a[0])|(__uint128_t(a[1])<<32)|(__uint128_t(a[2])<<64);
    return a[2]&0x80000000u?__int128(x)-(__int128(1)<<96):__int128(x);
}
int main(int argc,char** argv){
    try{
        VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
        Vcore27_prefill_tail_probe d{&context};
        if(argc==2 && std::string(argv[1])=="--runtime-probe"){
            std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
            return context.threads()==1 && d.threads()==1?0:2;
        }
        need(argc==4 || argc==6,"usage: --changed-base vectors control | --tail-reset/error vectors age first/middle/final control");
        const std::string mode=argv[1];
        const bool reject_base=mode=="--base-reject";
        const bool changed=mode=="--changed-base" || reject_base,reset_case=mode=="--tail-reset",error_case=mode=="--tail-error",carry_error_case=mode=="--tail-carry-error";
        need(changed || reset_case || error_case || carry_error_case,"unknown targeted mode");
        need((changed && argc==4) || (!changed && argc==6),"strict targeted argument count");
        need(std::string(argv[argc-1])=="control","explicit control source mode required");
        unsigned age=0;
        if(!changed){need(std::string(argv[3]).size()==1 && argv[3][0]>='0' && argv[3][0]<='6',"tail age 0..6 required");age=unsigned(argv[3][0]-'0');}
        std::ifstream f(argv[2]);need(bool(f),"missing targeted vector");
        unsigned n,a,b;f>>n>>a>>b;need(n==32 && a==604832956 && b==1000000000,"exact AW5 targeted profile");
        const std::string row=changed?"none":argv[4];
        need(changed || row=="first" || row=="middle" || row=="final","explicit emission row selection");
        const unsigned row_index=row=="first"?0:row=="middle"?(n/16)/2:n/16-1;
        need(changed || row=="final" || age==0,"non-final emission probes target commit E0 only");
        std::vector<std::vector<int64_t>> v(4,std::vector<int64_t>(n));
        for(auto& row:v)for(auto& x:row)need(bool(f>>x),"truncated targeted vector");
        std::string extra;need(!(f>>extra),"trailing targeted vector input");
        auto idle=[&](){d.start=0;d.load_we=0;d.read_en=0;d.sim_host_error=0;d.sim_carry_error=0;};
        auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};
        auto reset=[&](){
            idle();d.rst_n=0;d.eval();
            need(!d.busy && !d.done && !d.error && !d.read_valid && !d.dbg_prefilled,"T5_ASYNC_RESET_LEAK");
            tick();d.rst_n=1;d.eval();tick();
            need(!d.busy && !d.done && !d.error && !d.read_valid && !d.dbg_prefilled,"T5_RESET_RELEASE_LEAK");
        };
        auto load=[&](unsigned radix){
            idle();d.base=radix;
            for(unsigned i=0;i<n;++i){d.host_addr=i;d.write_data=uint32_t(v[0][i]);d.load_we=1;tick();}
            idle();tick();need(!d.dbg_prefilled,"T5_LOAD_ELIGIBILITY_LEAK");
        };
        auto start=[&](unsigned radix,unsigned bit){
            d.base=radix;d.double_bit=bit;d.start=1;d.load_we=1;d.read_en=1;d.write_data=0xffffffffu;tick();idle();
            need(d.busy && !d.done && !d.error,"T5_START_REJECTED");
        };
        auto poison=[&](unsigned t){d.start=t&1;d.load_we=1;d.read_en=1;d.base=0;d.double_bit=t&1;d.host_addr=t%n;d.write_data=123;};
        unsigned successful=0,readbacks=0,event_hits=0,recoveries=0;
        auto finish=[&](unsigned radix,const std::vector<int64_t>& expected,bool fast){
            unsigned elapsed=0;
            while(!d.done && elapsed<20000){poison(elapsed);tick();++elapsed;need(!d.read_valid,"T5_BUSY_READ_LEAK");}
            idle();d.base=radix;
            need(d.done && !d.busy && !d.error && d.dbg_prefilled,"T5_RECOVERY_COMPLETION");
            need(d.conversion_cycles==(fast?0:8),"T5_TARGET_CONVERSION_MODE");
            need(d.dbg_issued==n && d.dbg_written==n,"T5_TARGET_IMAGE_COUNT");
            for(unsigned i=0;i<n;++i){d.host_addr=i;d.read_en=1;tick();
                need(d.read_valid && signed96(d.read_data)==__int128(expected[i]),"T5_TARGET_READBACK index="+std::to_string(i));}
            idle();need(d.dbg_prefilled,"T5_READBACK_INVALIDATED_IMAGE");++successful;++readbacks;
        };
        d.clk=1;d.rst_n=1;d.eval();reset();load(a);start(a,0);
        if(changed){
            finish(a,v[1],false);
            if(reject_base){
                // Legal base, but current canonical digits do not fit it.
                start(2*n+5,0);
                unsigned waited=0;
                while(!d.done && waited++<32){poison(waited);tick();}
                idle();need(d.done && d.error && !d.busy && !d.dbg_prefilled,"T5_SMALLER_BASE_DIGIT_NOT_REJECTED");
                reset();load(a);start(a,0);finish(a,v[1],false);++recoveries;
            }else{
                // No host load between starts: only the base tag changes.
                start(b,0);finish(b,v[2],false);
                start(b,1);finish(b,v[3],true);
            }
            event_hits=1;
        }else{
            bool seen=false,triggered=false;unsigned relative=0,elapsed=0;
            while(!triggered && elapsed<20000){
                if(!seen && d.dbg_emit && d.dbg_issued==row_index*16){seen=true;relative=0;}
                if(seen && relative==age){
                    ++event_hits;triggered=true;
                    if(reset_case){
                        // The clock is held high from the preceding edge. E0
                        // means cancel just before the actual final commit.
                        reset();
                        for(unsigned k=0;k<12;++k){tick();need(!d.done && !d.read_valid && !d.dbg_prefilled,"T5_RESET_TAIL_GHOST");}
                    }else{
                        poison(elapsed);d.sim_host_error=error_case?2:0;d.sim_carry_error=carry_error_case;tick();idle();
                        need(d.done && d.error && !d.busy && !d.dbg_prefilled,"T5_ERROR_TAIL_NOT_REJECTED");
                        for(unsigned k=0;k<12;++k){poison(k);tick();need(!d.busy && !d.read_valid && !d.dbg_prefilled,"T5_FAILED_QUARANTINE_LEAK");}
                        reset();
                    }
                    break;
                }
                need(!d.done && !d.error,"T5_TAIL_EVENT_MISSED");poison(elapsed);tick();++elapsed;if(seen)++relative;
            }
            need(triggered && event_hits==1,"T5_TAIL_EVENT_UNREACHED");
            load(a);start(a,0);finish(a,v[1],false);++recoveries;
        }
        need(context.threads()==1 && d.threads()==1,"T5_CONTEXT_DRIFT");
        std::cout<<"T5_TARGET_PASS mode="<<mode<<" age="<<age<<" row="<<row<<" row_index="<<row_index
                 <<" middle_aliases_final="<<(n/16==2)<<" event_hits="<<event_hits
                 <<" successful="<<successful<<" readbacks="<<readbacks<<" recoveries="<<recoveries<<"\n";
        d.final();return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
