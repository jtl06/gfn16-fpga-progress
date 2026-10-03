// SPDX-License-Identifier: Apache-2.0
// Native DIRECT65 simulation + host GMP prototype, not PCIe/CDC/VFIO/board.
#include "s4_host_contexts_config_v1.h"
#include "verilated.h"
#include "native_runtime_context_v1.h"
#include <gmpxx.h>
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
using Z=mpz_class;
static void need(bool ok,const char* tag){if(!ok)throw std::runtime_error(tag);}
static constexpr unsigned K=4;
static constexpr unsigned MASKS[2]={13,6};
static constexpr unsigned CHUNKS[2]={11,6};
static unsigned raw_words=0,read_words=0,started_jobs=0;
static std::array<uint64_t,2> owners{};
static std::array<unsigned,2> generations{};
static Z modulus(unsigned base){Z x;mpz_ui_pow_ui(x.get_mpz_t(),base,N);return x+1;}
static Z powmod(const Z& x,unsigned long exponent,const Z& m){Z y;mpz_powm_ui(y.get_mpz_t(),x.get_mpz_t(),exponent,m.get_mpz_t());return y;}
static Z advance(Z x,unsigned c,const Z& m){for(unsigned i=0;i<K;i++)x=(x*x*((MASKS[c]>>i)&1?2:1))%m;return x;}
static std::array<int32_t,N> words(Z value,unsigned base,const Z& m){
 std::array<int32_t,N> out{};need(value>=0&&value<m,"R15_WINDOW_HOST_RESIDUE");
 if(value==m-1){out[0]=-1;return out;}
 for(unsigned i=0;i<N;i++){out[i]=int32_t(mpz_fdiv_ui(value.get_mpz_t(),base));value/=base;}
 need(value==0,"R15_WINDOW_HOST_DIGIT_WIDTH");return out;
}
static void clear(DUT& d){
 d.host_context=d.load_we=d.read_en=0;d.host_addr=d.write_data=0;
 d.start_contexts=d.batch_mode=d.feed_mode=d.double_bit=0;d.base=d.warm_count=d.double_mask=0;
 d.command_context=d.command_valid=d.command_double=0;d.command_index=d.command_generation=0;
 for(unsigned i=0;i<2*P;i++)d.initial_c0[i]=d.initial_c1[i]=0;
 d.dc_begin=d.dc_cancel=d.dc_commit=d.dc_word_valid=0;
}
static void edge(DUT& d){d.clk=0;d.eval();d.clk=1;d.eval();}
static void reset(DUT& d,unsigned session){
 clear(d);d.dc_link_drained=1;d.dc_current_session=session;d.dc_transport_empty=1;
 d.dc_context=0;d.dc_owner=d.dc_session=d.dc_lease=d.dc_count=d.dc_mask=d.dc_mode=d.dc_index=d.dc_word=0;
 for(unsigned i=0;i<8;i++)d.dc_profile[i]=0;
 d.clk=0;d.rst_n=0;d.eval();edge(d);d.clk=0;d.rst_n=1;d.eval();edge(d);
 need(!d.dc_error&&!d.error&&!d.busy&&!d.done&&!d.canonical_ready&&!d.dc_loaded&&d.dc_job_generation==0,
      "R15_WINDOW_COMMON_CORE_RESET");
 // Trusted core-clock drain input only; no actual DMA/CDC/reset delivery claim.
}
static void load(DUT& d,unsigned c,const Z& value,const Z& m){
 clear(d);need(d.dc_idle==3&&!d.busy,"R15_WINDOW_BOTH_IDLE_LOAD");
 d.dc_context=c;d.dc_session=d.dc_current_session;d.dc_lease=d.dc_next_lease;
 generations[c]=uint8_t(d.dc_job_generation>>(8*c))+1;
 need(generations[c]<=255,"R15_WINDOW_GENERATION_REFUSAL");
 unsigned epoch=uint16_t(uint16_t(d.dc_next_epoch>>(16*c))+K-1);
 owners[c]=(uint64_t(K-1)<<24)|(uint64_t(epoch)<<8)|generations[c];d.dc_owner=owners[c];
 d.dc_count=K;d.dc_mask=MASKS[c];d.dc_mode=1|((MASKS[c]&1)<<2);
 for(unsigned i=0;i<8;i++)d.dc_profile[i]=0;
 d.dc_profile[0]=BASES[c];d.dc_profile[1]=generations[c];
 d.dc_begin=1;edge(d);d.dc_begin=0;
 need(d.dc_active&&!d.dc_error&&!d.error&&!(d.dc_loaded&(1u<<c)),"R15_WINDOW_BEGIN_ACK");
 auto payload=words(value,BASES[c],m);d.dc_transport_empty=0;
 for(unsigned i=0;i<N+2*P;i++){
  d.dc_word_valid=1;d.dc_index=i;d.dc_word=i<N?uint32_t(payload[i]):0;
  unsigned waits=0;
  for(;;){d.clk=0;d.eval();bool accepted=d.dc_word_ready;edge(d);
   need(!d.dc_error&&!d.error,"R15_WINDOW_DESTINATION_WRITE");
   if(accepted){need(d.dc_applied==i+1,"R15_WINDOW_REAL_APPLIED_ACK");raw_words++;break;}
   need(++waits<32,"R15_WINDOW_PORT_GRANT_BOUND");
  }
 }
 d.dc_word_valid=0;d.dc_transport_empty=1;edge(d);edge(d);
 need(d.dc_applied==N+2*P&&!d.dc_error&&!d.error,"R15_WINDOW_DRAIN_ACK");
 d.dc_commit=1;edge(d);d.dc_commit=0;
 for(unsigned i=0;i<4&&!(d.dc_loaded&(1u<<c));i++)edge(d);
 need(!d.dc_active&&!d.dc_error&&!d.error&&(d.dc_loaded&(1u<<c)),"R15_WINDOW_RAW_COMMIT");edge(d);
}
static std::array<Z,2> job(DUT& d,const std::array<Z,2>& start,const std::array<Z,2>& mod,
                         bool oracle_negative=false){
 for(unsigned c=0;c<2;c++)load(d,c,start[c],mod[c]);
 need(d.dc_loaded==3,"R15_WINDOW_TWO_COMPLETE_IMAGES");clear(d);
 d.start_contexts=d.batch_mode=3;d.double_bit=1; // MASKS[0] bit0=1, MASKS[1] bit0=0.
 d.base=uint64_t(BASES[0])|(uint64_t(BASES[1])<<32);
 d.warm_count=uint64_t(K)|(uint64_t(K)<<32);
 d.double_mask=uint64_t(MASKS[0])|(uint64_t(MASKS[1])<<32);edge(d);
 need(d.busy==3&&!d.error&&!d.dc_error&&d.accepted_generation==
      (generations[0]|(generations[1]<<8)),"R15_WINDOW_COHERENT_START_BUSY_GENERATION");
 started_jobs+=2;std::array<unsigned,2> done{};unsigned age=0;
 for(;age<16000;age++){
  clear(d);edge(d);need(!d.error&&!d.dc_error,"R15_WINDOW_RETAINED_CORE_ERROR");
  for(unsigned c=0;c<2;c++)if(d.done&(1u<<c)){
   done[c]++;need((d.canonical_ready&(1u<<c))&&!(d.busy&(1u<<c)),"R15_WINDOW_ATOMIC_DONE_FENCE");
  }
  if(d.canonical_ready==3&&!d.busy)break;
 }
 need(age<16000&&done[0]==1&&done[1]==1,"R15_WINDOW_FINAL_PUBLICATION_BOUND");
 std::array<Z,2> result{};
 for(unsigned c=0;c<2;c++){
  need(uint32_t(d.completed_squares>>(32*c))==K,"R15_WINDOW_REAL_COMPLETION_COUNT");
  Z expected=advance(start[c],c,mod[c]);auto expected_words=words(expected,BASES[c],mod[c]);
  std::array<int32_t,N> actual{};
  for(unsigned i=0;i<N;i++){
   clear(d);d.host_context=c;d.host_addr=i;d.read_en=1;edge(d);
   need(!d.error&&!d.dc_error&&!d.busy&&d.canonical_ready==3&&d.read_valid&&
        d.read_context==c&&uint64_t(d.read_owner)==owners[c],"R15_WINDOW_FULL56_FINAL_READ_FENCE");
   int32_t wanted=expected_words[i];if(oracle_negative&&c==0&&i==0)wanted++;
   uint32_t upper=wanted<0?0xffffffffu:0;
   need(d.read_data[0]==uint32_t(wanted)&&d.read_data[1]==upper&&d.read_data[2]==upper,
        "R15_WINDOW_SIGNED96_ORACLE_WITNESS");actual[i]=int32_t(d.read_data[0]);read_words++;
  }
  if(actual[0]==-1){for(unsigned i=1;i<N;i++)need(actual[i]==0,"R15_WINDOW_SPECIAL_IMAGE");result[c]=mod[c]-1;}
  else{for(unsigned i=N;i--;) {need(actual[i]>=0&&uint32_t(actual[i])<BASES[c],"R15_WINDOW_CANONICAL_RANGE");result[c]=result[c]*BASES[c]+actual[i];}}
  need(result[c]==expected,"R15_WINDOW_ACTUAL_CANONICAL_GMP");
 }
 clear(d);edge(d);need(!d.error&&!d.dc_error&&!d.read_valid&&!d.busy&&d.canonical_ready==3,
                      "R15_WINDOW_FINAL_COHERENT_FENCE");return result;
}
static bool gl(const Z& cp,const Z& end,const Z& product,unsigned sum,const Z& m){
 return (product*end)%m == (cp*powmod(product,1u<<K,m)*powmod(Z(2),sum,m))%m;
}
static void normal(DUT& d,std::array<Z,2>& cp,std::array<Z,2>& mod){
 auto current=cp;std::array<Z,2> product{1,1};
 for(unsigned j=0;j<2;j++){
  for(unsigned c=0;c<2;c++)product[c]=(product[c]*current[c])%mod[c];
  current=job(d,current,mod);
 }
 for(unsigned c=0;c<2;c++)need(gl(cp[c],current[c],product[c],2*CHUNKS[c],mod[c]),"R15_WINDOW_GMP_GL");
 cp=current;
 std::cout<<"R15_HOST_WINDOW_NORMAL_PASS n="<<N<<" p="<<P<<" jobs="<<started_jobs
  <<" squares=16 raw="<<raw_words<<" signed96_reads="<<read_words
  <<" gl_checks=2 ordinal=8/8 session=7 owner_bits=56 value0="<<cp[0].get_str(16)
  <<" value1="<<cp[1].get_str(16)<<" core_simulation=1 pcie=0 cdc=0 vfio=0 board=0 full_prp=0\n";
}
int main(int argc,char** argv){try{
 VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
 bool rollback=argc==2&&std::string(argv[1])=="--host-corrupt-rollback";
 bool negative=argc==2&&std::string(argv[1])=="--oracle-negative";
 need((argc==1||rollback||negative)&&gfn16_runtime::matches(context,d)&&AW==8&&N==256&&P==16,
      "R15_WINDOW_ARGUMENTS_GEOMETRY_THREADS");
 std::array<Z,2> mod{modulus(BASES[0]),modulus(BASES[1])},cp{1,7};reset(d,7);normal(d,cp,mod);
 if(negative){job(d,cp,mod,true);throw std::runtime_error("R15_WINDOW_ORACLE_NEGATIVE_NOT_REJECTED");}
 if(rollback){
  auto safe=cp,current=cp;std::array<Z,2> product{1,1};
  for(unsigned j=0;j<2;j++){for(unsigned c=0;c<2;c++)product[c]=(product[c]*current[c])%mod[c];current=job(d,current,mod);}
  current[0]=(current[0]+1)%mod[0]; // Local host receipt flip AFTER all actual words passed.
  need(!gl(safe[0],current[0],product[0],2*CHUNKS[0],mod[0]),"R15_WINDOW_HOST_CORRUPTION_NOT_DETECTED");
  need(cp==safe,"R15_WINDOW_TWO_SAFE_CHECKPOINTS");reset(d,8);auto recovered=job(d,safe,mod);
  for(unsigned c=0;c<2;c++)need(gl(safe[c],recovered[c],safe[c],CHUNKS[c],mod[c]),"R15_WINDOW_RELOAD_RECOVERY_GL");
  std::cout<<"R15_HOST_WINDOW_ROLLBACK_PASS checkpoints=2 restored_ordinal=8/8 peer_discard=8/8 common_core_reset=1 fullreload=1 recovery_squares=8 signed96_reads="
   <<read_words<<" session=8 value0="<<recovered[0].get_str(16)<<" value1="<<recovered[1].get_str(16)
   <<" actual_dma_drain=0 physical_reset_delivery=0 board=0\n";
 }
 return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
