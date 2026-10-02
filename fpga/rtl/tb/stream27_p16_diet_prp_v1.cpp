// Own P16 diet full-PRP driver; no P8 schedule or numeric result inherited.
#include "stream27_p16_diet_prp_helpers_v1.h"
static std::vector<Program> prp_programs(const char* path){
    std::ifstream in(path);unsigned aw=0,count=0;in>>aw>>count;
    need(aw==5&&AW==5&&P==16&&MIN_BASE==300&&count==8,"P16_PRP_HEADER");
    std::vector<Program> out;
    for(unsigned i=0;i<count;++i){
        Program p{};unsigned size=0;in>>p.base>>size;p.paired=true;
        need(p.base>=MIN_BASE&&p.base<=1000000000&&size>32&&size<=1000,"P16_PRP_BOUND");
        p.initial[0]=1;
        for(unsigned j=0;j<size;++j){unsigned bit=2;in>>bit;need(bit<2,"P16_PRP_BIT");p.bits.push_back(bit);}
        for(auto& x:p.expected){int64_t v;in>>v;need(v>=-1&&v<int64_t(p.base),"P16_PRP_DIGIT");x=int32_t(v);}
        out.push_back(p);
    }
    need(!in.fail(),"P16_PRP_PARSE");std::string extra;need(!(in>>extra),"P16_PRP_TRAILING");return out;
}
int main(int argc,char** argv){try{
    if(argc==2&&std::string(argv[1])=="--runtime-probe")return scalar_regression_main(argc,argv);
    need(argc==2,"P16_PRP_ARGUMENTS");auto list=prp_programs(argv[1]);
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);DUT d{&context};FeedCounts c;
    reset(d);unsigned index=0;uint64_t cycles=0;
    for(const auto& p:list){
        // One initial load per complete PRP; never reload/reset within its chain.
        d.base=p.base;load(d,p.initial);chain_run(d,p,false,c);
        need(d.profile_loads==1&&d.profile_hits==0,"P16_PRP_BASE_CHANGE_CACHE_MISS");
        auto elapsed=d.cycles;cycles+=elapsed;long_production(d,p);long_compare(d,p,c);
        bool is_one=p.expected[0]==1;for(unsigned a=1;a<N;++a)is_one=is_one&&p.expected[a]==0;
        std::cout<<"P16_PRP_CASE index="<<index++<<" base="<<p.base<<" operations="<<p.bits.size()
                 <<" cycles="<<elapsed<<" prp="<<unsigned(is_one)<<" reads="<<N<<"\n";
    }
    need(c.jobs==8&&c.rows==16&&c.reads==256&&c.pushes==c.pops&&c.pops==c.operations-8
         &&c.backpressure>0&&c.full_exchange>0,"P16_PRP_COVERAGE");
    std::cout<<"P16_PRP_PASS cases="<<c.jobs<<" operations="<<c.operations<<" descriptors="<<c.pops
             <<" rows="<<c.rows<<" reads="<<c.reads<<" cycles="<<cycles<<" base_floor="<<MIN_BASE<<"\n";
    need(context.threads()==1&&d.threads()==1,"P16_PRP_THREADS");d.final();return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
