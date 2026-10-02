// Independent bounded flat-memory/math/calendar oracle. Standard C++ only.
// This is a native component test when compiled on an admitted Linux worker;
// reading/running its Python source guards is not native RTL validation.
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include <verilated.h>
#include "Vgenefer_anext_field_reset_probe_v1.h"
#ifndef ANEXT_RESET_AW
#error "ANEXT_RESET_AW must match the compiled RTL AW parameter"
#endif
constexpr unsigned AW=ANEXT_RESET_AW,N=1u<<AW,T=N/16;
constexpr unsigned PAIR=AW==8?1:0;
constexpr std::array<uint32_t,3> PRIMES{104857601,69206017,67239937};
constexpr std::array<uint32_t,3> GENERATORS{3,5,10};
static_assert(AW==5 || AW==8,"ANEXT_RESET_COMPONENT_AW5_AW8_ONLY");
static void need(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
static uint32_t power(uint32_t a,uint64_t k,uint32_t p){
    uint32_t v=1;while(k){if(k&1)v=uint64_t(v)*a%p;a=uint64_t(a)*a%p;k>>=1;}return v;
}
static uint32_t ordinary_montgomery(uint32_t a,uint32_t b,unsigned f){
    const uint32_t p=PRIMES[f],r=uint64_t(1ull<<32)%p;
    return uint64_t(uint64_t(a)*b%p)*power(r,p-2,p)%p;
}
static std::array<uint32_t,4> header(unsigned f){
    const uint32_t p=PRIMES[f],r=uint64_t(1ull<<32)%p;
    return {0x41313000u,N,uint32_t(uint64_t(uint64_t(r)*r%p)*power(N,p-2,p)%p),
            power(GENERATORS[f],(p-1)/(2*N),p)};
}
static unsigned bank(unsigned a){unsigned b=0;for(unsigned j=0;j<AW;++j)b^=((a>>j)&1)<<(j%7);return b;}
struct Write {uint64_t leaf;unsigned offset,mask;std::array<uint32_t,48> words;};
struct Read {uint64_t leaf,caller;unsigned offset,mask;uint32_t generation;std::array<uint32_t,48> words{};};
struct Product {uint64_t due;std::array<uint32_t,3> words;};

class Bench {
public:
    Vgenefer_anext_field_reset_probe_v1& d;
    std::array<std::vector<uint32_t>,3> flat;
    std::vector<Write> writes;
    std::vector<Read> reads;
    std::vector<Product> products;
    uint64_t edge=0,observed_read_edges=0,observed_write_edges=0;
    uint64_t expected_read_edges=0,expected_write_edges=0;
    uint64_t accepted_reads=0,accepted_writes=0,caller_responses=0;
    unsigned mult_accepted=0,mult_completed=0,rom_started=0,rom_word_edges=0;
    unsigned full_reloads=0,tail_windows=0,rom_completed=0;
    bool guard=false,driver=false,outer=false,transfer_error=false,poison_pending=false;
    bool rom_busy=false,rom_valid=false,loaded=false;
    unsigned rom_index=0,rom_address=0,profile_count=0;
    uint32_t profile_generation=0;
    explicit Bench(Vgenefer_anext_field_reset_probe_v1& model):d(model){for(auto& plane:flat)plane.resize(N);}
    bool raw_live()const{return d.rst_n && !d.cancel && !d.failed && !outer;}
    void quiet(){
        d.transfer_read_en=0;d.transfer_write_en=0;d.direct_start=0;d.direct_mult_valid=0;
        d.sim_bad_response_tag=0;d.sim_drop_response=0;
    }
    void clear_leaf_model(){
        guard=false;driver=false;products.clear();rom_busy=false;rom_valid=false;loaded=false;
        rom_index=0;rom_address=0;profile_count=0;profile_generation=0;
    }
    void settle(){
        d.clk=0;d.eval();
        if(!d.rst_n){outer=false;transfer_error=false;reads.clear();writes.clear();poison_pending=false;}
        if(!raw_live())clear_leaf_model();
        need(d.field_rst_n==(driver?7:0),"ANEXT_RESET_FIELD_DRIVERS");
        need(d.field_allow==(raw_live() && driver?7:0),"ANEXT_RESET_RAW_ALLOW");
        need(bool(d.reset_ready)==bool(raw_live() && driver),"ANEXT_RESET_EARLY_READY");
        need(bool(d.kill)==!raw_live(),"ANEXT_RESET_RAW_KILL");
        if(!raw_live() || !driver){
            need(!d.physical_read && !d.physical_write,"ANEXT_RESET_ASSERTION_PHYSICAL_ACCESS");
            need(!d.caller_valid && !d.mult_valid && !d.rom_valid && !d.rom_done && !d.profile_loaded,
                 "ANEXT_RESET_STALE_VALID");
            for(unsigned f=0;f<3;++f)need(d.mult_results[f]==0,"ANEXT_RESET_MULT_PAYLOAD_RESET");
        }
    }
    void tick(){
        settle();
        const bool old_outer=outer,old_error=transfer_error;
        const bool live=raw_live(),allow=live && driver;
        const bool transfer_cancel=d.cancel || d.failed || old_outer;
        bool response_now=false;
        for(const auto& r:reads)response_now|=r.caller==edge+2;
        const bool protocol_fault=!transfer_cancel && d.rst_n && response_now &&
            (d.sim_bad_response_tag || d.sim_drop_response || poison_pending);
        if(!d.rst_n || transfer_cancel || old_error || protocol_fault){reads.clear();writes.clear();}
        const bool accept_read=d.transfer_read_en && live && !old_error && !protocol_fault;
        const bool accept_write=d.transfer_write_en && live && !old_error && !protocol_fault;
        need(bool(d.accepted_transfer_read)==accept_read && bool(d.accepted_transfer_write)==accept_write,
             "ANEXT_RESET_TRANSFER_ACCEPTANCE");
        accepted_reads+=accept_read;accepted_writes+=accept_write;
        const bool start=d.direct_start && allow && !rom_busy;
        const bool multiply=d.direct_mult_valid && allow;
        need(d.accepted_start==(start?7:0) && d.accepted_mult==(multiply?7:0),"ANEXT_RESET_DIRECT_ACCEPTANCE");
        mult_accepted+=multiply;rom_started+=start;
        if(accept_write){
            Write w{edge+2,unsigned(d.write_offset),unsigned(d.write_mask),{}};
            need(w.offset<T,"ANEXT_RESET_ORACLE_WRITE_OFFSET");
            for(unsigned j=0;j<48;++j)w.words[j]=d.write_words[j];writes.push_back(w);
        }
        if(accept_read){
            need(d.read_offset<T,"ANEXT_RESET_ORACLE_READ_OFFSET");
            reads.push_back(Read{edge+2,edge+5,unsigned(d.read_offset),unsigned(d.read_mask),d.generation,{}});
        }
        bool physical_read=false,physical_write=false;
        for(auto& r:reads)if(r.leaf==edge && allow && !old_error && !protocol_fault){
            physical_read|=bool(r.mask);
            for(unsigned f=0;f<3;++f)for(unsigned lane=0;lane<16;++lane)
                r.words[f*16+lane]=flat[f][lane*T+r.offset];
        }
        for(const auto& w:writes)if(w.leaf==edge && allow && !old_error && !protocol_fault){
            physical_write|=bool(w.mask);
            for(unsigned f=0;f<3;++f)for(unsigned lane=0;lane<16;++lane)if(w.mask>>lane&1)
                flat[f][lane*T+w.offset]=w.words[f*16+lane];
        }
        need(d.physical_read==(physical_read?7:0),"ANEXT_RESET_TRANSFER_RAM_E2_READ");
        need(d.physical_write==(physical_write?7:0),"ANEXT_RESET_TRANSFER_RAM_E2_WRITE");
        observed_read_edges+=d.physical_read!=0;observed_write_edges+=d.physical_write!=0;
        expected_read_edges+=physical_read;expected_write_edges+=physical_write;
        if(multiply){
            Product p{edge+3,{}};for(unsigned f=0;f<3;++f)
                p.words[f]=ordinary_montgomery(d.mult_lhs[f],d.mult_rhs[f],f);
            products.push_back(p);
        }
        const bool old_rom_busy=rom_busy,old_rom_valid=rom_valid;
        const unsigned old_rom_address=rom_address;
        if(allow){
            if(start){loaded=false;profile_count=0;profile_generation=d.generation;}
            else if(old_rom_valid){
                if(old_rom_address==3 && profile_count==3){loaded=true;++rom_completed;}
                ++profile_count;
            }
            rom_valid=old_rom_busy;
            if(!old_rom_busy){if(start){rom_busy=true;rom_index=0;}}
            else {rom_address=rom_index;if(rom_index==3)rom_busy=false;else ++rom_index;}
        }else {rom_busy=false;rom_valid=false;loaded=false;profile_count=0;profile_generation=0;rom_address=0;rom_index=0;}
        if(!d.rst_n){outer=false;transfer_error=false;}
        else {outer=old_outer || old_error;transfer_error=transfer_cancel?false:(old_error || protocol_fault);}
        if(live){driver=guard;guard=true;}else {driver=false;guard=false;}
        d.clk=1;d.eval();
        // The sticky outer error asserts the same raw island predicate after
        // this edge; model its asynchronous clearing before post-edge checks.
        if(!raw_live())clear_leaf_model();
        need(bool(d.outer_fault)==outer,"ANEXT_RESET_OUTER_FAULT_STICKY");
        need(bool(d.transfer_error)==transfer_error,"ANEXT_RESET_ACTUAL_TRANSFER_PROTOCOL_ERROR");
        need(d.field_rst_n==(driver?7:0) && d.field_allow==(raw_live() && driver?7:0),"ANEXT_RESET_RELEASE_CALENDAR");
        need(bool(d.reset_ready)==bool(raw_live() && driver),"ANEXT_RESET_EARLY_READY");
        const Read* caller=nullptr;for(const auto& r:reads)if(r.caller==edge && raw_live() && driver)caller=&r;
        need(d.caller_valid==(caller?7:0),"ANEXT_RESET_STALE_VALID");
        caller_responses+=caller!=nullptr;
        if(caller){
            need(d.caller_generation==caller->generation,"ANEXT_RESET_BAD_GENERATION");
            for(unsigned f=0;f<3;++f){
                const uint32_t packed_offset=(d.caller_offsets>>(f*AW))&((1u<<AW)-1);
                need(packed_offset==caller->offset && ((d.caller_masks>>(f*16))&65535)==caller->mask,
                     "ANEXT_RESET_CALLER_E5_TAG");
                for(unsigned lane=0;lane<16;++lane)if(caller->mask>>lane&1)
                    need(d.caller_words[f*16+lane]==caller->words[f*16+lane],"ANEXT_RESET_RETAINED_FLAT_WORD");
            }
        }
        const Product* product=nullptr;for(const auto& p:products)if(p.due==edge)product=&p;
        need(d.mult_valid==(product?7:0),"ANEXT_RESET_MONT_E3_VALID");
        mult_completed+=product!=nullptr;
        if(product)for(unsigned f=0;f<3;++f)need(d.mult_results[f]==product->words[f],"ANEXT_RESET_ORDINARY_MONT_MATH");
        need(d.rom_busy==(rom_busy?7:0) && d.rom_valid==(rom_valid?7:0),"ANEXT_RESET_ROM_WORD_CALENDAR");
        rom_word_edges+=rom_valid;
        need(d.rom_done==(rom_valid && rom_address==3?7:0),"ANEXT_RESET_ROM_WORD3_DONE");
        need(d.profile_loaded==(loaded?7:0),"ANEXT_RESET_PROFILE_RESET_NOT_READY");
        for(unsigned f=0;f<3;++f){
            need(((d.profile_counts>>(3*f))&7)==profile_count,"ANEXT_RESET_PROFILE_COLLECTOR_COUNT");
            need(d.profile_generations[f]==profile_generation,"ANEXT_RESET_PROFILE_GENERATION");
            if(rom_valid){
                need(((d.rom_addresses>>(16*f))&65535)==rom_address,"ANEXT_RESET_ROM_FOUR_WORD_ORDER");
                need(d.rom_words[f]==header(f)[rom_address],"ANEXT_RESET_ROM_INDEPENDENT_HEADER");
            }
        }
        if(protocol_fault)poison_pending=false;
        for(auto it=writes.begin();it!=writes.end();)if(it->leaf<=edge)it=writes.erase(it);else ++it;
        for(auto it=reads.begin();it!=reads.end();)if(it->caller<=edge)it=reads.erase(it);else ++it;
        for(auto it=products.begin();it!=products.end();)if(it->due<=edge)it=products.erase(it);else ++it;
        need(observed_read_edges==expected_read_edges && observed_write_edges==expected_write_edges,
             "ANEXT_RESET_PHYSICAL_EDGE_COUNTERS");
        ++edge;
    }
    void advance(unsigned count){for(unsigned j=0;j<count;++j)tick();}
    void words(uint32_t gen,unsigned offset){for(unsigned f=0;f<3;++f)for(unsigned lane=0;lane<16;++lane)
        d.write_words[f*16+lane]=(uint64_t(gen)*1000003+uint64_t(lane*T+offset)*12345+f*701)%PRIMES[f];}
    void operands(unsigned sequence){for(unsigned f=0;f<3;++f){
        d.mult_lhs[f]=sequence&1?PRIMES[f]-1-sequence:sequence*117u;
        d.mult_rhs[f]=sequence&2?PRIMES[f]-2-sequence:sequence*719u;
    }}
    void release_and_prime(uint32_t gen){
        quiet();d.generation=gen;d.direct_start=1;d.direct_mult_valid=1;operands(gen);
        d.transfer_write_en=1;d.write_offset=0;d.write_mask=65535;words(gen,0);
        // First raw-live request E0 reaches the real leaf at E2, exactly when
        // two release edges have completed. Direct leaves reject E0 and E1.
        tick();need(!d.profile_loaded,"ANEXT_RESET_READY_IS_NOT_PROFILE_READY");
        d.transfer_write_en=0;tick();need(d.reset_ready && !d.profile_loaded,"ANEXT_RESET_TWO_EDGE_BARRIER");
        tick();quiet();advance(6);need(d.profile_loaded==7,"ANEXT_RESET_ROM_FULL_RELOAD");
    }
    void fill(uint32_t gen){
        quiet();d.generation=gen;
        for(unsigned offset=0;offset<T;++offset){d.transfer_write_en=1;d.write_offset=offset;d.write_mask=65535;words(gen,offset);tick();}
        quiet();advance(6);++full_reloads;
    }
    void check(){
        quiet();for(unsigned offset=0;offset<T;++offset){d.transfer_read_en=1;d.read_offset=offset;d.read_mask=65535;tick();}
        quiet();advance(6);
    }
    void tail(){
        quiet();advance(6);const auto before=observed_write_edges;
        for(unsigned j=0;j<16;++j){tick();need(!d.caller_valid && !d.mult_valid && !d.rom_valid && !d.rom_done &&
            !d.physical_read && !d.physical_write,"ANEXT_RESET_QUIET16_STALE_TAIL");}
        need(observed_write_edges==before,"ANEXT_RESET_QUIET16_PHYSICAL_WRITE_TAIL");++tail_windows;
    }
    void external_reset(){quiet();d.rst_n=0;settle();tick();d.rst_n=1;}
    void cancel_bundle(unsigned age,uint32_t gen){
        quiet();d.transfer_read_en=1;d.read_offset=0;d.read_mask=65535;
        d.direct_start=1;d.direct_mult_valid=1;operands(gen);tick();quiet();advance(age);
        d.cancel=1;d.transfer_write_en=1;d.write_offset=0;d.write_mask=65535;words(999,0);
        d.direct_start=1;d.direct_mult_valid=1;settle();tick();
        d.cancel=0;quiet();tail();
        // Tail includes the two release edges with no work. Assert again so
        // recovery below exercises first-eligible E0 rather than warm entry.
        d.cancel=1;tick();d.cancel=0;release_and_prime(gen);fill(gen);check();
    }
    void malformed(unsigned kind,uint32_t gen){
        quiet();d.transfer_read_en=1;d.read_offset=0;d.read_mask=65535;tick();quiet();advance(2);
        if(kind==0)d.sim_bad_response_tag=1;
        if(kind==1)d.sim_drop_response=1;
        if(kind==2){
            // Outside the legal whole-cancel contract: a subcycle pulse while
            // read_due is outstanding clears the leaf response, not transfer
            // tokens. The actual frozen protocol checker must quarantine it.
            d.cancel=1;settle();d.cancel=0;settle();poison_pending=true;
        }
        tick();need(d.transfer_error,"ANEXT_RESET_MALFORMED_REAL_ERROR");
        quiet();tick();need(d.outer_fault,"ANEXT_RESET_MALFORMED_OUTER_LATCH");
        d.cancel=1;tick();d.cancel=0;tail();
        need(d.outer_fault && !d.reset_ready,"ANEXT_RESET_FAULT_NOT_MASKED_BY_CANCEL");
        external_reset();release_and_prime(gen);fill(gen);check();
    }
    void baseline(){
        quiet();d.cancel=0;d.failed=0;d.sim_bad_generation=0;d.sim_early_ready=0;d.sim_stale_valid=0;
        d.rst_n=0;tick();d.rst_n=1;release_and_prime(1);fill(1);check();
        // Ordinary Montgomery boundary/burst values and fixed-ROM restart.
        for(unsigned j=0;j<8;++j){d.direct_mult_valid=1;operands(j);tick();}quiet();advance(4);
        d.direct_start=1;tick();quiet();advance(6);need(d.profile_loaded==7,"ANEXT_RESET_ROM_RESTART");
        // Actual same-bank/different-row behavior at AW8 and disjoint masks.
        if(AW==8){bool shared=false;for(unsigned r=0;r<16;++r)for(unsigned w=0;w<16;++w)
            shared|=bank(r*T)==bank(w*T+1) && (r*T>>7)!=(w*T+1>>7);
            need(shared && bank(0)==bank(8*T+1) && (0>>7)!=(8*T+1>>7),
                 "ANEXT_RESET_AW8_DISTINCT_RAM_ROWS");
            // Actual bank0 row0 read and bank0 row1 write on the same edge;
            // the independent flat image snapshots the old read before write.
            d.transfer_read_en=1;d.transfer_write_en=1;d.read_offset=0;d.write_offset=1;
            d.read_mask=1;d.write_mask=1u<<8;words(3,1);tick();quiet();advance(6);check();
        }
        d.transfer_read_en=1;d.transfer_write_en=1;d.read_offset=0;d.write_offset=0;
        d.read_mask=0x5555;d.write_mask=0xaaaa;words(2,0);tick();quiet();advance(6);check();tail();
        for(unsigned age:std::array<unsigned,3>{0,1,3})cancel_bundle(age,10+age);
        // Registered steady terminal FAILED flushes pending transfer tokens.
        d.transfer_read_en=1;d.read_offset=0;d.read_mask=65535;tick();quiet();d.failed=1;
        d.direct_start=1;d.direct_mult_valid=1;d.transfer_write_en=1;words(999,0);advance(3);
        d.failed=0;quiet();tail();d.failed=1;tick();d.failed=0;release_and_prime(20);fill(20);check();
        // Asynchronous assertion between edges while transfer is quiet kills
        // pending multiplier/ROM state; retained RAM must read back unchanged.
        d.direct_start=1;d.direct_mult_valid=1;operands(21);tick();quiet();
        d.cancel=1;settle();d.cancel=0;settle();advance(3);tail();check();
        // External reset with pending transfer + multiplier + ROM word zero.
        d.transfer_read_en=1;d.read_offset=0;d.read_mask=65535;d.direct_start=1;
        d.direct_mult_valid=1;operands(22);tick();quiet();advance(1);external_reset();
        release_and_prime(22);check();fill(22);check();tail();
        // Reset after real ROM word3 publication and before collector commit.
        d.direct_start=1;tick();quiet();advance(4);need(d.rom_valid==7 && d.rom_done==7,
            "ANEXT_RESET_PENDING_ROM_WORD3");external_reset();release_and_prime(23);fill(23);check();tail();
        for(unsigned kind=0;kind<3;++kind)malformed(kind,30+kind);
        tail();need(full_reloads==10 && tail_windows==12 && rom_completed==11,
             "ANEXT_RESET_SOURCE_DERIVED_SCENARIO_COUNTS");
        need(edge==571+23*T+PAIR*(13+T) && accepted_reads==13*T+9+PAIR*(T+1) && accepted_writes==10*T+11+PAIR &&
             observed_read_edges==13*T+5+PAIR*(T+1) && observed_write_edges==10*T+11+PAIR && caller_responses==13*T+1+PAIR*(T+1) &&
             mult_accepted==23 && mult_completed==19 && rom_started==17 && rom_word_edges==53,
             "ANEXT_RESET_SOURCE_DERIVED_EDGE_COUNTS");
        need(!outer && !transfer_error && d.transfer_quiet,"ANEXT_RESET_FINAL_RECOVERY_QUIET");
    }
};

static void baseline_footer(){
    std::cout<<"ANEXT_FIELD_RESET_BASELINE aw="<<AW<<" fields=3 banks=384 ram_depth="<<(AW>7?1u<<(AW-7):1u)
        <<" release_edges=2 direct_edge=3 transfer_ram=2 transfer_caller=5 mont=3 rom_words=4"
        <<" cancel_ages=0,1,3 quiet_tail=16 reloads=10 tail_windows=12 rom_completed=11"
        <<" edges="<<571+23*T+PAIR*(13+T)<<" read_accepts="<<13*T+9+PAIR*(T+1)<<" write_accepts="<<10*T+11+PAIR
        <<" physical_read_edges="<<13*T+5+PAIR*(T+1)<<" physical_write_edges="<<10*T+11+PAIR
        <<" caller_responses="<<13*T+1+PAIR*(T+1)<<" mult_accepts=23 mult_completed=19 rom_starts=17 rom_word_edges=53"
        <<" same_bank_row_pairs="<<PAIR<<"\n";
}
int main(int argc,char** argv){try{
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
    Vgenefer_anext_field_reset_probe_v1 d{&context};
    if(argc==2 && std::string(argv[1])=="--runtime-probe"){
        std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
        return context.threads()==1 && d.threads()==1?0:2;
    }
    const std::string mode=argc==1?"positive":argc==2?argv[1]:"invalid";
    need(mode=="positive" || mode=="--negative-bad-generation" || mode=="--negative-early-ready" ||
         mode=="--negative-stale-valid","ANEXT_RESET_ARGS");
    Bench b(d);b.baseline();baseline_footer();
    if(mode!="positive"){
        const std::string expected=mode=="--negative-bad-generation"?"ANEXT_RESET_BAD_GENERATION":
            mode=="--negative-early-ready"?"ANEXT_RESET_EARLY_READY":"ANEXT_RESET_STALE_VALID";
        bool caught=false;
        try {
            if(mode=="--negative-bad-generation"){
                d.sim_bad_generation=1;d.transfer_read_en=1;d.read_offset=0;d.read_mask=65535;b.tick();b.quiet();b.advance(5);
            }else {
                d.cancel=1;b.settle();b.tick();d.cancel=0;
                if(mode=="--negative-early-ready")d.sim_early_ready=1;else d.sim_stale_valid=1;
                b.settle();
            }
        }catch(const std::exception& e){need(e.what()==expected,"ANEXT_RESET_NEGATIVE_WRONG_ORACLE");caught=true;}
        need(caught,"ANEXT_RESET_NEGATIVE_NOT_DETECTED");d.final();
        std::cerr<<"ANEXT_RESET_NEGATIVE_"<<(mode=="--negative-bad-generation"?"BAD_GENERATION":
            mode=="--negative-early-ready"?"EARLY_READY":"STALE_VALID")<<"\n";
        return mode=="--negative-bad-generation"?41:mode=="--negative-early-ready"?42:43;
    }
    d.final();std::cout<<"ANEXT_FIELD_RESET_PASS aw="<<AW<<" fields=3 scope=real-leaf-component no_clock_claim=1\n";
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
