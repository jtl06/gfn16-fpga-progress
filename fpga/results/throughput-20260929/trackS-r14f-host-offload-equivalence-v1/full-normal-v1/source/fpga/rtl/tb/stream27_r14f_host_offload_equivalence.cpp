// PRIVATE AUTHOR fixture. Actual FIELD100 OFF/actual B ON packet bodies, not footers.
#define main r14f_original_unused_main
#include "stream27_r14f_twin_driver.cpp"
#undef main
#include "stream27_host_offload_host_v2.h"
#include <iomanip>
#include <sstream>
#include <vector>

static constexpr unsigned COUNTS[2]={COUNT,COUNT},FIRST[2]={204,204+INTERVAL/2};
static std::array<Image,2> INITIAL,EXPECTED;
static constexpr int32_t C0[2][16]={},C1[2][16]={};
static unsigned launched(unsigned age,unsigned c){return age<FIRST[c]?0:std::min(COUNT,1u+(age-FIRST[c])/INTERVAL);}
static unsigned completed(unsigned age,unsigned c){return age<FIRST[c]+CARRY_DONE+1?0:std::min(COUNT,1u+(age-FIRST[c]-CARRY_DONE-1)/INTERVAL);}

struct Packet {
 std::vector<uint8_t> input,cold,profile,raw,canonical,reference;
 unsigned rows=0,boundaries=0,reads=0;uint64_t owner=0;
};
static std::array<Packet,2> twin_packet,b_packet;
static bool collecting_twin=false,collecting_b=false;
static void put(std::vector<uint8_t>& out,uint32_t word){
 size_t p=out.size();out.resize(p+4);gfn16_b_store32(out.data()+p,word);
}
static void prepare_packets(){
 for(unsigned c=0;c<2;c++){
  twin_packet[c]=Packet{};b_packet[c]=Packet{};
  auto& q=b_packet[c];q.profile.resize(32);q.cold.resize(4*(3*N+96));
  need(!gfn16_b_profile_make(N,BASES[c],1,q.profile.data(),q.profile.size()),"R14F_B_PROFILE_C");
  for(unsigned a=0;a<N;a++)put(q.input,uint32_t(INITIAL[c][a]));
  for(unsigned a=0;a<P;a++)put(q.input,uint32_t(C0[c][a]));
  for(unsigned a=0;a<P;a++)put(q.input,uint32_t(C1[c][a]));
  uint64_t initial_owner=(uint64_t(EPOCHS[c])<<8)|1u;
  need(!gfn16_b_cold_write(N,q.profile.data(),32,c,c,initial_owner,initial_owner,
       q.input.data(),4*N,q.input.data()+4*N,128,q.cold.data(),q.cold.size()),"R14F_B_COLD_C");
  for(unsigned a=0;a<N;a++)put(q.reference,uint32_t(EXPECTED[c][a]));
 }
}
static void eq_pre(DUT& d){
 if(!d.rst_n)return;
 if(collecting_twin&&d.eq_twin_raw_valid){
  unsigned c=d.eq_twin_context;auto& q=twin_packet[c];
  need(c<2&&d.eq_twin_capture&&d.eq_twin_owner==owner(c)&&d.eq_twin_live==owner(c)&&
       q.rows<T&&d.eq_twin_row==q.rows&&q.boundaries==0,"R14F_B_TWIN_RAW_OWNER_ROWS");
  for(unsigned l=0;l<P;l++)put(q.raw,d.eq_twin_data[l]);q.rows++;q.owner=d.eq_twin_owner;
 }
 if(collecting_twin&&d.eq_twin_boundary){
  unsigned c=d.eq_twin_boundary_context;auto& q=twin_packet[c];
  need(q.rows==T&&q.boundaries==0&&d.eq_twin_boundary_owner==owner(c)&&
       d.eq_twin_boundary_live==owner(c),"R14F_B_TWIN_BOUNDARY_OWNER");
  for(unsigned l=0;l<P;l++)put(q.raw,d.eq_twin_c0[l]);
  for(unsigned l=0;l<P;l++)put(q.raw,d.eq_twin_c1[l]);q.boundaries++;
 }
 if(collecting_b&&d.off_raw_valid){
  unsigned c=d.off_raw_context;auto& q=b_packet[c];
  need(c<2&&d.off_raw_ready&&d.off_raw_owner==owner(c)&&q.rows<T&&
       d.off_raw_row==q.rows&&q.boundaries==0,"R14F_B_ON_RAW_OWNER_ROWS");
  for(unsigned l=0;l<P;l++)put(q.raw,d.off_raw_data[l]);q.rows++;q.owner=d.off_raw_owner;
 }
 if(collecting_b&&d.off_boundary_valid){
  unsigned c=d.off_boundary_context;auto& q=b_packet[c];
  need(d.off_boundary_ready&&q.rows==T&&q.boundaries==0&&
       d.off_boundary_owner==owner(c),"R14F_B_ON_BOUNDARY_OWNER");
  for(unsigned l=0;l<P;l++)put(q.raw,d.off_c0[l]);
  for(unsigned l=0;l<P;l++)put(q.raw,d.off_c1[l]);q.boundaries++;
 }
}
static void eq_read(DUT& d,unsigned c,unsigned address){
 auto& q=twin_packet[c];
 need(q.rows==T&&q.boundaries==1&&q.owner==owner(c),"R14F_B_TWIN_CANONICAL_AFTER_RAW");
 if(address==q.reads){put(q.canonical,d.read_data[0]);q.reads++;}
 else need(address<q.reads&&gfn16_b_load32(q.canonical.data()+4*address)==d.read_data[0],
           "R14F_B_TWIN_STABLE_CANONICAL");
}
static void clear_b(DUT& d){
 d.b_host_context=d.b_load_we=d.b_read_en=0;d.b_host_addr=d.b_write_data=0;
 d.b_start_contexts=d.b_batch_mode=d.b_feed_mode=d.b_double_bit=0;
 d.b_base=d.b_warm_count=d.b_double_mask=0;
 d.b_command_context=d.b_command_valid=d.b_command_double=0;
 d.b_command_index=d.b_command_generation=0;
 for(unsigned i=0;i<2*P;i++)d.b_initial_c0[i]=d.b_initial_c1[i]=0;
 d.off_begin=d.off_write=d.off_commit=d.off_context=0;
 d.off_index=d.off_word=d.off_base=d.off_generation=d.off_epoch=0;
 for(unsigned i=0;i<3;i++)d.off_reciprocal[i]=d.off_limit[i]=0;
 d.off_raw_ready=d.off_boundary_ready=1;
}
#ifdef R14F_PRP
static unsigned prp_bit(unsigned c,unsigned ordinal){return unsigned(PRP_BITS[c][ordinal]-'0');}
static void run_feed_twin(DUT& d){
 clear(d);clear_b(d);d.rst_n=0;edge(d);d.rst_n=1;edge(d);
 for(unsigned c=0;c<2;c++)for(unsigned a=0;a<N;a++){
  clear(d);d.load_we=1;d.host_context=c;d.host_addr=a;d.write_data=INITIAL[c][a];edge(d);
  need(!d.error&&!d.canonical_ready,"R14F_PRP_COLD_LOAD");
 }
 clear(d);d.start_contexts=d.batch_mode=d.feed_mode=3;
 d.base=uint64_t(BASES[0])|(uint64_t(BASES[1])<<32);
 d.warm_count=uint64_t(COUNTS[0])|(uint64_t(COUNTS[1])<<32);
 d.double_bit=prp_bit(0,0)|(prp_bit(1,0)<<1);edge(d);
 need(!d.error&&d.busy==3&&d.accepted_generation==0x0101,"R14F_PRP_JOINT_START");
 std::array<unsigned,2> next{1,1},reads{},done{};
 unsigned limit=std::max(COUNTS[0],COUNTS[1])*INTERVAL+33*N+10000;
 for(unsigned age=1;age<limit;age++){
  clear(d);unsigned offer=age&1u;
  if(next[offer]<COUNTS[offer]){
   d.command_valid=1;d.command_context=offer;d.command_generation=1;
   d.command_index=next[offer];d.command_double=prp_bit(offer,next[offer]);
  }
  int selected=-1;for(unsigned c=0;c<2;c++)if((d.canonical_ready&(1u<<c))&&reads[c]<N){selected=int(c);break;}
  if(selected>=0){d.read_en=1;d.host_context=unsigned(selected);d.host_addr=reads[selected];}
  d.clk=0;d.eval();bool accepted=d.command_accept;edge(d);if(accepted)next[offer]++;
  need(!d.error,"R14F_PRP_HEALTHY_TWIN_ERROR age="+std::to_string(age));
  need((d.feed_level&7u)<=4&&((d.feed_level>>3)&7u)<=4,"R14F_PRP_TWIN_FIFO_CAPACITY");
  for(unsigned c=0;c<2;c++){
   need(lane32(d.operations_started,c)==launched(age,c)&&lane32(d.completed_squares,c)==completed(age,c),"R14F_PRP_TWIN_EVERY_BIT_CALENDAR");
   if(d.done&(1u<<c)){
    done[c]++;need(d.canonical_ready&(1u<<c)&&!(d.busy&(1u<<c)),"R14F_PRP_TWIN_ATOMIC_PUBLICATION");
    need(lane64(d.canonical_cycles,c)==9*N&&lane64(d.image_copy_cycles,c)==N+4,"R14F_PRP_TWIN_CANONICAL_COPY_ONCE");
   }
  }
  if(selected>=0){read_word(d,unsigned(selected),reads[selected]);reads[selected]++;}
  else need(!d.read_valid,"R14F_PRP_TWIN_UNPUBLISHED_READ");
  if(reads==std::array<unsigned,2>{N,N}){
   need(!d.busy&&!d.feed_level&&next==std::array<unsigned,2>{COUNTS[0],COUNTS[1]}&&
        done==std::array<unsigned,2>{1,1},"R14F_PRP_TWIN_COMPLETE_NO_CHECKPOINT");return;
  }
 }
 need(false,"R14F_PRP_FINITE_COMPLETE_CHAIN");
}
#endif
static void stage_b(DUT& d){
 for(unsigned c=0;c<2;c++){
  auto& q=b_packet[c];clear(d);clear_b(d);
  d.off_begin=1;d.off_context=c;d.off_base=BASES[c];d.off_generation=1;d.off_epoch=EPOCHS[c];
  for(unsigned i=0;i<3;i++){
   d.off_reciprocal[i]=gfn16_b_load32(q.profile.data()+8+4*i);
   d.off_limit[i]=gfn16_b_load32(q.profile.data()+20+4*i);
  }
  edge(d);need(!d.b_error&&!d.off_error&&!(d.off_loaded&(1u<<c)),"R14F_B_BEGIN_ATOMIC_UNLOADED");
  for(unsigned j=0;j<3*N+96;j++){
   clear(d);clear_b(d);d.off_write=1;d.off_context=c;d.off_index=j;
   d.off_word=gfn16_b_load32(q.cold.data()+4*j);edge(d);
   need(!d.b_error&&!d.off_error&&!(d.off_loaded&(1u<<c))&&!d.off_done,
        "R14F_B_PARTIAL_INPUT_UNPUBLISHED");
  }
  clear(d);clear_b(d);d.off_commit=1;d.off_context=c;edge(d);
  need(!d.b_error&&!d.off_error&&(d.off_loaded&(1u<<c))&&!d.off_done,"R14F_B_COMPLETE_INPUT_COMMIT");
 }
}
static void run_b(DUT& d){
 stage_b(d);clear(d);clear_b(d);d.b_start_contexts=d.b_batch_mode=3;
 d.b_base=uint64_t(BASES[0])|(uint64_t(BASES[1])<<32);
 d.b_warm_count=uint64_t(COUNTS[0])|(uint64_t(COUNTS[1])<<32);
 d.b_double_bit=(BITS[0][0]?1u:0u)|(BITS[1][0]?2u:0u);
 d.b_double_mask=uint64_t(BITS[0][1]<<1)|(uint64_t(BITS[1][1]<<1)<<32);
#ifdef R14F_PRP
 d.b_feed_mode=3;d.b_double_bit=prp_bit(0,0)|(prp_bit(1,0)<<1);
#endif
 edge(d);need(!d.off_error&&!d.b_error&&d.b_busy==3&&d.b_accepted_generation==0x0101,
              "R14F_B_START_MATCHED_PROFILE_GENERATION");
 std::array<unsigned,2> finished{},next{1,1},warm{};
 collecting_b=true;
 for(unsigned age=1;age<MAX_EDGES;age++){
  clear(d);clear_b(d);
#ifdef R14F_PRP
  unsigned offer=age&1u;
  if(next[offer]<COUNTS[offer]){
   d.b_command_valid=1;d.b_command_context=offer;d.b_command_generation=1;
   d.b_command_index=next[offer];d.b_command_double=prp_bit(offer,next[offer]);
  }
  d.clk=0;d.eval();bool accepted=d.b_command_accept;
#endif
  edge(d);
#ifdef R14F_PRP
  if(accepted)next[offer]++;
  need((d.b_feed_level&7u)<=4&&((d.b_feed_level>>3)&7u)<=4,"R14F_PRP_ON_FIFO_CAPACITY");
#endif
  need(!d.b_error&&!d.off_error&&!d.b_canonical_ready&&!d.b_read_valid,
       "R14F_B_NO_CANONICAL_HARDWARE_OR_ERROR age="+std::to_string(age));
#ifndef R14F_PRP
  need(!d.b_command_accept&&!d.b_operation_accept&&!d.b_feed_level,"R14F_B_NORMAL_NO_DESCRIPTOR");
#endif
  for(unsigned c=0;c<2;c++){
   need(lane32(d.b_operations_started,c)==launched(age,c)&&
        lane32(d.b_completed_squares,c)==completed(age,c),"R14F_B_EXACT_TWIN_CALENDAR age="+std::to_string(age));
   if(d.b_warm_done&(1u<<c)){need(!warm[c],"R14F_B_ONE_WARM");warm[c]=age;}
   if(d.off_done&(1u<<c)){
    need(warm[c]&&age==warm[c]+2,"R14F_B_ACTUAL_WARM_TO_RAW_DONE_TWO_EDGES");
    need(!finished[c]&&b_packet[c].rows==T&&b_packet[c].boundaries==1&&
         b_packet[c].owner==owner(c)&&!(d.b_busy&(1u<<c)),"R14F_B_FINAL_PACKET_ATOMIC_DONE");
    finished[c]++;
   }
  }
  if(finished[0]&&finished[1]){
#ifdef R14F_PRP
   need(next==std::array<unsigned,2>{COUNTS[0],COUNTS[1]}&&!d.b_feed_level,"R14F_PRP_ON_COMPLETE_NO_CHECKPOINT");
#endif
   collecting_b=false;return;
  }
 }
 need(false,"R14F_B_FINITE_TWIN_COMPLETION");
}
static std::string hex(const std::vector<uint8_t>& raw){
 std::ostringstream s;s<<std::hex<<std::setfill('0');
 for(auto v:raw)s<<std::setw(2)<<unsigned(v);return s.str();
}
// Control packet uses ONLY public pins; no hierarchy force or expected payload.
static void control_reset(DUT& d){
 collecting_twin=collecting_b=false;clear(d);clear_b(d);d.rst_n=0;edge(d);
 need(!d.off_loaded&&!d.off_done&&!d.off_error&&!d.b_error&&!d.off_raw_valid&&
      !d.off_boundary_valid&&!d.b_busy,"R14F_B_CONTROL_RESET_CLEAR");
 d.rst_n=1;edge(d);prepare_packets();
}
static void control_begin(DUT& d,unsigned variant=0){
 clear(d);clear_b(d);auto& q=b_packet[0];d.off_begin=1;d.off_context=0;
 d.off_base=BASES[0];d.off_generation=1;d.off_epoch=EPOCHS[0];
 for(unsigned j=0;j<3;j++){
  d.off_reciprocal[j]=gfn16_b_load32(q.profile.data()+8+4*j);
  d.off_limit[j]=gfn16_b_load32(q.profile.data()+20+4*j);
 }
 if(variant==1)d.off_generation=256;
 if(variant==2)d.off_base=1;
 if(variant==3)d.off_limit[2]|=1u<<13;
 if(variant==4)d.off_generation=2;
 if(variant==5)d.off_epoch^=1;
 if(variant==6)d.off_reciprocal[0]^=1;
 if(variant==7)d.off_limit[0]^=1;
 edge(d);
}
static void control_body(DUT& d,unsigned words=3*N+96){
 for(unsigned j=0;j<words;j++){
  clear(d);clear_b(d);d.off_write=1;d.off_index=j;
  d.off_word=gfn16_b_load32(b_packet[0].cold.data()+4*j);edge(d);
  need(!d.off_error&&!d.off_done&&!d.off_loaded,"R14F_B_CONTROL_PARTIAL_ATOMIC");
 }
}
static void control_commit(DUT& d){clear(d);clear_b(d);d.off_commit=1;edge(d);}
static void control_start(DUT& d){
 clear(d);clear_b(d);d.b_start_contexts=d.b_batch_mode=1;
 d.b_base=BASES[0];d.b_warm_count=COUNTS[0];edge(d);
}
static void control_abort(DUT& d,const std::string& name){
 need(d.off_error||d.b_error,"R14F_B_CONTROL_EXPECTED_ABORT "+name);
 for(unsigned age=0;age<24;age++){
  clear(d);clear_b(d);edge(d);
  need((d.off_error||d.b_error)&&!d.off_done&&!d.off_raw_valid&&!d.off_boundary_valid&&
       !d.b_canonical_ready&&!d.b_read_valid&&!d.b_command_accept&&!d.b_operation_accept,
       "R14F_B_CONTROL_STICKY_NO_PUBLICATION "+name);
 }
 std::cout<<"R14F_B_CONTROL_CASE "<<name<<" abort=1 quiet=24\n";
}
static void host_atomic_controls(){
 auto& q=b_packet[0];uint64_t o=owner(0),initial=(uint64_t(EPOCHS[0])<<8)|1u;
 std::vector<uint8_t> output(4*N,0xa5),raw(4*(N+32));
 // Synthetic valid raw body tests host API validation only, never chip proof.
 gfn16_b_final_info info{{17,18,19},23};auto before=info;
 for(unsigned k=0;k<6;k++){
  auto p=q.profile;unsigned ctx=0;uint64_t actual=o,expected=o;size_t len=raw.size();
  if(k==0)actual^=1ull<<48;if(k==1)actual^=1ull<<8;if(k==2)ctx=1;
  if(k==3)len--;if(k==4)p[8]^=1;if(k==5)expected^=1;
  need(gfn16_b_final_decode(N,p.data(),32,ctx,0,actual,expected,raw.data(),len,
       output.data(),output.size(),&info)!=0&&output==std::vector<uint8_t>(4*N,0xa5)&&
       std::equal(std::begin(info.carry),std::end(info.carry),std::begin(before.carry))&&
       info.special==before.special,"R14F_B_HOST_FINAL_ERROR_ATOMIC");
 }
 std::vector<uint8_t> cold(q.cold.size(),0xa5);
 for(unsigned k=0;k<5;k++){
  auto input=q.input;auto p=q.profile;uint64_t actual=initial;unsigned ctx=0;size_t len=4*N;
  if(k==0)actual^=1ull<<24;if(k==1)ctx=1;if(k==2)len--;
  if(k==3)gfn16_b_store32(input.data(),BASES[0]);if(k==4)p[4]^=1;
  need(gfn16_b_cold_write(N,p.data(),32,ctx,0,actual,initial,input.data(),len,
       input.data()+4*N,128,cold.data(),cold.size())!=0&&
       cold==std::vector<uint8_t>(q.cold.size(),0xa5),"R14F_B_HOST_COLD_ERROR_ATOMIC");
 }
 std::cout<<"R14F_B_HOST_ATOMIC_PASS final_cases=6 cold_cases=5\n";
}
static void controls(DUT& d){
 control_reset(d);host_atomic_controls();
 control_begin(d);control_commit(d);control_abort(d,"empty-commit");
 control_reset(d);control_begin(d);control_body(d,3*N+95);control_commit(d);control_abort(d,"partial-commit");
 for(unsigned k=0;k<2;k++){
  control_reset(d);control_begin(d);clear(d);clear_b(d);d.off_write=1;
  d.off_index=k?0:1;d.off_word=k?104857601u:gfn16_b_load32(b_packet[0].cold.data());
  edge(d);control_abort(d,k?"noncanonical-residue":"skipped-index");
 }
 for(unsigned v=1;v<=3;v++){
  control_reset(d);control_begin(d,v);control_abort(d,v==1?"generation-width":v==2?"base-range":"limit-upper-bits");
 }
 for(unsigned v=4;v<=7;v++){
  control_reset(d);control_begin(d,v);control_body(d);control_commit(d);
  need(d.off_loaded==1&&!d.off_error,"R14F_B_CONTROL_BODY_NOT_PROFILE_PROOF");
  control_start(d);
  for(unsigned age=0;age<500&&!d.off_error&&!d.b_error;age++){
   clear(d);clear_b(d);edge(d);need(!d.off_done&&!d.off_raw_valid&&!d.off_boundary_valid,
                                 "R14F_B_CONTROL_BAD_PROFILE_NO_RAW");
  }
  control_abort(d,v==4?"startup-generation":v==5?"startup-epoch":v==6?"reciprocal-mismatch":"limit-mismatch");
 }
 control_reset(d);control_begin(d);control_body(d,7);control_start(d);control_abort(d,"partial-start");
 control_reset(d);control_begin(d);control_body(d,7);control_reset(d);
 clear(d);clear_b(d);d.off_write=1;edge(d);control_abort(d,"reset-partial-requires-begin");
 control_reset(d);control_begin(d);control_body(d);control_commit(d);control_reset(d);
 control_start(d);control_abort(d,"reset-complete-requires-reload");
 control_reset(d);control_begin(d);control_body(d);control_commit(d);control_begin(d);
 need(!d.off_loaded&&!d.off_done&&!d.off_error,"R14F_B_CONTROL_REBEGIN_ATOMIC");
 control_commit(d);control_abort(d,"rebegin-requires-new-body");
 for(unsigned k=0;k<2;k++){
  control_reset(d);control_begin(d);control_body(d);control_commit(d);control_start(d);
  clear(d);clear_b(d);if(k)d.b_read_en=1;else d.b_load_we=1;edge(d);
  control_abort(d,k?"old-read-forbidden":"old-load-forbidden");
 }
 control_reset(d);control_begin(d);control_body(d);control_commit(d);control_start(d);
 control_begin(d);control_abort(d,"begin-while-busy");
 for(unsigned k=0;k<2;k++){
  control_reset(d);control_begin(d);control_body(d);control_commit(d);control_start(d);
  for(unsigned age=0;age<2000&&!d.off_error&&!d.b_error;age++){
   clear(d);clear_b(d);if(k)d.off_boundary_ready=0;else d.off_raw_ready=0;edge(d);
   need(!d.off_done,"R14F_B_CONTROL_TRANSFER_NOT_PUBLISHED");
  }
  control_abort(d,k?"boundary-receiver-not-ready":"raw-receiver-not-ready");
 }
 control_reset(d);need(!d.off_loaded&&!d.b_busy,"R14F_B_CONTROL_FINAL_RESET_RECOVERY");
 std::cout<<"R14F_B_CONTROL_PASS chip_cases=20 host_cases=11 quiet_edges=480 reset_recovery=1 public_pins_only=1\n";
}
static void finish(){
 for(unsigned c=0;c<2;c++){
  auto& q=b_packet[c];auto& t=twin_packet[c];q.canonical.resize(4*N);
  gfn16_b_final_info info{};
  need(q.raw==t.raw&&t.reads==N,"R14F_B_ACTUAL_RAW_TWIN_EQUAL");
  need(!gfn16_b_final_decode(N,q.profile.data(),32,c,c,q.owner,owner(c),
       q.raw.data(),q.raw.size(),q.canonical.data(),q.canonical.size(),&info),"R14F_B_HOST_FINAL_C");
  need(q.canonical==t.canonical&&q.canonical==q.reference&&!info.special,"R14F_B_THREE_CANONICAL_EQUAL");
  std::cout<<"R14F_B_EQ_PACKET {\"label\":\"dense\",\"n\":"<<N<<",\"p\":"<<P
   <<",\"context\":"<<c<<",\"base\":"<<BASES[c]<<",\"generation\":1,\"epoch_seed\":"<<EPOCHS[c]
   <<",\"count\":"<<COUNTS[c]<<",\"input_owner\":"<<((uint64_t(EPOCHS[c])<<8)|1u)
   <<",\"owner\":"<<q.owner<<",\"input\":\""<<hex(q.input)<<"\",\"cold\":\""<<hex(q.cold)
   <<"\",\"profile\":\""<<hex(q.profile)<<"\",\"raw_twin\":\""<<hex(t.raw)
   <<"\",\"raw_b\":\""<<hex(q.raw)<<"\",\"canonical_twin\":\""<<hex(t.canonical)
   <<"\",\"canonical_host\":\""<<hex(q.canonical)<<"\",\"reference\":\""<<hex(q.reference)<<"\"}\n";
 }
 std::cout<<"R14F_B_EQ_NORMAL_PASS n=65536 contexts=2 counts=2/2 raw_actual=1 cold_actual=1 independent_reference=1\n";
}
int main(int argc,char** argv){try{
 VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d(&context);
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
 if(argc==2&&std::string(argv[1])=="--controls"){
  need(gfn16_runtime::matches(context,d),"R14F_B_ARGUMENTS_RUNTIME");controls(d);return 0;
 }
 need(argc==1&&gfn16_runtime::matches(context,d),"R14F_B_ARGUMENTS_RUNTIME");
 s4_full_reference::self_check();INITIAL={initial(0),initial(1)};EXPECTED=INITIAL;
 for(unsigned c=0;c<2;c++)for(unsigned k=0;k<COUNT;k++)EXPECTED[c]=s4_full_reference::square(EXPECTED[c],BASES[c],BITS[c][k]);
 clear_b(d);prepare_packets();collecting_twin=true;
 std::ostringstream discarded;auto* old=std::cout.rdbuf(discarded.rdbuf());
 try{
#ifdef R14F_PRP
  run_feed_twin(d);
#else
  run(d,3,INITIAL,EXPECTED);
#endif
 }catch(...){std::cout.rdbuf(old);throw;}
 std::cout.rdbuf(old);collecting_twin=false;
 run_b(d);finish();return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
