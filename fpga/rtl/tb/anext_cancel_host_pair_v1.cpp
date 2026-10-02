// Actual host/setup/canonical/RAM pair, not a square/CRT arithmetic engine.
#include "Vgenefer_anext_cancel_host_pair_v1.h"
#include "verilated.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>

#ifndef ANEXT_CANCEL_AW
#error ANEXT_CANCEL_AW must match -GAW
#endif
static_assert(ANEXT_CANCEL_AW==5 || ANEXT_CANCEL_AW==8,"bounded host pair only");
constexpr unsigned AW=ANEXT_CANCEL_AW,N=1u<<AW,T=N/16;
constexpr uint32_t K=2*N+384,MIN_BASE=std::max(2*N+5,(2*K+2)/3+1);
using DUT=Vgenefer_anext_cancel_host_pair_v1;
using Words=std::array<uint32_t,N>;
using Signed=std::array<int64_t,N>;
using Corrections=std::array<int32_t,16>;
static void need(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
template<class Wide>static int64_t signed33(const Wide& data,unsigned lane){
    uint64_t value=0;for(unsigned k=0;k<33;++k){unsigned bit=33*lane+k;value|=uint64_t((data[bit/32]>>(bit%32))&1u)<<k;}
    return value&(uint64_t(1)<<32)?int64_t(value)-int64_t(uint64_t(1)<<33):int64_t(value);
}
struct Image{Words raw{};Corrections low{},high{};uint32_t base=1000;};
static Signed effective(const Image& image){Signed result{};for(unsigned j=0;j<N;++j)result[j]=int32_t(image.raw[j]);for(unsigned b=0;b<16;++b){result[b*T]+=image.low[b];result[b*T+1]+=image.high[b];}return result;}
// Ordinary signed Euclidean integer normalization: no RTL comparison tree,
// input-stage/payload scheduler or one-cycle canonical-cell recurrence reused.
static Image normalized(const Image& image){
    Signed values=effective(image);Image result;result.base=image.base;
    for(unsigned fold=0;fold<6;++fold){int64_t carry=0;bool zero=true,max=true;
        for(unsigned j=0;j<N;++j){int64_t x=values[j]+carry,q=x/image.base,r=x%image.base;if(r<0){r+=image.base;--q;}carry=q;result.raw[j]=uint32_t(r);zero&=!r;max&=r==image.base-1;}
        if((carry==1&&zero)||(carry==-1&&max)){result.raw.fill(0);result.low[0]=-1;return result;}
        if(!carry)return result;
        for(unsigned j=0;j<N;++j)values[j]=result.raw[j];values[0]-=carry;
    }throw std::runtime_error("ANEXT_CANCEL_REFERENCE_FOLD_BOUND");
}
struct Counts{uint64_t commands=0,reads=0,errors=0,holds=0,host_cases=0,seams=0,ram=0,image_reads=0,image_faults=0,image_cancels=0,image_ram=0,max_latency=0;};
struct Response{uint32_t op,word,error,code,generation;
    explicit Response(const DUT& d):op(d.rsp_opcode),word(d.rsp_word),error(d.rsp_error),code(d.rsp_error_code),generation(d.rsp_generation){}
    bool equals(const DUT& d)const{return d.rsp_valid&&op==d.rsp_opcode&&word==uint32_t(d.rsp_word)&&error==d.rsp_error&&code==d.rsp_error_code&&generation==d.rsp_generation;}
};
enum class Hook{None,HostWrite,CanonicalRead};
class Bench{
public:
    DUT& d;Counts c;Image host,image;uint64_t edge=0,host_due=0;bool negative=false,negative_used=false;
    explicit Bench(DUT& dut,bool mutant):d(dut),negative(mutant){clear();d.rst_n=0;step();d.rst_n=1;step();}
    void clear_compute(){d.compute_configure=0;d.compute_clear_image=0;d.compute_read_en=0;d.compute_write_en=0;d.compute_boundary_commit=0;d.compute_read_offset=0;d.compute_write_offset=0;d.compute_read_tag=0;d.compute_read_mask=0;d.compute_write_mask=0;d.compute_read_apply_corrections=0;for(unsigned b=0;b<16;++b){d.compute_write_words[b]=0;d.compute_boundary_low[b]=0;d.compute_boundary_high[b]=0;}}
    void clear_image(){d.i_cancel=0;d.i_configure=0;d.i_clear_image=0;d.i_read_en=0;d.i_write_en=0;d.i_base=image.base;d.i_generation=17;d.i_read_offset=0;d.i_read_tag=0;d.i_read_mask=0;d.i_read_apply_corrections=0;d.i_write_offset=0;d.i_write_mask=0;d.i_write_kind=0;d.i_clear_corrections=0;d.i_set_minus_one=0;d.i_boundary_commit=0;for(unsigned b=0;b<16;++b){d.i_write_words[b]=0;d.i_boundary_low_words[b]=0;d.i_boundary_high_words[b]=0;}}
    void clear(){d.clk=0;d.cmd_valid=0;d.rsp_ready=0;d.cmd_opcode=7;d.cmd_address=0;d.cmd_word=0;d.cmd_base=1000;d.cmd_double=0;d.peek_offset=0;d.square_done=0;d.square_error=0;d.square_tail_checked=0;d.square_root_coherent=0;d.square_out_generation=0;d.square_coefficients_seen=0;d.square_digits_written=0;d.square_patch_words_written=0;clear_compute();clear_image();}
    void paired(){need(!d.shell_pair_mismatch,"ANEXT_CANCEL_SHELL_PAIR edge="+std::to_string(edge));need(!d.image_pair_mismatch,"ANEXT_CANCEL_IMAGE_PAIR edge="+std::to_string(edge));need(!d.square_begin,"ANEXT_CANCEL_NO_SQUARE_ENGINE");}
    void step(){
        d.clk=0;d.eval();paired();bool held=d.rsp_valid&&!d.rsp_ready;Response response(d);
        bool cancel=d.square_cancel||d.compute_memory_error;
        if(!d.rst_n||cancel)host_due=0;
        if(d.rst_n&&d.host_begin&&!cancel)host_due=edge+2;
        d.clk=1;d.eval();paired();
        if(d.rst_n && !cancel && !d.square_cancel && !d.compute_memory_error){
            need(bool(d.host_done)==(host_due && edge==host_due),"ANEXT_CANCEL_HOST_E2");
            if(host_due&&edge==host_due)host_due=0;
        }
        if(held&&d.rst_n)need(response.equals(d),"ANEXT_CANCEL_HELD_RESPONSE");++edge;
    }
    void hold(unsigned count){Response response(d);for(unsigned j=0;j<count;++j){step();need(response.equals(d),"ANEXT_CANCEL_EXPLICIT_HOLD");++c.holds;}}
    void acknowledge(){d.rsp_ready=1;step();d.rsp_ready=0;d.eval();need(d.cmd_ready&&!d.rsp_valid,"ANEXT_CANCEL_RESPONSE_DRAIN");}
    void quiet(unsigned count){clear_compute();d.cmd_valid=0;for(unsigned j=0;j<count;++j){d.clk=0;d.eval();need(!d.old_image_write_accept&&!d.new_image_write_accept,"ANEXT_CANCEL_QUIET_COMMIT");step();}}
    void check_ram(bool standalone=false){
        const auto& expected=standalone?image.raw:host.raw;
        for(unsigned row=0;row<T;++row){d.peek_offset=row;d.eval();for(unsigned b=0;b<16;++b){uint32_t old=standalone?d.old_i_ram_peek[b]:d.old_ram_peek[b],actual=standalone?d.new_i_ram_peek[b]:d.new_ram_peek[b];need(old==actual && actual==expected[b*T+row],"ANEXT_CANCEL_RAM_ORACLE");if(standalone)++c.image_ram;else ++c.ram;
            // Mutation is local to expected data, AFTER real old/new/oracle equality.
            if(negative&&!negative_used&&!standalone&&row==0&&b==0){negative_used=true;need(actual==(expected[0]^1u),"ANEXT_CANCEL_HOST_NEGATIVE_ORACLE_REJECT");}
        }}
    }
    void response(unsigned op,unsigned error,int32_t word,bool valid,uint32_t generation,bool ack=true){
        need(d.rsp_valid && d.rsp_opcode==op && d.rsp_error==unsigned(error!=0) && d.rsp_error_code==error && int32_t(d.rsp_word)==word && d.rsp_generation==generation,"ANEXT_CANCEL_RESPONSE_ORACLE");
        need(bool(d.image_valid)==valid && !d.prefill_valid && bool(d.fault_sticky)==bool(error),"ANEXT_CANCEL_ELIGIBILITY");
        ++c.commands;c.errors+=bool(error);c.reads+=op==2&&!error;hold(2);if(ack)acknowledge();
    }
    bool command(unsigned op,unsigned address,int32_t word,uint32_t base,unsigned error,int32_t result,bool valid,Hook hook=Hook::None,bool ack=true){
        need(d.cmd_ready&&!d.rsp_valid,"ANEXT_CANCEL_COMMAND_READY");uint32_t generation=d.image_generation;
        if(op==0 || ((!error || error==11) && (op==2||op==3||op==4)))++generation;
        d.cmd_opcode=op;d.cmd_address=address;d.cmd_word=uint32_t(word);d.cmd_base=base;d.cmd_valid=1;step();d.cmd_valid=0;
        bool injected=false,committed=false;unsigned waited=0;
        while(!d.rsp_valid && waited<8*N+200){
            clear_compute();d.clk=0;d.eval();
            if(!injected && hook==Hook::HostWrite && d.new_hw_en){d.compute_write_en=1;d.compute_write_offset=T-1;d.compute_write_mask=0x8000;d.compute_write_words[15]=29;injected=true;}
            if(!injected && hook==Hook::CanonicalRead && d.canonical_read_en){d.compute_read_en=1;d.compute_read_offset=T-1;d.compute_read_mask=0xffff;d.compute_read_tag=N-1;injected=true;}
            d.eval();if(d.new_image_write_accept && d.new_write_kind==2){need(d.old_image_write_accept,"ANEXT_CANCEL_HOST_WRITE_PAIR");need(d.new_write_offset==address%T && d.new_write_mask==(1u<<(address/T)) && d.new_write_words[address/T]==uint32_t(word),"ANEXT_CANCEL_LATCHED_HOST_WORD");committed=true;}
            need(!d.cmd_ready,"ANEXT_CANCEL_BUSY_BACKPRESSURE");d.cmd_opcode=7;d.cmd_address=N-1;d.cmd_word=0x80000000u;d.cmd_base=0xffffffffu;d.cmd_valid=waited==2;step();d.cmd_valid=0;++waited;
        }
        clear_compute();d.eval();need(d.rsp_valid && (hook==Hook::None||injected),"ANEXT_CANCEL_COMMAND_TIMEOUT_OR_HOOK");
        c.max_latency=std::max(c.max_latency,uint64_t(waited));
        response(op,error,result,valid,generation,ack);return committed;
    }
    void reload(uint32_t base,const Signed& values){
        command(0,0,0,base,0,0,false);host.base=base;host.low.fill(0);host.high.fill(0);
        for(unsigned j=0;j<N;++j){need(values[j]>=-1 && values[j]<base,"ANEXT_CANCEL_LOAD_DOMAIN");host.raw[j]=uint32_t(int32_t(values[j]));command(1,j,int32_t(values[j]),base,0,0,j==N-1);}
        host=normalized(host);check_ram();
    }
    void read(unsigned address,bool ack=true){auto logical=effective(host);command(2,address,0,host.base,0,int32_t(logical[address]),true,Hook::None,ack);}
    void write(unsigned address,int32_t value){host.raw[address]=uint32_t(value);unsigned b=address/T,row=address%T;if(row==0)host.low[b]=0;if(row==1)host.high[b]=0;host=normalized(host);command(3,address,value,host.base,0,0,true);check_ram();}
    void host_suite(){
        Signed values{};for(unsigned j=0;j<N;++j)values[j]=(j*13+7)%101;reload(1000,values);for(unsigned j=0;j<N;++j)read(j);check_ram();write(0,-1);read(0);write(N-1,-1);read(N-1);write(0,7);read(0);command(4,0,0,1000000000,0,0,true);host.base=1000000000;read(N/2);check_ram();++c.host_cases;
        values.fill(0);values[0]=-1;reload(MIN_BASE,values);read(0);read(N-1);write(0,9);read(0);++c.host_cases;
        // E0 accepts legal LOAD_WORD while illegal external compute offset
        // registers image_error. E1 sees that error and raises real bus.cancel,
        // while host_word captures ACCESS. Canceled raw host intent must not
        // fall through to unrelated compute payload or reach any actual RAM.
        command(0,0,0,1000,0,0,false);host.base=1000;host.low.fill(0);host.high.fill(0);host.raw[0]=31;command(1,0,31,1000,0,0,false);check_ram();
        uint32_t generation=d.image_generation;d.cmd_valid=1;d.cmd_opcode=1;d.cmd_address=1;d.cmd_word=43;d.cmd_base=1000;d.compute_write_en=1;d.compute_write_offset=T;d.compute_write_mask=1;d.compute_write_words[0]=55;step();d.cmd_valid=0;clear_compute();need(d.compute_memory_error && d.host_begin,"ANEXT_CANCEL_SEAM_REGISTERED_ERROR");step();
        need(d.square_cancel && d.rsp_valid && d.rsp_error_code==11 && !d.old_hw_en && !d.new_hw_en && d.new_hw_select,"ANEXT_CANCEL_SEAM_PENDING_ACCESS");
        d.compute_write_en=1;d.compute_write_offset=0;d.compute_write_mask=0x8000;d.compute_write_words[15]=91;d.clk=0;d.eval();
        need(!d.old_image_write_accept&&!d.new_image_write_accept && d.new_write_kind==2 && d.new_write_offset==1 && d.new_write_mask==1 && d.new_write_words[0]==43,"ANEXT_CANCEL_NO_HOST_FALLBACK_OR_COMMIT");step();clear_compute();d.eval();check_ram();response(1,11,0,false,generation);quiet(12);command(2,0,0,1000,3,0,false);values.fill(0);reload(1000,values);read(1);++c.host_cases;++c.seams;
        read(0,false);Response held(d);d.compute_write_en=1;d.compute_write_offset=T;d.compute_write_mask=1;d.compute_write_words[0]=3;step();clear_compute();step();need(d.fault_sticky&&!d.image_valid&&held.equals(d),"ANEXT_CANCEL_LATER_FAULT_HELD_SUCCESS");hold(3);quiet(12);acknowledge();check_ram();reload(MIN_BASE,values);read(N-1);++c.host_cases;++c.seams;
        bool committed=command(3,2,17,MIN_BASE,11,0,false,Hook::HostWrite);need(!committed,"ANEXT_CANCEL_OVERLAP_ATOMIC_HOST_WRITE");check_ram();quiet(8);reload(MIN_BASE,values);read(2);++c.host_cases;++c.seams;
        committed=command(3,0,19,MIN_BASE,11,0,false,Hook::CanonicalRead);need(committed,"ANEXT_CANCEL_PRIOR_COMMIT_NOT_ROLLED_BACK");host.raw[0]=19;check_ram();quiet(8);reload(MIN_BASE,values);read(0);++c.host_cases;++c.seams;
    }
    void image_meta(){need(d.i_configured && d.i_active_base==image.base && d.i_active_generation==17,"ANEXT_CANCEL_IMAGE_CONFIG");for(unsigned b=0;b<16;++b)need(int32_t(d.i_c0_words[b])==image.low[b] && int32_t(d.i_c1_words[b])==image.high[b],"ANEXT_CANCEL_IMAGE_CORRECTION_ORACLE");}
    void image_read(unsigned row,uint16_t mask,bool corrections){clear_image();d.i_read_en=1;d.i_read_offset=row;d.i_read_tag=(row+3)%N;d.i_read_mask=mask;d.i_read_apply_corrections=corrections;step();need(d.i_read_valid && d.i_read_tag_out==(row+3)%N && d.i_read_mask_out==mask && d.i_read_generation==17 && !d.i_error,"ANEXT_CANCEL_IMAGE_READ_E0");for(unsigned b=0;b<16;++b)if(mask&(1u<<b)){int64_t expected=int32_t(image.raw[b*T+row]);if(corrections)expected+=row==0?image.low[b]:row==1?image.high[b]:0;need(signed33(d.i_read_words,b)==expected,"ANEXT_CANCEL_SIGNED33_READ");++c.image_reads;}}
    void image_suite(){
        clear_image();d.i_configure=1;d.i_clear_image=1;step();image_meta();
        for(unsigned row=0;row<T;++row){clear_image();d.i_write_en=1;d.i_write_offset=row;d.i_write_mask=0xffff;for(unsigned b=0;b<16;++b){image.raw[b*T+row]=((b+1)*19+row*7)%101;d.i_write_words[b]=image.raw[b*T+row];}step();need(!d.i_error,"ANEXT_CANCEL_IMAGE_INITIAL_WRITE");}check_ram(true);
        for(unsigned row=0;row<T;++row)image_read(row,row&1?0x5a5a:0xffff,false);
        clear_image();d.i_boundary_commit=1;for(unsigned b=0;b<16;++b){d.i_boundary_low_words[b]=b+1;d.i_boundary_high_words[b]=uint32_t(int32_t(b%3)-1);unsigned destination=(b+1)%16;image.low[destination]=(b==15?-1:1)*int32_t(b+1);image.high[destination]=(b==15?-1:1)*(int32_t(b%3)-1);}step();image_meta();image_read(0,0xffff,true);image_read(1,0xffff,true);check_ram(true);
        clear_image();d.i_write_en=1;d.i_write_kind=2;d.i_write_offset=0;d.i_write_mask=1u<<5;d.i_write_words[5]=0xffffffffu;image.raw[5*T]=0xffffffffu;image.low[5]=0;step();need(!d.i_error && !(d.i_shadow0_valid&(1u<<5)),"ANEXT_CANCEL_PARTIAL_HOST_MINUS1");
        clear_image();d.i_write_en=1;d.i_write_kind=2;d.i_write_offset=1;d.i_write_mask=1u<<7;d.i_write_words[7]=image.base-1;image.raw[7*T+1]=image.base-1;image.high[7]=0;step();need(!d.i_error && !(d.i_shadow1_valid&(1u<<7)),"ANEXT_CANCEL_PARTIAL_HOST_CORRECTION_CLEAR");image_read(0,0xffff,true);image_read(1,0xffff,true);check_ram(true);
        for(unsigned test=0;test<7;++test){clear_image();unsigned code=0;
            if(test==0){d.i_write_en=1;d.i_write_kind=2;d.i_write_mask=3;d.i_write_words[0]=8;d.i_write_words[1]=0xfffffffeu;code=6;}
            if(test==1){d.i_write_en=1;d.i_write_mask=4;d.i_write_words[2]=image.base;code=6;}
            if(test==2){d.i_configure=1;d.i_base=MIN_BASE-1;code=2;}
            if(test==3){d.i_read_en=1;d.i_read_mask=1;d.i_generation=18;code=3;}
            if(test==4){d.i_read_en=1;d.i_write_en=1;d.i_read_mask=1;d.i_write_mask=1;code=5;}
            if(test==5){d.i_configure=1;d.i_clear_corrections=1;code=1;}
            if(test==6){d.i_boundary_commit=1;d.i_boundary_low_words[0]=image.base;code=7;}
            step();need(d.i_error && d.i_error_code==code && !d.i_read_valid,"ANEXT_CANCEL_IMAGE_TYPED_FAULT");image_meta();check_ram(true);++c.image_faults;clear_image();step();need(!d.i_error&&!d.i_read_valid,"ANEXT_CANCEL_IMAGE_FAULT_PULSE");
        }
        for(unsigned test=0;test<8;++test){image_read(0,0xffff,true);uint16_t shadow0=d.i_shadow0_valid,shadow1=d.i_shadow1_valid;clear_image();d.i_cancel=1;
            if(test==0){d.i_configure=1;d.i_clear_image=1;d.i_base=MIN_BASE-1;d.i_generation=99;}
            if(test==1||test==2){d.i_write_en=1;d.i_write_kind=2;d.i_write_mask=0xffff;d.i_write_offset=test==2?T:0;for(unsigned b=0;b<16;++b)d.i_write_words[b]=test==2?0xfffffffeu:0xffffffffu;}
            if(test==3){d.i_read_en=1;d.i_read_mask=0xffff;d.i_read_apply_corrections=1;}
            if(test==4||test==5){d.i_boundary_commit=1;for(unsigned b=0;b<16;++b){d.i_boundary_low_words[b]=test==5?image.base:1;d.i_boundary_high_words[b]=test==5?K+1:1;}}
            if(test==6){d.i_clear_corrections=1;d.i_set_minus_one=1;}
            if(test==7){d.i_configure=1;d.i_clear_image=1;d.i_read_en=1;d.i_write_en=1;d.i_boundary_commit=1;d.i_clear_corrections=1;d.i_set_minus_one=1;d.i_generation=99;d.i_read_mask=0xffff;d.i_write_mask=0xffff;}
            d.clk=0;d.eval();need(!d.old_i_write_accept&&!d.new_i_write_accept,"ANEXT_CANCEL_IMAGE_SAME_EDGE_KILL");step();need(!d.i_error && !d.i_error_code && !d.i_read_valid && !d.i_read_mask_out && d.i_shadow0_valid==shadow0 && d.i_shadow1_valid==shadow1,"ANEXT_CANCEL_IMAGE_PUBLICATION_AND_SHADOW_FREEZE");image_meta();check_ram(true);++c.image_cancels;
        }
        clear_image();d.rst_n=0;step();d.rst_n=1;step();need(!d.i_configured && !d.i_read_valid && !d.i_error && !d.i_shadow0_valid && !d.i_shadow1_valid && !d.rsp_valid && !d.image_valid,"ANEXT_CANCEL_RESET_ELIGIBILITY");check_ram(true);
        image.low.fill(0);image.high.fill(0);clear_image();d.i_configure=1;d.i_clear_image=1;step();
        for(unsigned row=0;row<T;++row){clear_image();d.i_write_en=1;d.i_write_mask=0xffff;d.i_write_offset=row;for(unsigned b=0;b<16;++b){d.i_write_words[b]=0;image.raw[b*T+row]=0;}step();}
        check_ram(true);for(unsigned row=0;row<T;++row)image_read(row,0xffff,false);clear_image();step();
    }
};
int main(int argc,char** argv){try{
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);DUT d{&context};
    if(argc==2&&std::string(argv[1])=="--runtime-probe"){std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";return context.threads()==1&&d.threads()==1?0:2;}
    bool negative=argc==2&&std::string(argv[1])=="--negative-oracle";need(argc==1||negative,"ANEXT_CANCEL_ARGUMENTS");Bench bench(d,negative);bench.host_suite();bench.image_suite();const auto& c=bench.c;
    need(c.commands==7*N+29 && c.reads==N+12 && c.errors==4 && c.holds==14*N+61 && c.host_cases==6 && c.seams==4 && c.ram==17*N && c.image_reads==28*T+192 && c.image_faults==7 && c.image_cancels==8 && c.image_ram==20*N,"ANEXT_CANCEL_EXACT_COUNTERS");
    // Calendar derives from accepted command wait edges, real E97 setup,
    // E2 host child and N+3 ordinary/T+1 special canonical tail. Peeks do
    // not advance clk. No elapsed host-time/implicit sleep enters this count.
    need(bench.edge==67*N+5*T+1139 && c.max_latency==std::max(100u,2*N+12),"ANEXT_CANCEL_EXACT_EDGE_CALENDAR");
    need(!negative,"ANEXT_CANCEL_NEGATIVE_MISSED");need(context.threads()==1&&d.threads()==1,"ANEXT_CANCEL_THREADS");
    std::cout<<"ANEXT_CANCEL_HOST_PAIR_PASS aw="<<AW<<" commands="<<c.commands<<" readbacks="<<c.reads<<" error_responses="<<c.errors<<" explicit_hold_checks="<<c.holds<<" host_cases="<<c.host_cases<<" cancel_seams="<<c.seams<<" ram_words="<<c.ram<<" image_read_words="<<c.image_reads<<" image_faults="<<c.image_faults<<" image_cancels="<<c.image_cancels<<" image_ram_words="<<c.image_ram<<" ticks="<<bench.edge<<" max_latency="<<c.max_latency<<"\n";
    d.final();return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 1;}}
