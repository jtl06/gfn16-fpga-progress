// Own functional application/core/CDC target. No vendor HIP or behavioral core.
#include "s4_host_contexts_config_v1.h"
#include "native_runtime_context_v1.h"
#include "verilated.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
static_assert(AW==8&&N==256&&P==16,"Own AW8 application normal only");
static void need(bool b,const std::string&s){if(!b)throw std::runtime_error(s);}
static uint32_t lane32(uint64_t x,unsigned c){return uint32_t(x>>(32*c));}
static uint64_t lane64(const VlWide<4>&x,unsigned c){return uint64_t(x[2*c])|(uint64_t(x[2*c+1])<<32);}
static uint64_t expected_owner(unsigned c){return (uint64_t(COUNTS[c]-1)<<24)|(uint64_t(uint16_t(EPOCHS[c]+COUNTS[c]-1))<<8)|1u;}
struct Event{bool pcie,core,ctrl,cold,exp,ctrl_response,export_response;};
static uint64_t ticks=0,age=0;static bool tracking=false;
static std::array<unsigned,2> done_count{},done_edges{};
static bool waiting_b=false,capture_copy=false,canonical_peer=false;static unsigned previous_raw_b=0;
static unsigned ctrl_transactions=0,cold_words=0,read_words=0;
static void scoreboard(DUT&d){
 need(!d.probe_error,"R15_APPLICATION_REAL_CORE_OR_TRANSPORT_ERROR age="+std::to_string(age));
 if(!tracking)return;
 for(unsigned c=0;c<2;c++){
  unsigned started=age<FIRST[c]?0:std::min(COUNTS[c],1u+unsigned((age-FIRST[c])/INTERVAL));
  unsigned completed=age<FIRST[c]+CARRY_DONE+1?0:std::min(COUNTS[c],1u+unsigned((age-FIRST[c]-CARRY_DONE-1)/INTERVAL));
  need(lane32(d.probe_started,c)==started&&lane32(d.probe_completed,c)==completed,"R15_APPLICATION_OWN_CORE_CALENDAR");
  uint64_t digit=FIRST[c]+uint64_t(COUNTS[c]-1)*INTERVAL+FIRST_DIGIT;
  unsigned rows=age>digit?std::min(T,unsigned(age-digit)):0;
  need(lane32(d.probe_rows,c)==rows,"R15_APPLICATION_ACTUAL_LAST_ROWS");
  bool warm=age==FIRST[c]+uint64_t(COUNTS[c]-1)*INTERVAL+CARRY_DONE+1;
  need(bool(d.probe_warm&(1u<<c))==warm,"R15_APPLICATION_WARM_EDGE");
  if(d.probe_done&(1u<<c)){
   done_count[c]++;done_edges[c]=unsigned(age);
   need((d.probe_ready&(1u<<c))&&!(d.probe_busy&(1u<<c)),"R15_APPLICATION_ATOMIC_CORE_PUBLICATION");
   need(lane64(d.probe_canonical,c)==CANON_PASSES*N&&lane64(d.probe_copy,c)==N+4,"R15_APPLICATION_COPY_N_PLUS4");
  }
 }
 if(d.probe_waiting&2u)waiting_b=true;
 unsigned raw_b=lane32(d.probe_rows,1);
 if(raw_b>previous_raw_b&&lane64(d.probe_copy,0)>0&&(d.probe_busy&1u))capture_copy=true;
 previous_raw_b=raw_b;
 if(lane64(d.probe_canonical,0)>0&&lane32(d.probe_completed,1)<COUNTS[1]&&(d.probe_busy&2u))canonical_peer=true;
 need(age<100000,"R15_APPLICATION_BOUNDED_CORE_PROGRAM");
}
static Event tick(DUT&d){
 d.eval();uint64_t next=ticks+1;bool pr=next%4==2,cr=next%12==6;
 Event e{pr,cr,pr&&(d.ctrl_read||d.ctrl_write)&&!d.ctrl_waitrequest,
   pr&&d.cold_write&&!d.cold_waitrequest,pr&&d.export_read&&!d.export_waitrequest,false,false};
 bool start=cr&&d.probe_start==3;
 if(start){need(!tracking,"R15_APPLICATION_ONE_ACTUAL_START");tracking=true;age=0;}
 else if(cr&&tracking)age++;
 d.pcie_clk=(next/2)&1;d.core_clk=(next/6)&1;ticks=next;d.eval();
 e.ctrl_response=pr&&d.ctrl_readdatavalid;e.export_response=pr&&d.export_readdatavalid;
 if(cr&&d.probe_link_ready)scoreboard(d);
 return e;
}
static void idle(DUT&d,unsigned n){for(unsigned i=0;i<n;i++)tick(d);}
static void requests_clear(DUT&d){d.ctrl_read=d.ctrl_write=d.cold_write=d.export_read=0;}
static void wr(DUT&d,unsigned addr,uint32_t data){
 requests_clear(d);d.ctrl_address=addr;d.ctrl_writedata=data;d.ctrl_byteenable=15;d.ctrl_write=1;
 for(unsigned i=0;i<100000;i++)if(tick(d).ctrl){d.ctrl_write=0;ctrl_transactions++;return;}
 throw std::runtime_error("R15_APPLICATION_CTRL_WRITE_TIMEOUT");
}
static uint32_t rd(DUT&d,unsigned addr){
 requests_clear(d);d.ctrl_address=addr;d.ctrl_writedata=0;d.ctrl_byteenable=15;d.ctrl_read=1;bool accepted=false;
 for(unsigned i=0;i<100000;i++){
  Event e=tick(d);if(e.ctrl){need(!accepted,"R15_APPLICATION_ONE_CTRL_REQUEST");accepted=true;d.ctrl_read=0;ctrl_transactions++;}
  if(e.ctrl_response){need(accepted,"R15_APPLICATION_RESPONSE_AFTER_ACCEPT");return d.ctrl_readdata;}
 }
 throw std::runtime_error("R15_APPLICATION_CTRL_READ_TIMEOUT");
}
static void error_fence(DUT&d){need(rd(d,0x4c)==0,"R15_APPLICATION_FRESH_ERROR_FENCE");}
static uint32_t session=0;static std::array<uint32_t,2> leases{};
static void load(DUT&d,unsigned c){
 wr(d,0x10,c);uint32_t gen=rd(d,0x58),epoch=rd(d,0x54);
 uint64_t owner=(uint64_t(COUNTS[c]-1)<<24)|(uint64_t(uint16_t(epoch+COUNTS[c]-1))<<8)|gen;
 need(gen==1&&owner==expected_owner(c),"R15_APPLICATION_CORE_ISSUED_HEADER");
 wr(d,0x14,uint32_t(owner));wr(d,0x18,uint32_t(owner>>32));wr(d,0x1c,COUNTS[c]);wr(d,0x20,BASES[c]);
 wr(d,0x24,gen);wr(d,0x50,1);wr(d,0x60,0);wr(d,0x64,session);
 for(unsigned r=0x28;r<=0x3c;r+=4)wr(d,r,0);
 wr(d,0x40,1);leases[c]=rd(d,0x5c);error_fence(d);
 for(unsigned index=0;index<N+2*P;index++){
  uint32_t word=uint32_t(index<N?INITIAL[c][index]:(index<N+P?C0[c][index-N]:C1[c][index-N-P]));
  requests_clear(d);d.cold_address=index*32;d.cold_byteenable=0xffffffffu;d.cold_burstcount=1;
  d.cold_writedata[0]=0x52315000u|c;d.cold_writedata[1]=session;d.cold_writedata[2]=leases[c];
  d.cold_writedata[3]=uint32_t(owner);d.cold_writedata[4]=uint32_t(owner>>32);
  d.cold_writedata[5]=index;d.cold_writedata[6]=word;d.cold_writedata[7]=0;d.cold_write=1;
  bool accepted=false;for(unsigned wait=0;wait<100000;wait++)if(tick(d).cold){accepted=true;break;}
  need(accepted,"R15_APPLICATION_HELD_DATA32_TIMEOUT");d.cold_write=0;cold_words++;
 }
 need(rd(d,0x44)==N+2*P&&rd(d,0x48)==N+2*P,"R15_APPLICATION_REAL_ACCEPTED_APPLIED_COUNTS");
 wr(d,0x64,session);wr(d,0x68,leases[c]);wr(d,0x40,2);
 uint32_t status=rd(d,0x0c);error_fence(d);
 need((status&(1u<<(4+c)))&&!(status&(1u<<3)),"R15_APPLICATION_COMMIT_AUTHORITY");
}
static void read_word(DUT&d,unsigned c,unsigned index){
 requests_clear(d);d.export_address=(c<<22)|(index*32);d.export_burstcount=1;d.export_read=1;bool accepted=false;
 for(unsigned wait=0;wait<100000;wait++){
  Event e=tick(d);if(e.exp){need(!accepted,"R15_APPLICATION_ONE_EXPORT_REQUEST");accepted=true;d.export_read=0;}
  if(e.export_response){
   need(accepted,"R15_APPLICATION_EXPORT_RESPONSE_CREDIT");
   auto&v=d.export_readdata;uint64_t owner=uint64_t(v[2])|(uint64_t(v[3])<<32);
   need(v[0]==(0x52314100u|c)&&v[1]==session&&owner==expected_owner(c)&&v[4]==index,
        "R15_APPLICATION_A32_SESSION_FULL56_CONTEXT_INDEX");
   int32_t expected=EXPECTED[c][index];uint32_t sign=expected<0?0xffffffffu:0;
   need(v[5]==uint32_t(expected)&&v[6]==sign&&v[7]==sign,"R15_APPLICATION_ALL_SIGNED96_REFERENCE");
   read_words++;return;
  }
 }
 throw std::runtime_error("R15_APPLICATION_A32_TIMEOUT");
}
static void run(DUT&d){
 requests_clear(d);d.ctrl_address=d.ctrl_writedata=d.ctrl_byteenable=0;
 d.cold_address=d.cold_byteenable=d.cold_burstcount=0;for(auto&v:d.cold_writedata)v=0;
 d.export_address=d.export_burstcount=0;d.pcie_clk=d.core_clk=0;
 d.board_perst_n=d.hip_reset_n=d.pll_locked=0;idle(d,96);
 d.board_perst_n=d.hip_reset_n=d.pll_locked=1;
 need(rd(d,0)==0x52313541&&rd(d,4)==0x10000,"R15_APPLICATION_ID_ABI");
 session=rd(d,8);need(session!=0&&(rd(d,0x0c)&1u),"R15_APPLICATION_FRESH_LINK_SESSION");error_fence(d);
 load(d,0);load(d,1);need(cold_words==2*(N+2*P),"R15_APPLICATION_COMPLETE_COLD_PAIR");
 need(rd(d,8)==session,"R15_APPLICATION_SESSION_STABLE_BEFORE_START");
 uint32_t latest=rd(d,0x5c);need(latest==leases[1],"R15_APPLICATION_GLOBAL_LATEST_BEGIN_LEASE");
 wr(d,0x64,session);wr(d,0x68,latest);wr(d,0x6c,3);wr(d,0x40,4);
 for(unsigned i=0;i<2000000&&(d.probe_ready!=3||d.probe_busy);i++)tick(d);
 need(tracking&&d.probe_ready==3&&!d.probe_busy&&done_count[0]==1&&done_count[1]==1&&
      done_edges[0]<done_edges[1]&&waiting_b&&capture_copy==EXPECT_CAPTURE_COPY&&canonical_peer,
      "R15_APPLICATION_CORE_PUBLICATION_INTERLEAVE");
 uint32_t status=rd(d,0x0c);error_fence(d);need((status&0xc00u)==0xc00u&&(status&0x300u)==0,"R15_APPLICATION_FRESH_PUBLISHED_SNAPSHOT");
 for(unsigned c=0;c<2;c++)for(unsigned a=0;a<N;a++)read_word(d,c,a);
 for(unsigned a=0;a<N;a++)for(unsigned c=0;c<2;c++)read_word(d,c,a);
 need(read_words==4*N&&rd(d,8)==session,"R15_APPLICATION_FINAL_SESSION_WORD_LEDGER");error_fence(d);
 status=rd(d,0x0c);need((status&0xc00u)==0xc00u&&(status&0x300u)==0,"R15_APPLICATION_FINAL_COHERENT_PUBLICATION");
 std::cout<<"R15_APPLICATION_PASS aw=8 contexts=2 squares=17 signed96_words=1024 cold_records=576 interval=215 first=204/311 core_publication=1 live_core_cdc=1 mmio_data_a32=1 vendor_hip_simulated=0 host_gl=0\n";
}
int main(int argc,char**argv){try{VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
 need(argc==1&&gfn16_runtime::matches(context,d),"R15_APPLICATION_ARGUMENTS_THREADS");run(d);d.final();return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
