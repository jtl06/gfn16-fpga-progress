#include "Vgenefer_track_a4_ntt_sequencer_v1.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>

#ifndef A4_SEQ_AW
#error Explicit A4_SEQ_AW must match HDL AW
#endif
static_assert(A4_SEQ_AW==5,"AW5 exploratory sequencer only");
static constexpr unsigned N=1u<<A4_SEQ_AW,T=N/16;
static constexpr std::array<uint32_t,3> P{{104857601u,69206017u,67239937u}};
using Image=std::array<std::array<uint32_t,N>,3>;
static void need(bool ok,const std::string& message){if(!ok)throw std::runtime_error(message);}

// Independent schoolbook in Z_p[X]/(X^N+1), not an NTT implementation.
// <=N terms per coefficient, each <=104857600^2: magnitude <2^59 for N32.
static Image square(const Image& input){
    Image output{};
    for(unsigned f=0;f<3;++f){
        std::array<int64_t,N> coefficients{};
        for(unsigned i=0;i<N;++i)for(unsigned j=0;j<N;++j){
            const int64_t product=int64_t(input[f][i])*input[f][j];
            coefficients[(i+j)%N]+=(i+j<N?product:-product);
        }
        for(unsigned i=0;i<N;++i){
            int64_t value=coefficients[i]%int64_t(P[f]);
            if(value<0)value+=P[f];
            output[f][i]=uint32_t(value);
        }
    }
    return output;
}

struct Bench{
    Vgenefer_track_a4_ntt_sequencer_v1& d;
    uint64_t checked=0,operations=0,cold=0,warm=0,edges=0;
    void tick(){d.clk=0;d.eval();d.clk=1;d.eval();++edges;}
    void idle_ports(){d.start_ntt=0;d.cancel=0;d.block_read_en=0;d.block_write_en=0;
        d.block_read_offset=0;d.block_write_offset=0;d.block_read_mask=65535;d.block_write_mask=65535;
        for(unsigned i=0;i<48;++i)d.block_write_words[i]=0;}
    void reset(){idle_ports();d.rst_n=0;tick();need(!d.busy&&!d.done&&!d.error&&!d.profile_cache_valid&&!d.block_read_valid,"A4_SEQ_RESET");
        d.rst_n=1;tick();need(d.ready,"A4_SEQ_COLD_READY");}
    void load(const Image& image){
        d.block_write_en=1;
        for(unsigned offset=0;offset<T;++offset){
            d.block_write_offset=offset;
            for(unsigned f=0;f<3;++f)for(unsigned lane=0;lane<16;++lane)
                d.block_write_words[f*16+lane]=image[f][lane*T+offset];
            tick();need(!d.block_error&&!d.error&&!d.block_read_valid,"A4_SEQ_LOAD");
        }
        d.block_write_en=0;d.eval();need(d.ready,"A4_SEQ_LOADED_READY");
    }
    void read(const Image& expected,uint64_t operation){
        d.block_read_en=1;
        for(unsigned offset=0;offset<T;++offset){
            d.block_read_offset=offset;tick();
            need(d.block_read_valid==7&&!d.block_error&&!d.error,"A4_SEQ_READ_VALID");
            need(d.block_read_masks==0xffffffffffffull,"A4_SEQ_READ_MASK");
            const uint32_t tags=offset|(offset<<A4_SEQ_AW)|(offset<<(2*A4_SEQ_AW));
            need(d.block_read_offsets==tags,"A4_SEQ_READ_OFFSET");
            need(!d.ready,"A4_SEQ_PENDING_RESPONSE_READY");
            for(unsigned f=0;f<3;++f)for(unsigned lane=0;lane<16;++lane){
                const unsigned index=lane*T+offset;
                need(d.block_read_words[f*16+lane]==expected[f][index],
                    "A4_SEQ_WORD_MISMATCH operation="+std::to_string(operation)+" field="+std::to_string(f)+" index="+std::to_string(index));
                ++checked;
            }
        }
        d.block_read_en=0;tick();need(!d.block_read_valid&&d.ready,"A4_SEQ_READ_DRAIN");
    }
    void run(bool is_cold){
        need(d.ready,"A4_SEQ_START_READY");d.start_ntt=1;tick();d.start_ntt=0;
        need(d.busy&&!d.done&&!d.error,"A4_SEQ_START_ACCEPT");
        unsigned timeout=0;
        while(!d.done){need(++timeout<20000,"A4_SEQ_TIMEOUT");tick();need(!d.error,"A4_SEQ_RUN_ERROR");}
        need(!d.busy&&d.ready&&d.profile_cache_valid&&d.profile_coherent,"A4_SEQ_COMPLETION_IDLE");
        need(d.ntt_cycles==246 && d.seed_setup_cycles==122,"A4_SEQ_FROZEN_NTT_METRICS");
        need(d.root_cycles==(is_cold?3089u:0u) && d.profile_words_loaded==(is_cold?3084u:0u),"A4_SEQ_PROFILE_METRICS");
        need(d.profile_loads==unsigned(is_cold)&&d.profile_hits==unsigned(!is_cold),"A4_SEQ_PROFILE_CACHE_ACCOUNTING");
        need(d.cycles==d.root_cycles+d.ntt_cycles,"A4_SEQ_PHASE_TOTAL_METRIC");
        ++operations;if(is_cold)++cold;else ++warm;
        // Caller may now assert its first read. No intervening idle edge needed.
    }
};

int main(int argc,char** argv){
    try{
        VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
        Vgenefer_track_a4_ntt_sequencer_v1 d{&context};
        if(argc==2&&std::string(argv[1])=="--runtime-probe"){
            std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
            return context.threads()==1&&d.threads()==1?0:2;
        }
        need(argc==2 && (std::string(argv[1])=="--smoke" || std::string(argv[1])=="--wrong-expected"),"A4_SEQ_USAGE");
        const bool wrong=std::string(argv[1])=="--wrong-expected";
        Bench b{d};Image image{};
        for(unsigned fixture=0;fixture<3;++fixture){
            b.reset();image={};
            for(unsigned f=0;f<3;++f)for(unsigned i=0;i<N;++i){
                if(fixture==1)image[f][i]=i==N-1?1u:0u;
                if(fixture==2)image[f][i]=(i%3==0)?P[f]-1u:(i*i+7*i+3)%P[f];
            }
            b.load(image);b.read(image,b.operations);
            for(unsigned iteration=0;iteration<3;++iteration){
                Image expected=square(image);b.run(iteration==0);
                if(wrong&&b.operations==1)expected[0][0]^=1;
                b.read(expected,b.operations-1);image=expected;
            }
        }
        // Simultaneous start/write is atomically rejected before field RAM.
        d.start_ntt=1;d.block_write_en=1;d.block_write_offset=0;
        for(unsigned word=0;word<48;++word)d.block_write_words[word]=0xffffffffu;
        b.tick();need(d.error&&!d.busy&&d.done&&!d.profile_cache_valid,"A4_SEQ_START_BLOCK_REJECT");
        d.start_ntt=0;d.block_write_en=0;d.cancel=1;b.tick();
        need(!d.error&&!d.busy&&!d.done&&!d.profile_cache_valid&&!d.block_read_valid,"A4_SEQ_CANCEL_FAILED");
        d.cancel=0;b.tick();b.read(image,b.operations);
        // Cancel an in-flight cold profile, reload, and require a new cold run.
        d.start_ntt=1;b.tick();d.start_ntt=0;
        for(unsigned age=0;age<8;++age)b.tick();
        need(d.busy&&!d.profile_cache_valid,"A4_SEQ_PROFILE_CANCEL_WINDOW");
        d.cancel=1;b.tick();need(!d.busy&&!d.done&&!d.error&&!d.profile_cache_valid&&!d.profile_coherent
            &&!d.block_read_valid&&d.cycles==0,"A4_SEQ_PROFILE_CANCEL");
        d.cancel=0;b.tick();b.load(image);b.read(image,b.operations);
        Image expected=square(image);b.run(true);b.read(expected,b.operations-1);
        need(context.threads()==1&&d.threads()==1,"A4_SEQ_THREAD_DRIFT");
        std::cout<<"A4_SEQ_PASS aw=5 operations="<<b.operations<<" cold="<<b.cold<<" warm="<<b.warm<<" words="<<b.checked
            <<" ntt=246 seed=122 cold_roots=3089 atomic_start_block=1 cancel_profile=1\n";
        d.final();return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}
}
