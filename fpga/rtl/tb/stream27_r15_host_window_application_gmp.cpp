// SPDX-License-Identifier: Apache-2.0
// Actual application/core/CDC simulation + limited host-GMP windows.
// No vendor HIP, physical reset delivery, VFIO, board, or full-PRP claim.
#include "s4_host_contexts_config_v1.h"
#include "native_runtime_context_v1.h"
#include "verilated.h"
#include <gmpxx.h>
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
using Z=mpz_class;
static void need(bool ok,const char* tag){if(!ok)throw std::runtime_error(tag);}
static constexpr unsigned K=4,MASKS[2]={13,6},CHUNKS[2]={11,6};
static uint64_t ticks=0;
static uint32_t session=0;
static unsigned cold_words=0,read_words=0,jobs=0;
static std::array<uint32_t,2> leases{},generations{};
static std::array<uint64_t,2> owners{};
static Z modulus(unsigned base){Z m;mpz_ui_pow_ui(m.get_mpz_t(),base,N);return m+1;}
static Z power(const Z& x,unsigned long exponent,const Z& m){Z y;mpz_powm_ui(y.get_mpz_t(),x.get_mpz_t(),exponent,m.get_mpz_t());return y;}
static Z advance(Z x,unsigned c,const Z& m){for(unsigned i=0;i<K;i++)x=(x*x*((MASKS[c]>>i)&1?2:1))%m;return x;}
static std::array<int32_t,N> digits(Z x,unsigned base,const Z& m){
 std::array<int32_t,N> v{};need(x>=0&&x<m,"R15_APP_WINDOW_HOST_RANGE");
 if(x==m-1){v[0]=-1;return v;}
 for(unsigned i=0;i<N;i++){v[i]=int32_t(mpz_fdiv_ui(x.get_mpz_t(),base));x/=base;}
 need(x==0,"R15_APP_WINDOW_HOST_WIDTH");return v;
}
struct Event{bool ctrl,cold,exp,ctrl_response,export_response;};
static Event tick(DUT& d){
 d.eval();uint64_t next=ticks+1;bool pr=next%4==2;
 Event e{pr&&(d.ctrl_read||d.ctrl_write)&&!d.ctrl_waitrequest,
   pr&&d.cold_write&&!d.cold_waitrequest,pr&&d.export_read&&!d.export_waitrequest,false,false};
 d.pcie_clk=(next/2)&1;d.core_clk=(next/6)&1;ticks=next;d.eval();
 e.ctrl_response=pr&&d.ctrl_readdatavalid;e.export_response=pr&&d.export_readdatavalid;
 need(!d.probe_error,"R15_APP_WINDOW_CORE_TRANSPORT_ERROR");return e;
}
static void idle(DUT&d,unsigned n){for(unsigned i=0;i<n;i++)tick(d);}
static void clear(DUT&d){d.ctrl_read=d.ctrl_write=d.cold_write=d.export_read=0;}
static void wr(DUT&d,unsigned address,uint32_t word){
 clear(d);d.ctrl_address=address;d.ctrl_writedata=word;d.ctrl_byteenable=15;d.ctrl_write=1;
 for(unsigned i=0;i<100000;i++)if(tick(d).ctrl){d.ctrl_write=0;return;}
 throw std::runtime_error("R15_APP_WINDOW_MMIO_WRITE_TIMEOUT");
}
static uint32_t rd(DUT&d,unsigned address){
 clear(d);d.ctrl_address=address;d.ctrl_byteenable=15;d.ctrl_read=1;bool accepted=false;
 for(unsigned i=0;i<100000;i++){
  auto e=tick(d);if(e.ctrl){need(!accepted,"R15_APP_WINDOW_ONE_MMIO_READ");accepted=true;d.ctrl_read=0;}
  if(e.ctrl_response){need(accepted,"R15_APP_WINDOW_ACK_AFTER_REQUEST");return d.ctrl_readdata;}
 }
 throw std::runtime_error("R15_APP_WINDOW_MMIO_READ_TIMEOUT");
}
static void fence(DUT&d){need(rd(d,0x4c)==0&&rd(d,8)==session,"R15_APP_WINDOW_COHERENT_ERROR_SESSION");}
static void reset(DUT&d,bool initial=false){
 uint32_t old=session;clear(d);d.external_fault_valid=0;
 d.board_perst_n=d.hip_reset_n=d.pll_locked=0;idle(d,96);
 d.board_perst_n=d.hip_reset_n=d.pll_locked=1;
 need(rd(d,0)==0x52313541&&rd(d,4)==0x10000,"R15_APP_WINDOW_ID_ABI");
 session=rd(d,8);need(session!=0&&(initial||session!=old),"R15_APP_WINDOW_NEW_COMMON_SESSION");
 uint32_t status=rd(d,0x0c);fence(d);
 need((status&1u)&&(status&0xc0u)==0xc0u&&(status&0xf30u)==0,"R15_APP_WINDOW_COMMON_RESET_IDLE");
 // Real simulated reset/CDC release only, not a host hardware-reset API.
}
static void load(DUT&d,unsigned c,const Z& x,const Z&m){
 clear(d);uint32_t status=rd(d,0x0c);fence(d);
 need((status&0xc0u)==0xc0u&&!(status&0x300u),"R15_APP_WINDOW_BOTH_IDLE_BEFORE_BEGIN");
 wr(d,0x10,c);generations[c]=rd(d,0x58);uint32_t epoch=rd(d,0x54);
 need(generations[c]>0&&generations[c]<256&&epoch<65536,"R15_APP_WINDOW_FRESH_GENERATION_EPOCH");
 owners[c]=(uint64_t(K-1)<<24)|(uint64_t(uint16_t(epoch+K-1))<<8)|generations[c];
 wr(d,0x14,uint32_t(owners[c]));wr(d,0x18,uint32_t(owners[c]>>32));wr(d,0x1c,K);
 wr(d,0x20,BASES[c]);wr(d,0x24,generations[c]);wr(d,0x50,1|((MASKS[c]&1)<<2));
 wr(d,0x60,MASKS[c]);wr(d,0x64,session);for(unsigned a=0x28;a<=0x3c;a+=4)wr(d,a,0);
 wr(d,0x40,1);leases[c]=rd(d,0x5c);fence(d);
 need(leases[c]!=0,"R15_APP_WINDOW_BEGIN_LEASE");auto v=digits(x,BASES[c],m);
 for(unsigned i=0;i<N+2*P;i++){
  clear(d);d.cold_address=i*32;d.cold_byteenable=0xffffffffu;d.cold_burstcount=1;
  d.cold_writedata[0]=0x52315000u|c;d.cold_writedata[1]=session;d.cold_writedata[2]=leases[c];
  d.cold_writedata[3]=uint32_t(owners[c]);d.cold_writedata[4]=uint32_t(owners[c]>>32);
  d.cold_writedata[5]=i;d.cold_writedata[6]=i<N?uint32_t(v[i]):0;d.cold_writedata[7]=0;d.cold_write=1;
  bool accepted=false;for(unsigned wait=0;wait<100000;wait++)if(tick(d).cold){accepted=true;break;}
  need(accepted,"R15_APP_WINDOW_STABLE_DATA32_TIMEOUT");d.cold_write=0;cold_words++;
 }
 need(rd(d,0x44)==N+2*P&&rd(d,0x48)==N+2*P,"R15_APP_WINDOW_ACCEPTED_APPLIED_DRAIN");
 wr(d,0x64,session);wr(d,0x68,leases[c]);wr(d,0x40,2);status=rd(d,0x0c);fence(d);
 need((status&(1u<<(4+c)))&&!(status&(1u<<3)),"R15_APP_WINDOW_RAW_COMMIT_NO_PROFILE_ACK");
}
static int32_t read_word(DUT&d,unsigned c,unsigned index,int32_t wanted){
 clear(d);d.export_address=(uint64_t(c)<<22)|uint64_t(index*32);d.export_burstcount=1;d.export_read=1;
 bool accepted=false;
 for(unsigned wait=0;wait<100000;wait++){
  auto e=tick(d);if(e.exp){need(!accepted,"R15_APP_WINDOW_ONE_A32_REQUEST");accepted=true;d.export_read=0;}
  if(e.export_response){
   need(accepted,"R15_APP_WINDOW_RESERVED_RESPONSE_CREDIT");auto& v=d.export_readdata;
   uint64_t owner=uint64_t(v[2])|(uint64_t(v[3])<<32);uint32_t sign=wanted<0?0xffffffffu:0;
   need(v[0]==(0x52314100u|c)&&v[1]==session&&owner==owners[c]&&v[4]==index,
        "R15_APP_WINDOW_A32_SESSION_FULL56_ROW");
   need(v[5]==uint32_t(wanted)&&v[6]==sign&&v[7]==sign,"R15_APP_WINDOW_SIGNED96_ORACLE_WITNESS");
   read_words++;return int32_t(v[5]);
  }
 }
 throw std::runtime_error("R15_APP_WINDOW_A32_TIMEOUT");
}
static std::array<Z,2> job(DUT&d,const std::array<Z,2>& start,const std::array<Z,2>&mod,bool wrong=false){
 for(unsigned c=0;c<2;c++)load(d,c,start[c],mod[c]);uint32_t status=rd(d,0x0c);fence(d);
 need((status&0xf0u)==0xf0u,"R15_APP_WINDOW_BOTH_IDLE_SELECTED_LOADED");
 uint32_t latest=rd(d,0x5c);need(latest==leases[1],"R15_APP_WINDOW_LATEST_GLOBAL_BEGIN_LEASE");
 wr(d,0x64,session);wr(d,0x68,latest);wr(d,0x6c,3);wr(d,0x40,4);status=rd(d,0x0c);fence(d);
 need((status&0x300u)==0x300u,"R15_APP_WINDOW_START_ADMITTED_BUSY");
 for(unsigned c=0;c<2;c++){wr(d,0x10,c);need(rd(d,0x58)==generations[c]+1,"R15_APP_WINDOW_START_GENERATION_SNAPSHOT");}
 jobs+=2;unsigned age=0;for(;age<2000000&&(d.probe_ready!=3||d.probe_busy);age++)tick(d);
 need(age<2000000,"R15_APP_WINDOW_PUBLICATION_TIMEOUT");status=rd(d,0x0c);fence(d);
 need((status&0xc00u)==0xc00u&&!(status&0x300u),"R15_APP_WINDOW_OWNED_FINAL_FENCE");
 std::array<Z,2> result{};
 for(unsigned c=0;c<2;c++){
  Z expected=advance(start[c],c,mod[c]);auto v=digits(expected,BASES[c],mod[c]);std::array<int32_t,N> got{};
  for(unsigned i=0;i<N;i++){int32_t wanted=v[i];if(wrong&&c==0&&i==0)wanted++;got[i]=read_word(d,c,i,wanted);}
  if(got[0]==-1){for(unsigned i=1;i<N;i++)need(got[i]==0,"R15_APP_WINDOW_SPECIAL_A");result[c]=mod[c]-1;}
  else for(unsigned i=N;i--;){need(got[i]>=0&&uint32_t(got[i])<BASES[c],"R15_APP_WINDOW_CANONICAL_RANGE");result[c]=result[c]*BASES[c]+got[i];}
  need(result[c]==expected,"R15_APP_WINDOW_ACTUAL_CANONICAL_GMP");
 }
 fence(d);status=rd(d,0x0c);need((status&0xc00u)==0xc00u&&!(status&0x300u),"R15_APP_WINDOW_FINAL_STATUS");return result;
}
static bool gl(const Z&cp,const Z&end,const Z&product,unsigned sum,const Z&m){
 return(product*end)%m==(cp*power(product,1u<<K,m)*power(Z(2),sum,m))%m;
}
static void normal(DUT&d,std::array<Z,2>&cp,const std::array<Z,2>&mod){
 auto x=cp;std::array<Z,2> product{1,1};for(unsigned j=0;j<2;j++){
  for(unsigned c=0;c<2;c++)product[c]=(product[c]*x[c])%mod[c];x=job(d,x,mod);
 }
 for(unsigned c=0;c<2;c++)need(gl(cp[c],x[c],product[c],2*CHUNKS[c],mod[c]),"R15_APP_WINDOW_GL");cp=x;
 std::cout<<"R15_APP_WINDOW_NORMAL_PASS n="<<N<<" p="<<P<<" jobs="<<jobs<<" squares=16 raw="<<cold_words
  <<" signed96_reads="<<read_words<<" gl_checks=2 ordinal=8/8 generations=2/2 owner_bits=56 value0="<<cp[0].get_str(16)
  <<" value1="<<cp[1].get_str(16)<<" actual_application_core_cdc=1 vendor_hip=0 vfio=0 board=0 full_prp=0\n";
}
int main(int argc,char**argv){try{
 VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
 bool rollback=argc==2&&std::string(argv[1])=="--host-corrupt-rollback",wrong=argc==2&&std::string(argv[1])=="--oracle-negative";
 need((argc==1||rollback||wrong)&&gfn16_runtime::matches(context,d)&&AW==8&&N==256&&P==16,"R15_APP_WINDOW_ARGUMENTS");
 clear(d);d.ctrl_address=d.ctrl_writedata=d.ctrl_byteenable=0;d.cold_address=d.cold_byteenable=d.cold_burstcount=0;
 for(unsigned i=0;i<8;i++)d.cold_writedata[i]=0;d.export_address=d.export_burstcount=0;d.pcie_clk=d.core_clk=0;
 std::array<Z,2> mod{modulus(BASES[0]),modulus(BASES[1])},cp{1,7};reset(d,true);normal(d,cp,mod);
 if(wrong){job(d,cp,mod,true);throw std::runtime_error("R15_APP_WINDOW_ORACLE_NOT_REJECTED");}
 if(rollback){auto safe=cp,x=cp;std::array<Z,2> product{1,1};for(unsigned j=0;j<2;j++){
   for(unsigned c=0;c<2;c++)product[c]=(product[c]*x[c])%mod[c];x=job(d,x,mod);
  }x[0]=(x[0]+1)%mod[0];need(!gl(safe[0],x[0],product[0],2*CHUNKS[0],mod[0]),"R15_APP_WINDOW_CORRUPTION_DETECTION");
  need(cp==safe,"R15_APP_WINDOW_TWO_SAFE_CHECKPOINTS");reset(d);auto recovered=job(d,safe,mod);
  for(unsigned c=0;c<2;c++)need(gl(safe[c],recovered[c],safe[c],CHUNKS[c],mod[c]),"R15_APP_WINDOW_RELOAD_GL");
  std::cout<<"R15_APP_WINDOW_ROLLBACK_PASS checkpoints=2 restored_ordinal=8/8 peer_discard=8/8 common_simulated_reset=1 fullreload=1 signed96_reads="
   <<read_words<<" value0="<<recovered[0].get_str(16)<<" value1="<<recovered[1].get_str(16)<<" hardware_reset_delivery=0 board=0\n";
 }d.final();return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
