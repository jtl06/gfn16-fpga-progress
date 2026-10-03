#include "Vgenefer_stream27_r15_dma_aperture_v1.h"
#include "native_runtime_context_v1.h"
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

static void need(bool b,const char*s){if(!b)throw std::runtime_error(s);}
struct Write{uint64_t address;unsigned count,be;std::array<uint32_t,8> data;};
struct Bench{
 VerilatedContext context;
 Vgenefer_stream27_r15_dma_aperture_v1 *p;
 std::vector<Write> writes;
 std::vector<std::array<uint32_t,8>> reads;
 unsigned requests=0,faults=0,ticks=0;
 Bench(int argc,char**argv){gfn16_runtime::configure(context,argc,argv);p=new Vgenefer_stream27_r15_dma_aperture_v1(&context);}
 ~Bench(){p->final();delete p;}
 auto& d(){return *p;}
 void pre(){p->clk=0;p->eval();}
 void step(){
  pre();
  if(p->down_wr_write&&!p->down_wr_waitrequest){Write w{p->down_wr_address,p->down_wr_burstcount,p->down_wr_byteenable,{}};
   for(unsigned j=0;j<8;j++)w.data[j]=p->down_wr_writedata[j];writes.push_back(w);}
  if(p->down_rd_read&&!p->down_rd_waitrequest)requests++;
  if(p->fault_valid&&p->fault_ready)faults++;
  if(p->rd_readdatavalid){std::array<uint32_t,8>a{};for(unsigned j=0;j<8;j++)a[j]=p->rd_readdata[j];reads.push_back(a);}
  p->clk=1;p->eval();context.timeInc(1);p->clk=0;p->eval();ticks++;
 }
 void reset(){
  p->wr_write=p->rd_read=0;p->wr_address=p->rd_address=0;p->wr_burstcount=p->rd_burstcount=1;
  p->wr_byteenable=0xffffffffu;p->fault_ready=1;p->down_wr_waitrequest=p->down_rd_waitrequest=0;
  p->down_rd_readdatavalid=0;for(unsigned j=0;j<8;j++){p->wr_writedata[j]=0;p->down_rd_readdata[j]=0;}
  p->reset=1;step();step();p->reset=0;step();writes.clear();reads.clear();requests=faults=0;
  need(!p->protocol_error,"R15_APERTURE_RESET");
 }
 void write(uint64_t address,unsigned count,unsigned seed,unsigned be=0xffffffffu){
  for(unsigned i=0;i<count;i++){
   p->wr_address=i?uint64_t(1)<<63:address;p->wr_burstcount=i?0:count;p->wr_write=1;p->wr_byteenable=be;
   for(unsigned j=0;j<8;j++)p->wr_writedata[j]=seed+8*i+j;
   bool accepted=false;
   for(unsigned t=0;t<100;t++){
    p->down_wr_waitrequest=((ticks%5)==1||(ticks%5)==2);pre();accepted=!p->wr_waitrequest;step();if(accepted)break;
   }
   need(accepted,"R15_APERTURE_WRITE_PROGRESS");
  }
  p->wr_write=0;p->down_wr_waitrequest=0;step();step();
 }
 void read(uint64_t address,unsigned count){
  p->rd_address=address;p->rd_burstcount=count;p->rd_read=1;bool accepted=false;
  for(unsigned t=0;t<30;t++){pre();accepted=!p->rd_waitrequest;step();if(accepted)break;}
  need(accepted,"R15_APERTURE_READ_PROGRESS");p->rd_read=0;
 }
 void response(unsigned count,unsigned seed,bool expect_zero=false){
  for(unsigned i=0;i<count;i++){
   p->down_rd_readdatavalid=1;for(unsigned j=0;j<8;j++)p->down_rd_readdata[j]=seed+8*i+j;step();
  }
  p->down_rd_readdatavalid=0;step();
  need(reads.size()>=count,"R15_APERTURE_RESPONSE_COUNT");
  for(unsigned i=0;i<count;i++)for(unsigned j=0;j<8;j++)
   need(reads[reads.size()-count+i][j]==(expect_zero?0:seed+8*i+j),"R15_APERTURE_RESPONSE_BYTES");
 }
 void terminal(){
  need(p->protocol_error&&faults==1,"R15_APERTURE_ONE_FAULT");
  p->wr_address=0;p->wr_burstcount=1;p->wr_write=1;p->rd_address=0;p->rd_burstcount=1;p->rd_read=1;
  for(unsigned t=0;t<5;t++){pre();need(p->wr_waitrequest&&p->rd_waitrequest,"R15_APERTURE_POSTFAULT_ADMISSION");step();}
  // Even a NEW invalid request cannot turn terminal drain into fresh admission.
  p->wr_address=p->rd_address=uint64_t(1)<<63;
  for(unsigned t=0;t<5;t++){pre();need(p->wr_waitrequest&&p->rd_waitrequest,"R15_APERTURE_POSTFAULT_INVALID_ADMISSION");step();}
  p->wr_write=p->rd_read=0;need(faults==1,"R15_APERTURE_DUPLICATE_FAULT");
 }
};

static void normal(Bench&b){
 b.reset();auto&d=b.d();
 const uint64_t bases[]={0,0x400000-32,0x2000,0x1000004,0x1001fe0,0x1002004,0x1003fe0};
 const unsigned counts[]={1,1,31,3,1,4,1};
 unsigned off=0;
 for(unsigned k=0;k<7;k++){
  unsigned be=k>=3?0xf:0xffffffffu;b.write(bases[k],counts[k],1000+100*k,be);
  need(b.writes.size()==off+counts[k],"R15_APERTURE_EXACT_DOWNWRITE_COUNT");
  for(unsigned i=0;i<counts[k];i++){
   const auto&w=b.writes[off+i];need(w.address==bases[k]&&w.count==counts[k]&&w.be==be,"R15_APERTURE_FIRSTBEAT_AUTHORITY");
   for(unsigned j=0;j<8;j++)need(w.data[j]==1000+100*k+8*i+j,"R15_APERTURE_WRITE_BYTES");
  }off+=counts[k];
 }
 d.down_rd_waitrequest=1;b.read(0x400000,3);b.pre();
 need(d.down_rd_read&&d.down_rd_address==0x400000&&d.down_rd_burstcount==3,"R15_APERTURE_HELD_READ");
 for(unsigned t=0;t<4;t++)b.step();d.down_rd_waitrequest=0;b.step();b.response(3,3000);
 b.read(0x800000-32,1);d.down_rd_readdatavalid=1;for(unsigned j=0;j<8;j++)d.down_rd_readdata[j]=4000+j;
 b.step();d.down_rd_readdatavalid=0;b.step();
 need(b.requests==2&&b.reads.size()==4&&b.faults==0&&!d.protocol_error,"R15_APERTURE_NORMAL_COUNTS");
 for(unsigned j=0;j<8;j++)need(b.reads.back()[j]==4000+j,"R15_APERTURE_ZERO_LATENCY_RESPONSE");
 // Link qualification gates new work while no fault is generated.
 d.fault_ready=0;d.wr_write=1;d.wr_address=0;d.wr_burstcount=1;b.pre();
 need(d.wr_waitrequest&&!d.fault_valid,"R15_APERTURE_LINK_QUALIFICATION");
 for(unsigned t=0;t<3;t++)b.step();d.fault_ready=1;b.pre();need(!d.wr_waitrequest,"R15_APERTURE_LINK_RESUME");b.step();d.wr_write=0;b.step();
 need(!d.protocol_error,"R15_APERTURE_LINK_NO_FAULT");
 std::cout<<"R15_APERTURE_NORMAL_PASS writes=43 reads=4 held=1 firstbeat=1 symbols64=1 dts_partial=1 core_vendor=0\n";
}

static void faults(Bench&b){
 auto&d=b.d();unsigned cases=0;
 const uint64_t wb[]={uint64_t(1)<<25,uint64_t(1)<<32,uint64_t(1)<<63,0x400000-32,0x1002000-32,0x1004000-32,UINT64_MAX-16};
 for(uint64_t base:wb){b.reset();b.write(base,2,77);need(b.writes.empty(),"R15_APERTURE_INVALID_WRITE_FORWARDED");b.terminal();cases++;}
 b.reset();d.wr_write=1;d.wr_burstcount=0;d.wr_address=0;b.step();d.wr_write=0;b.step();b.terminal();cases++;
 const uint64_t rb[]={uint64_t(1)<<25,uint64_t(1)<<32,uint64_t(1)<<63,0x800000-32,0x1000000,UINT64_MAX-16};
 for(uint64_t base:rb){b.reset();b.read(base,2);for(unsigned t=0;t<5;t++)b.step();
  need(b.requests==0&&b.reads.size()==2,"R15_APERTURE_INVALID_READ_DRAIN_COUNT");
  for(const auto&r:b.reads)for(auto x:r)need(x==0,"R15_APERTURE_INVALID_READ_DATA");b.terminal();cases++;}
 // Fault handshake delayed: first invalid request remains stable, then drains
 // exactly once after link readiness. No combinational ready->valid loop.
 b.reset();d.fault_ready=0;d.rd_read=1;d.rd_address=uint64_t(1)<<63;d.rd_burstcount=2;b.pre();
 need(d.fault_valid&&d.rd_waitrequest,"R15_APERTURE_FAULT_VALID_INDEPENDENT_READY");b.step();b.step();
 d.fault_ready=1;b.pre();need(d.fault_valid&&!d.rd_waitrequest,"R15_APERTURE_PENDING_ORIGIN");b.step();d.rd_read=0;
 for(unsigned t=0;t<5;t++)b.step();need(b.reads.size()==2&&b.requests==0,"R15_APERTURE_PENDING_ZERO_DRAIN");b.terminal();cases++;
 // Already offered write cannot be withdrawn on fault. No second beat/new
 // request forwards; it drains locally while the pre-fault offer is held.
 b.reset();d.down_wr_waitrequest=1;d.wr_write=1;d.wr_address=0x2000;d.wr_burstcount=2;d.wr_writedata[0]=55;b.step();
 d.wr_address=0;d.wr_burstcount=0;d.wr_writedata[0]=56;d.rd_read=1;d.rd_address=uint64_t(1)<<63;d.rd_burstcount=1;b.pre();
 need(d.down_wr_write&&d.down_wr_writedata[0]==55,"R15_APERTURE_HELD_TAIL_WITHDRAWN");b.step();d.wr_write=d.rd_read=0;
 for(unsigned t=0;t<3;t++){b.pre();need(d.down_wr_write&&d.down_wr_address==0x2000&&d.down_wr_writedata[0]==55,"R15_APERTURE_HELD_TAIL_CHANGED");b.step();}
 d.down_wr_waitrequest=0;b.step();b.step();need(b.writes.size()==1,"R15_APERTURE_TAIL_COUNT");b.terminal();cases++;
 // Existing response credits must drain, but bytes lose authority immediately
 // at fault origin (including a response staged on the previous clock).
 b.reset();b.read(0,3);b.step();d.down_rd_readdatavalid=1;for(unsigned j=0;j<8;j++)d.down_rd_readdata[j]=900+j;b.step();
 d.down_rd_readdatavalid=0;d.wr_write=1;d.wr_address=uint64_t(1)<<63;d.wr_burstcount=1;b.pre();
 need(d.rd_readdatavalid,"R15_APERTURE_STAGED_RESPONSE_MISSING");
 for(unsigned j=0;j<8;j++)need(d.rd_readdata[j]==0,"R15_APERTURE_FAULT_ORIGIN_DATA_LEAK");
 b.step();d.wr_write=0;b.response(2,1000,true);need(b.requests==1&&b.reads.size()==3,"R15_APERTURE_CREDIT_DRAIN");b.terminal();cases++;
 // Pre-fault RD offered but not downstream accepted cannot be withdrawn. If
 // downstream remains stalled after ABORT, the host tail requires reset; do
 // not invent a completion or credit. Actual accepted credits tested above.
 b.reset();d.down_rd_waitrequest=1;b.read(0,2);d.wr_write=1;d.wr_address=uint64_t(1)<<63;d.wr_burstcount=1;b.step();d.wr_write=0;
 for(unsigned t=0;t<8;t++){b.pre();need(d.down_rd_read&&d.down_rd_address==0&&d.down_rd_burstcount==2,"R15_APERTURE_READ_OFFER_WITHDRAWN");
  need(!d.rd_readdatavalid,"R15_APERTURE_UNACCEPTED_READ_FAKE_COMPLETION");b.step();}
 need(b.requests==0&&b.reads.empty()&&b.faults==1,"R15_APERTURE_UNRESOLVED_TAIL_SCOPE");cases++;
 // Illegal upstream payload mutation under wait is an origin, not a new beat.
 b.reset();d.down_wr_waitrequest=1;d.wr_write=1;d.wr_address=0;d.wr_burstcount=2;b.step();d.wr_writedata[0]=1;b.step();
 d.wr_writedata[0]=2;b.pre();need(d.fault_valid,"R15_APERTURE_HELD_MUTATION");b.step();d.wr_write=0;d.down_wr_waitrequest=0;b.step();b.step();b.terminal();cases++;
 // Reset, not polling or a new valid request, restores the fence.
 b.reset();b.write(0x1002004,1,123,0xf);need(b.writes.size()==1&&!d.protocol_error,"R15_APERTURE_RESET_RECOVERY");cases++;
 need(cases==20,"R15_APERTURE_FAULT_CORPUS_COUNT");
 std::cout<<"R15_APERTURE_FAULT_PASS cases=20 high_alias=1 dts_split=1 one_fault=1 zero_invalid=1 held_tail=1 unresolved_tail_reset=1 reset=1 core_vendor=0\n";
}

int main(int argc,char**argv){try{
 Bench b(argc,argv);
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(b.context,b.d());
 need(gfn16_runtime::matches(b.context,b.d()),"R15_APERTURE_RUNTIME");
 if(argc==1)normal(b);else if(argc==2&&std::string(argv[1])=="--faults")faults(b);else throw std::runtime_error("R15_APERTURE_ARGS");
 return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
