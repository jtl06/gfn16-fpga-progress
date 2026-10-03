#include "Vgenefer_stream27_r15_async_fifo_v1.h"
#include "native_runtime_context_v1.h"
#include <array>
#include <cstdint>
#include <deque>
#include <iostream>
#include <stdexcept>
#include <string>

using Word=std::array<uint32_t,8>;
static void need(bool ok,const char* text){if(!ok)throw std::runtime_error(text);}
static uint32_t random_word(uint32_t& state){state^=state<<13;state^=state>>17;state^=state<<5;return state;}
static Word payload(uint32_t serial){Word v{};for(unsigned i=0;i<8;i++)v[i]=(serial*0x9e3779b9u)^(0xa5a55a5au+i*0x1020304u);return v;}

int main(int argc,char** argv){
 try{
  VerilatedContext context;gfn16_runtime::configure(context,argc,argv);
  Vgenefer_stream27_r15_async_fifo_v1 dut(&context);
  if(argc==2 && std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,dut);
  need(argc==1 && gfn16_runtime::matches(context,dut),"R15_CDC_RUNTIME");
  std::deque<Word> expected;
  uint32_t rng=0x12345678u,serial=1;
  uint64_t pushes=0,pops=0,discarded=0,full_stalls=0,read_stalls=0;
  bool pending=false,previous_reset=false,holding=false;
  Word offered{},held{};
  dut.wr_clk=0;dut.rd_clk=0;dut.rst_n=0;dut.wr_enable=0;dut.rd_enable=0;
  dut.wr_valid=0;dut.rd_ready=0;dut.eval();
  // Incommensurate 6/10 time-unit periods; offsets exercise coincident and
  // single-domain edges. Six common resets discard only unowned queued data.
  for(unsigned tick=0;tick<24000;tick++){
   const bool reset=tick<17 || (tick>=2500 && tick<2523) ||
    (tick>=6101 && tick<6120) || (tick>=9998 && tick<10021) ||
    (tick>=14002 && tick<14025) || (tick>=18001 && tick<18030);
   const bool drain=tick>=22000;
   const uint32_t bits=random_word(rng);
   if(reset && !previous_reset){discarded+=expected.size();expected.clear();pending=false;holding=false;}
   previous_reset=reset;
   if(!reset && !drain && !pending && (bits&3)!=0){offered=payload(serial++);pending=true;}
   dut.rst_n=!reset;
   dut.wr_enable=!reset && (drain || tick%701<630);
   dut.rd_enable=!reset && (drain || tick%911<830);
   dut.wr_valid=pending && !reset;
   dut.rd_ready=!reset && (drain || ((bits>>8)&7)<4);
   for(unsigned i=0;i<8;i++)dut.wr_data[i]=offered[i];
   dut.eval();
   if(reset)need(!dut.wr_ready && !dut.rd_valid,"R15_CDC_RESET_AUTHORITY");
   if(holding && !reset && dut.rd_valid){for(unsigned i=0;i<8;i++)need(dut.rd_data[i]==held[i],"R15_CDC_STALLED_PAYLOAD");}
   const bool next_w=(tick%6)>=3,next_r=((tick+1)%10)>=5;
   const bool wr_edge=!dut.wr_clk && next_w,rd_edge=!dut.rd_clk && next_r;
   const bool push=wr_edge && dut.wr_ready && dut.wr_valid;
   const bool pop=rd_edge && dut.rd_valid && dut.rd_ready;
   if(wr_edge && pending && !dut.wr_ready && !reset)full_stalls++;
   if(rd_edge && dut.rd_valid && !dut.rd_ready)read_stalls++;
   if(pop){
    need(!expected.empty(),"R15_CDC_SPURIOUS_OR_STALE_WORD");
    for(unsigned i=0;i<8;i++)need(dut.rd_data[i]==expected.front()[i],"R15_CDC_ORDER_OR_DATA");
    expected.pop_front();pops++;
   }
   if(push){expected.push_back(offered);pushes++;pending=false;}
   holding=dut.rd_valid && !pop && !reset;
   for(unsigned i=0;i<8;i++)held[i]=dut.rd_data[i];
   dut.wr_clk=next_w;dut.rd_clk=next_r;dut.eval();
   context.timeInc(1);
  }
  need(expected.empty() && !pending && !dut.rd_valid,"R15_CDC_FINAL_DRAIN");
  need(pushes==pops+discarded && pops>500 && full_stalls>100 && read_stalls>100,"R15_CDC_COVERAGE");
  std::cout<<"R15_CDC_PASS ticks=24000 resets=6 width=256 depth=8 independent_clocks=1 runtime_threads=1\n";
  dut.final();return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
