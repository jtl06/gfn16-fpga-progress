// The captured v6 scalar regression remains executable unchanged apart from
// explicitly clearing the additive feed inputs. All long output is actual RAM.
#define main scalar_regression_main
#include "stream27_host_core_v1.cpp"
#undef main

struct Program{uint32_t base;bool paired;Image initial,expected;std::vector<unsigned> bits;};
struct FeedCounts{uint64_t jobs=0,operations=0,pushes=0,pops=0,backpressure=0,full_exchange=0,rows=0,reads=0,faults=0,aborts=0;};
static void feed_clear(DUT& d){clear(d);d.feed_mode=0;d.command_valid=0;d.command_double=0;d.command_index=0;d.command_generation=0;}
static std::vector<Program> programs(const char* path){
    std::ifstream file(path);unsigned aw=0,count=0;file>>aw>>count;
    need(file.good()&&aw==AW&&count==2,"S4_LONG_PROGRAM_HEADER");std::vector<Program> out;
    for(unsigned i=0;i<count;++i){Program p{};unsigned size=0,paired=0;file>>p.base>>size>>paired;
        need(p.base==1000000000&&size>32&&size<=10000&&paired<=1,"S4_LONG_PROGRAM_BOUND");p.paired=bool(paired);
        for(auto& x:p.initial){int64_t v;file>>v;need(v>=-1&&v<int64_t(p.base),"S4_LONG_INITIAL");x=int32_t(v);}
        for(unsigned j=0;j<size;++j){unsigned bit=2;file>>bit;need(bit<2,"S4_LONG_BIT");p.bits.push_back(bit);}
        for(auto& x:p.expected){int64_t v;file>>v;need(v>=-1&&v<int64_t(p.base),"S4_LONG_EXPECTED");x=int32_t(v);}
        out.push_back(p);
    }
    need(!file.fail(),"S4_LONG_PROGRAM_PARSE");std::string extra;need(!(file>>extra),"S4_LONG_PROGRAM_TRAILING");return out;
}
static uint64_t chain_done(unsigned count,bool hit,bool special){return (hit?3u:102u)+uint64_t(count-1)*INTERVAL+CARRY_DONE+2+(special?7u:6u)*N+N+4;}
static void chain_run(DUT& d,const Program& p,bool hit,FeedCounts& c){
    feed_clear(d);d.base=p.base;d.batch_mode=1;d.feed_mode=1;d.warm_count=uint32_t(p.bits.size());d.double_bit=p.bits[0];d.start=1;edge(d);
    need(d.busy&&!d.error&&!d.canonical_ready&&d.feed_level==0,"S4_LONG_START");
    unsigned count=unsigned(p.bits.size()),next=1,popped=0,gap=0;uint8_t generation=d.accepted_generation;
    uint64_t first=hit?3:102,last=chain_done(count,hit,p.expected[0]==-1),warm=first+uint64_t(count-1)*INTERVAL+CARRY_DONE+1;
    for(uint64_t elapsed=1;elapsed<=last;++elapsed){
        feed_clear(d);d.base=p.base;
        if(gap)--gap;
        else if(next<count){d.command_valid=1;d.command_index=next;d.command_generation=generation;d.command_double=p.bits[next];}
        d.clk=0;d.eval();bool push=d.command_accept,pop=d.operation_accept;unsigned level=d.feed_level;
        if(d.command_valid&&!d.command_ready)++c.backpressure;
        if(push&&pop&&level==4)++c.full_exchange;
        if(pop){++popped;++c.pops;need(elapsed==first+uint64_t(popped)*INTERVAL,"S4_LONG_POP_CALENDAR");}
        edge(d);
        if(push){++next;++c.pushes;if(next%17==0)gap=2;}
        need(!d.error,"S4_LONG_NATIVE_ERROR age="+std::to_string(elapsed)+" code="+std::to_string(d.feed_error_code));
        need(bool(d.done)==(elapsed==last)&&bool(d.busy)==(elapsed!=last),"S4_LONG_EXACT_HOST_DONE");
        need(bool(d.warm_done)==(elapsed==warm)&&!d.read_valid,"S4_LONG_WARM_NOT_READ_READY");
        need(d.feed_level<=4&&d.commands_enqueued==next-1&&d.commands_consumed==popped,"S4_LONG_ACTUAL_FIFO_ACCOUNTING");
        need(d.operations_started<=count&&d.completed_squares<=count,"S4_LONG_ORDINAL_BOUND");
        if(elapsed<first+uint64_t(count-1)*INTERVAL+FIRST_DIGIT+1)
            need(d.final_image_rows==0,"S4_LONG_NO_EPOCH_ALIAS_PUBLICATION");
    }
    need(next==count&&popped==count-1&&d.operations_started==count&&d.completed_squares==count,"S4_LONG_FULL_COMMAND_COMPLETION");
    need(d.feed_level==0&&d.canonical_ready&&d.final_image_rows==N/16&&d.cycles==last,"S4_LONG_TRUE_LAST_CANONICAL_COPY");
    need(d.canonical_cycles==(p.expected[0]==-1?7u:6u)*N&&d.image_copy_cycles==N+3,"S4_LONG_FINALIZATION_COST");
    need(d.root_cycles==(hit?0u:99u)&&d.conversion_cycles==N/16&&d.crt_cycles==0&&
        d.cycles==d.root_cycles+d.conversion_cycles+d.ntt_cycles+d.carry_cycles,"S4_LONG_PHASE_COST");
    c.rows+=d.final_image_rows;c.operations+=count;++c.jobs;feed_clear(d);edge(d);need(!d.done&&!d.busy&&!d.error,"S4_LONG_SINGLE_DONE");
}
static void long_production(DUT& d,const Program& p){
    for(unsigned bit:p.bits){feed_clear(d);d.base=p.base;d.t5b_start=1;d.t5b_double_bit=bit;edge(d);
        need(d.t5b_busy&&!d.t5b_error,"S4_LONG_T5B_START");unsigned elapsed=0;
        while(!d.t5b_done&&elapsed<100000){feed_clear(d);edge(d);need(!d.t5b_error&&!d.error,"S4_LONG_T5B_ERROR");++elapsed;}
        need(d.t5b_done&&!d.t5b_busy&&!d.t5b_error,"S4_LONG_T5B_DONE");feed_clear(d);edge(d);
    }
}
static void long_compare(DUT& d,const Program& p,FeedCounts& c){
    for(unsigned a=0;a<N;++a){feed_clear(d);d.read_en=1;d.host_addr=a;if(p.paired){d.t5b_read_en=1;d.t5b_host_addr=a;}edge(d);
        need(d.read_valid&&d.canonical_ready&&!d.error,"S4_LONG_ACTUAL_E0_RAM_READ");
        need(word(d.read_data)==p.expected[a],"S4_LONG_POW_TYPED address="+std::to_string(a)+" expected="+std::to_string(p.expected[a])+" actual="+std::to_string(word(d.read_data)));
        if(p.paired)need(d.t5b_read_valid&&word(d.t5b_read_data)==p.expected[a],"S4_LONG_T5B_SIGNED96_EQUALITY");++c.reads;
    }feed_clear(d);edge(d);need(!d.read_valid&&!d.t5b_read_valid,"S4_LONG_READ_II1_DRAIN");
}
static void feed_fault(DUT& d,unsigned type,FeedCounts& c){
    reset(d);Image zero{};load(d,zero);feed_clear(d);d.base=MIN_BASE;d.batch_mode=1;d.feed_mode=1;d.warm_count=2;d.start=1;edge(d);
    unsigned expected=type==0?102+INTERVAL+1:1,code=type==0?1:(type==1?2:(type==2?3:4));
    for(unsigned elapsed=1;elapsed<=expected;++elapsed){feed_clear(d);
        if(type!=0&&elapsed==1){d.command_valid=1;d.command_index=type==2?2:(type==3?0:1);d.command_generation=d.accepted_generation+(type==1?1:0);}
        edge(d);need(bool(d.error)==(elapsed==expected),"S4_LONG_REGISTERED_FEED_FAULT_CYCLE");
    }
    need(d.error&&d.done&&!d.busy&&!d.canonical_ready&&d.feed_error_code==code&&!d.read_valid,"S4_LONG_FEED_QUARANTINE");
    for(unsigned k=0;k<5;++k){feed_clear(d);d.command_valid=1;d.start=1;d.read_en=1;d.load_we=1;edge(d);
        need(d.error&&!d.done&&!d.busy&&!d.command_ready&&!d.read_valid,"S4_LONG_STICKY_NO_SUCCESS");}
    reset(d);load(d,zero);Job recovered{};recovered.base=MIN_BASE;recovered.count=1;
    candidate(d,recovered,false,10,type);production(d,recovered);Counts old;compare(d,recovered,10,type,false,old);++c.faults;
}
static void feed_abort(DUT& d,unsigned age,FeedCounts& c){
    reset(d);Image zero{};load(d,zero);feed_clear(d);d.base=MIN_BASE;d.batch_mode=1;d.feed_mode=1;d.warm_count=20;d.start=1;edge(d);
    unsigned next=1;
    for(unsigned elapsed=1;elapsed<=age;++elapsed){feed_clear(d);d.command_valid=next<20;d.command_index=next;d.command_generation=d.accepted_generation;
        d.clk=0;d.eval();bool push=d.command_accept;edge(d);if(push)++next;need(d.busy&&!d.error&&!d.done,"S4_LONG_ABORT_ACTIVE");}
    need(d.feed_level==4,"S4_LONG_ABORT_NONEMPTY");reset(d);
    need(d.feed_level==0&&d.commands_enqueued==0&&d.commands_consumed==0&&d.operations_started==0&&!d.command_ready,"S4_LONG_RESET_FIFO_ELIGIBILITY");
    for(unsigned k=0;k<8;++k){feed_clear(d);edge(d);need(!d.busy&&!d.done&&!d.error&&!d.warm_done&&!d.read_valid,"S4_LONG_RESET_NO_STALE_WORK");}
    load(d,zero);Job recovered{};recovered.base=MIN_BASE;recovered.count=1;candidate(d,recovered,false,11,age);production(d,recovered);Counts old;compare(d,recovered,11,age,false,old);++c.aborts;
}
int main(int argc,char** argv){try{
    if(argc==2&&std::string(argv[1])=="--runtime-probe")return scalar_regression_main(argc,argv);
    if(argc==3&&std::string(argv[2])=="--negative")return scalar_regression_main(argc,argv);
    bool ordinal=argc==2&&std::string(argv[1])=="--ordinal",negative=argc==4&&std::string(argv[3])=="--negative-feed";
    need(ordinal||argc==3||negative,"S4_LONG_ARGUMENTS");
    if(!ordinal){int oldargc=2;int rc=scalar_regression_main(oldargc,argv);if(rc)return rc;}
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);DUT d{&context};FeedCounts c;
    if(ordinal){reset(d);Program p{};p.base=1000000000;p.bits.resize(65540);for(unsigned i=0;i<p.bits.size();++i)p.bits[i]=i&1;
        load(d,p.initial);chain_run(d,p,false,c);long_compare(d,p,c);
        need(c.operations==65540&&c.pops==65539&&c.rows==N/16&&c.full_exchange>0,"S4_LONG_16BIT_ALIAS_WITNESS");
        std::cout<<ORDINAL_LABEL<<" operations="<<c.operations<<" descriptors="<<c.pops<<" true_final_rows="<<c.rows<<" reads="<<c.reads<<"\n";
    }else{
        auto list=programs(argv[2]);reset(d);bool hit=false;
        for(const auto& p:list){load(d,p.initial);chain_run(d,p,hit,c);hit=true;if(p.paired)long_production(d,p);long_compare(d,p,c);}
        need(c.backpressure>0&&c.full_exchange>0,"S4_LONG_NATIVE_FULL_FIFO_COVERAGE");
        if(negative)throw std::runtime_error("S4_LONG_CONTROL_TYPED expected="+std::to_string(c.operations+1)+" actual="+std::to_string(c.operations));
        for(unsigned type=0;type<4;++type)feed_fault(d,type,c);
        feed_abort(d,10,c);feed_abort(d,102+INTERVAL+8,c);
        std::cout<<LONG_LABEL<<" jobs="<<c.jobs<<" operations="<<c.operations<<" descriptors="<<c.pops<<" true_final_rows="<<c.rows<<" reads="<<c.reads<<" faults="<<c.faults<<" reset_aborts="<<c.aborts<<"\n";
    }
    need(context.threads()==1&&d.threads()==1,"S4_LONG_THREADS");d.final();return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
