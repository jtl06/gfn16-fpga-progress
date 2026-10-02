// Own N256/P16 diet normal;18 feedback rows, dense signed state, no faults.
#include "stream27_p16_diet_prp_helpers_v1.h"
int main(int argc,char** argv){try{
    if(argc==2&&std::string(argv[1])=="--runtime-probe")return scalar_regression_main(argc,argv);
    need(argc==2&&AW==8&&N==256&&P==16&&MIN_BASE==599&&INTERVAL==214&&CARRY_DONE==214&&FIRST_DIGIT==195,"P16_DIET_AW8_SOURCE");
    std::ifstream in(argv[1]);unsigned aw=0,jobs=0,size=0;Program p{};p.paired=true;
    in>>aw>>jobs>>p.base>>size;need(aw==8&&jobs==1&&p.base==1000000000&&size==256,"P16_DIET_AW8_ASSET_HEADER");
    for(auto& v:p.initial){int64_t x;in>>x;need(x>=-1&&x<int64_t(p.base),"P16_DIET_AW8_SIGNED_INITIAL");v=int32_t(x);}
    for(unsigned i=0;i<size;++i){unsigned bit=2;in>>bit;need(bit<2,"P16_DIET_AW8_BIT");p.bits.push_back(bit);}
    for(auto& v:p.expected){int64_t x;in>>x;need(x>=-1&&x<int64_t(p.base),"P16_DIET_AW8_CANONICAL_EXPECTED");v=int32_t(x);}
    need(!in.fail(),"P16_DIET_AW8_PARSE");std::string extra;need(!(in>>extra),"P16_DIET_AW8_TRAILING");
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);DUT d{&context};FeedCounts c;
    reset(d);d.base=p.base;load(d,p.initial);chain_run(d,p,false,c);uint64_t cycles=d.cycles;
    need(d.profile_loads==1&&d.profile_hits==0,"P16_DIET_AW8_COLD_SETUP");
    long_production(d,p);long_compare(d,p,c);
    need(c.jobs==1&&c.operations==256&&c.pushes==255&&c.pops==255&&c.rows==16&&c.reads==256&&
         c.full_exchange>0&&c.backpressure>0&&!c.faults&&!c.aborts,"P16_DIET_AW8_ALL_RECURRENCE");
    need(context.threads()==1&&d.threads()==1,"P16_DIET_AW8_THREADS");
    std::cout<<"P16_DIET_AW8_NORMAL_PASS operations=256 descriptors=255 rows=16 reads=256 cycles="<<cycles<<" feedback_rows=18\n";
    d.final();return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
