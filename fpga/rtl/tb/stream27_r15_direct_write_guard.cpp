#include "Vstream27_r15_direct_write_guard.h"
#include "native_runtime_context_v1.h"
#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#ifndef R15_N
#define R15_N 32
#endif
namespace {
constexpr unsigned N=R15_N,T=N/16,B=1009,K=2*N+384;
constexpr uint64_t O0=0x123456789abcdeULL,O1=0xabcdef12345678ULL;
void need(bool x,const char* why){if(!x)throw std::runtime_error(why);}
struct C:VerilatedContext{C(int a,char** v){gfn16_runtime::configure(*this,a,v);}};
struct H{
 C c;Vstream27_r15_direct_write_guard d;unsigned writes=0,reads=0,stalls=0,peers=0;
 H(int a,char**v):c(a,v),d(&c){
  need(gfn16_runtime::matches(c,d),"R15_RUNTIME");unsigned nt=0;
  for(auto const& e:std::filesystem::directory_iterator("/proc/self/task")){(void)e;nt++;}
  need(nt==1,"R15_OS_THREADS");
  d.clk=0;d.rst_n=0;d.link_drained=1;d.core_idle=d.lease_safe=d.profile_ok=1;
  d.grant_enable=d.transport_empty=1;d.peer_port_busy=0;d.owner_enabled=3;
  d.live_owner[0]=uint32_t(O0);d.live_owner[1]=uint32_t((O0>>32)|(O1<<24));
  d.live_owner[2]=uint32_t(O1>>8);d.live_owner[3]=uint32_t(O1>>40);
  d.test_context=d.test_address=d.row_address=0;for(auto&i:d.row_data)i=0;
  clear();reset();
 }
 void clear(){d.begin_valid=d.word_valid=d.commit_valid=d.cancel=d.test_read=d.row_read_req=d.row_write_req=0;}
 void edge(){d.clk=0;d.eval();bool w=d.bank_write;d.clk=1;c.timeInc(1);d.eval();if(w)writes++;}
 void reset(){clear();d.rst_n=0;edge();need(!d.active&&!d.error&&!d.publish&&!d.host_write_ack&&!d.read_valid,"R15_RESET");
  d.rst_n=1;d.link_drained=d.core_idle=d.lease_safe=d.profile_ok=d.grant_enable=d.transport_empty=1;d.peer_port_busy=0;edge();}
 uint64_t owner(unsigned ctx){return ctx?O1:O0;}
 void begin(unsigned ctx){clear();d.begin_context=ctx;d.begin_owner=d.expected_owner=owner(ctx);d.session=11;d.lease=23;
  d.base=B;d.begin_valid=1;edge();d.begin_valid=0;need(d.active&&!d.error&&!d.publish,"R15_BEGIN");}
 uint32_t value(unsigned i){if(i<N)return i==0?0xffffffffu:(i*17+9)%B;
  int v=i<N+16?int(B-1):int(K);return uint32_t(i&1?-v:v);}
 void setword(unsigned ctx,unsigned i){d.word_context=ctx;d.word_owner=owner(ctx);d.word_session=11;d.word_lease=23;
  d.word_index=i;d.word_data=value(i);d.word_valid=1;}
 void init_peer(unsigned ctx){clear();d.row_write_req=1;d.row_write_context=ctx;d.row_owner=owner(ctx);
  for(unsigned r=0;r<T;r++){d.row_address=r;for(unsigned b=0;b<16;b++)d.row_data[b]=7000+b*T+r;edge();need(d.row_write_ack&&!d.rejected,"R15_INITIAL_RAM_CAPTURE");}
  clear();}
 void send(unsigned ctx,unsigned i,bool stress){clear();setword(ctx,i);
  if(stress && i<N && i%7==0){
   d.row_read_req=1;d.row_read_context=ctx;d.row_owner=owner(ctx);d.row_address=i%T;
   d.eval();need(!d.word_ready&&!d.bank_write,"R15_SAME_CONTEXT_PORT_PREEMPTS");auto count=d.applied_count;
   edge();need(d.applied_count==count&&!d.host_write_ack&&!d.error,"R15_STALL_NO_ACK");stalls++;d.row_read_req=0;
  }
  if(stress && i<N){d.row_write_req=1;d.row_write_context=1-ctx;d.row_owner=owner(1-ctx);d.row_address=i%T;
   for(unsigned b=0;b<16;b++)d.row_data[b]=7000+b*T+i%T;}
  d.eval();need(d.word_ready&&d.bank_write,"R15_WORD_ACCEPT");edge();
  need(!d.error&&d.applied_count==i+1&&!d.publish,"R15_ACCEPT_COUNT");
  if(i<N)need(d.host_write_ack,"R15_REAL_RAM_ACK");
  if(stress&&i<N){need(d.row_write_ack&&!d.rejected,"R15_PEER_CONCURRENT_CAPTURE");peers++;}
  clear();
 }
 void commit(unsigned ctx){clear();edge();edge();need(d.ack_count==N+32,"R15_ALL_ACKS");
  d.commit_valid=1;d.commit_context=ctx;d.commit_owner=owner(ctx);d.commit_session=11;d.commit_lease=23;edge();
  need(d.publish&&!d.active&&!d.error&&d.published_context==ctx&&d.published_owner==owner(ctx),"R15_PUBLISH_TUPLE");
  need(d.published_profile[0]==B&&(d.published_profile[1]&255)==(owner(ctx)&255),"R15_PROFILE_CAPTURE");clear();edge();need(!d.publish,"R15_PUBLISH_PULSE");}
 void read(unsigned ctx,unsigned a,uint32_t expected){clear();d.test_read=1;d.test_context=ctx;d.test_address=a;edge();
  need(d.read_valid&&d.read_context==ctx&&d.read_owner==owner(ctx),"R15_RAM_READ_EDGE_OWNER");
  auto sign=(expected>>31)?0xffffffffu:0u;
  need(d.read_data[0]==expected&&d.read_data[1]==sign&&d.read_data[2]==sign,"R15_RAM_READ_VALUE");reads++;clear();edge();need(!d.read_valid,"R15_READ_IDLE");}
 void normal(){init_peer(0);init_peer(1);for(unsigned ctx=0;ctx<2;ctx++){
   begin(ctx);for(unsigned i=0;i<N+32;i++)send(ctx,i,true);commit(ctx);
   for(unsigned i=0;i<N;i++){read(ctx,i,value(i));read(1-ctx,i,7000+i);}
   for(unsigned i=0;i<32;i++){d.test_context=ctx;d.test_address=i;d.eval();need(d.correction_read==value(N+i),"R15_CORRECTION_VALUE");}
  }
  need(writes==2*(N+32)&&reads==4*N&&peers==2*N,"R15_NORMAL_COUNTS");
 }
 void sticky(){need(d.error&&!d.active&&!d.publish,"R15_TYPED_FAULT");clear();
  for(unsigned j=0;j<4;j++){d.begin_valid=d.word_valid=d.commit_valid=1;edge();need(d.error&&!d.bank_write&&!d.publish,"R15_STICKY");}clear();}
 void faults(){unsigned cases=0;
  for(unsigned mode=0;mode<9;mode++){reset();begin(0);setword(0,0);
   if(mode==0)d.word_owner^=uint64_t(1)<<55;
   if(mode==1)d.word_session++;
   if(mode==2)d.word_lease++;
   if(mode==3)d.word_context=1;
   if(mode==4)d.word_index=1;
   if(mode==5)d.word_data=B;
   if(mode==6)d.word_index=N+32;
   if(mode==7)d.begin_valid=1;
   if(mode==8)d.expected_owner^=uint64_t(1)<<40;
   d.eval();need(!d.bank_write,"R15_INVALID_NO_WRITE");edge();sticky();cases++;
  }
  reset();begin(0);send(0,0,false);clear();d.commit_valid=1;d.commit_context=0;d.commit_owner=O0;d.commit_session=11;d.commit_lease=23;edge();sticky();cases++;
  reset();begin(0);send(0,0,false);clear();d.cancel=1;edge();need(!d.active&&!d.publish&&!d.error,"R15_CANCEL_PARTIAL");clear();
  setword(0,1);edge();sticky();cases++;
  reset();begin(0);send(0,0,false);d.link_drained=0;edge();need(!d.active&&!d.publish,"R15_DRAIN_REVOKES");reset();cases++;
  begin(0);send(0,0,false);reset();need(!d.active&&!d.publish&&!d.applied_count,"R15_RESET_PARTIAL");cases++;
  begin(0);d.core_idle=0;edge();sticky();cases++;
  // Fault recovery is a complete reload; cancellation never rolls back old RAM contents.
  reset();begin(0);for(unsigned i=0;i<N+32;i++)send(0,i,false);commit(0);
  for(unsigned i=0;i<N;i++)read(0,i,value(i));need(cases==14,"R15_FAULT_COUNTS");
 }
};
}
int main(int argc,char**argv){try{H h(argc,argv);if(argc>1&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(h.c,h.d);
 bool fault=argc>1&&std::string(argv[1])=="--fault";if(fault)h.faults();else h.normal();
 std::cout<<"R15_DIRECT_WRITE_"<<(fault?"FAULT":"NORMAL")<<"_PASS n="<<N;
 if(fault)std::cout<<" cases=14 recovery_reads="<<N;
 else std::cout<<" writes="<<h.writes<<" reads="<<h.reads<<" peer_captures="<<h.peers<<" port_stalls="<<h.stalls;
 std::cout<<" runtime_threads=1 core_clock_only=1\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
