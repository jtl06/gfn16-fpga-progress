#include "Vgenefer_stream27_l7_resetfree_mutants_v1.h"
#include "verilated.h"
#include <cstdint>
#include <deque>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>
#ifndef TEST_P
#error TEST_P must match RTL
#endif
static constexpr uint32_t P=TEST_P;
static uint64_t power(uint64_t a,uint64_t n){uint64_t y=1;for(;n;n>>=1,a=a*a%P)if(n&1)y=y*a%P;return y;}
struct Pending{uint64_t due;uint32_t expected;};
int main(int argc,char**argv){try{
 VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);
 Vgenefer_stream27_l7_resetfree_mutants_v1 d{&context};
 if(argc==2&&std::string(argv[1])=="--thread-probe"){
  std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
  return context.threads()==1&&d.threads()==1?0:2;
 }
 if(argc!=1)throw std::runtime_error("L7_ARGUMENTS");
 const uint64_t inverse=power((uint64_t(1)<<32)%P,P-2);
 if(((uint64_t(1)<<32)%P)*inverse%P!=1)throw std::runtime_error("L7_ORACLE_INVERSE");
 std::deque<Pending> pending;uint64_t edge=0,checked=0,canceled=0,holds=0,retained=0;
 uint32_t held_lazy=0,held_canonical=0,held_old=0,bad_held[5]{};unsigned detected=0;
 auto tick=[&](bool reset,bool valid,uint32_t lhs,uint32_t rhs,bool cancel=false){
  const bool active=reset&&!cancel;
  d.clk=0;d.rst_n=reset;d.cancel=cancel;d.in_valid=valid;d.lhs=lhs;d.rhs=rhs;d.eval();
  if(edge==0){held_lazy=d.lazy_result;held_canonical=d.canonical_result;for(unsigned i=0;i<5;i++)bad_held[i]=d.bad_result[i];}
  if(!active){canceled+=pending.size();pending.clear();held_old=0;retained+=held_lazy!=0;}
  if(d.lazy_result!=held_lazy||d.canonical_result!=held_canonical)throw std::runtime_error("L7_NEW_COMBINATIONAL_OR_RESET_PAYLOAD");
  if(active&&(d.old_lazy_result!=held_old||d.old_canonical_result!=held_old))throw std::runtime_error("L7_OLD_COMBINATIONAL_OUTPUT");
  if(!active&&d.out_valid)throw std::runtime_error("L7_ASYNC_VALID_KILL");
  if(!active)for(unsigned i=0;i<5;i++)if((d.bad_valid>>i)&1)detected|=1u<<i;
  if(active&&valid){
   if(lhs>=2*P||rhs>=P)throw std::runtime_error("L7_BAD_VECTOR");
   pending.push_back({edge+3,uint32_t((uint64_t(lhs)*rhs%P)*inverse%P)});
  }
  d.clk=1;d.eval();const bool due=!pending.empty()&&pending.front().due==edge;
  for(unsigned i=0;i<5;i++){
   const bool bvalid=(d.bad_valid>>i)&1;
   if(bvalid!=due || (due && d.bad_result[i]!=pending.front().expected) || (!due && d.bad_result[i]!=bad_held[i]))detected|=1u<<i;
   bad_held[i]=d.bad_result[i];
  }
  if(d.out_valid!=(due?15:0))throw std::runtime_error("L7_VALID_RESET_OR_LATENCY");
  if(due){
   const auto expected=pending.front().expected;
   if(d.lazy_result!=expected||d.canonical_result!=expected||d.old_lazy_result!=expected||d.old_canonical_result!=expected||d.lazy_result>=P)
    throw std::runtime_error("L7_ARITHMETIC edge="+std::to_string(edge));
   pending.pop_front();held_lazy=expected;held_canonical=expected;held_old=expected;checked++;
  }else{
   if(d.lazy_result!=held_lazy||d.canonical_result!=held_canonical||d.old_lazy_result!=held_old||d.old_canonical_result!=held_old)
    throw std::runtime_error("L7_INVALID_HOLD");
   holds++;
  }
  edge++;
 };
 tick(false,false,0,0);
 const std::vector<uint32_t> lhs_edges={0,1,P-1,P,P+1,(1u<<27)-1,1u<<27,2*P-1};
 const std::vector<uint32_t> rhs_edges={0,1,P-1,uint32_t((uint64_t(1)<<32)%P)};
 for(auto x:lhs_edges)for(auto y:rhs_edges)tick(true,true,x,y);
 std::mt19937 rng(0x28270001);
 for(unsigned i=0;i<20000;i++)tick(i%251!=250,i%7!=6,rng()%(2*P),rng()%P);
 for(unsigned occupancy=1;occupancy<=4;occupancy++){
  tick(false,false,0,0);
  for(unsigned j=0;j<occupancy;j++)tick(true,true,2*P-1-j,P-1-j);
  if(occupancy&1)tick(false,true,2*P-1,P-1);
  else tick(true,true,2*P-1,P-1,true);
  for(unsigned j=0;j<8;j++)tick(true,true,rng()%(2*P),rng()%P);
 }
 for(unsigned i=0;i<8;i++)tick(true,false,0,0);
 if(!pending.empty()||checked!=16925||canceled!=224||holds!=3166||edge!=20091||!retained||detected!=31)throw std::runtime_error("L7_MUTANT_COVERAGE");
 std::cout<<"PASS_L7_RESETFREE_MUTANTS P="<<P<<" checked="<<checked<<" canceled="<<canceled<<" holds="<<holds
  <<" detected="<<detected<<" edges="<<edge<<" outputs=4 latency=3 ii=1 dirty_reset_retention=true\n";
 d.final();return 0;
}catch(const std::exception&error){std::cerr<<error.what()<<"\n";return 1;}}
