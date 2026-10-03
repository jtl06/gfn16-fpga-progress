// Native-only PRE-edge endpoint observations; no datapath or state substitution.
#pragma once
#include <algorithm>
#include <array>
#include <iomanip>
#include <sstream>
#include <vector>
#include "stream27_host_chain_full_reference_v1.h"

struct OffloadEndpoint {
 struct Packet {
  std::vector<uint32_t> raw,actual,reference;
  std::array<uint32_t,P> c0{},c1{};
  uint64_t owner=0; unsigned rows=0,boundaries=0,read_count=0;
  std::vector<bool> seen;
 };
 std::array<Packet,2> packet;
 std::array<uint64_t,2> expected_owner{};
 unsigned mask=0;std::string label;
 void begin(unsigned enabled,const std::array<unsigned,2>& counts,const std::string& name){
  mask=enabled;label=name;
  for(unsigned c=0;c<2;c++){
   packet[c]=Packet{};packet[c].raw.resize(N);packet[c].actual.resize(N);
   packet[c].reference.resize(N);packet[c].seen.resize(N);
   expected_owner[c]=(uint64_t(counts[c]-1)<<24)|(uint64_t(uint16_t(EPOCHS[c]+counts[c]-1))<<8)|1u;
  }
 }
 void pre(DUT& d){
  if(!d.rst_n)return;
  if(d.off_raw_valid){
   unsigned c=d.off_raw_context;need((mask&(1u<<c))!=0,"B_ENDPOINT_RAW_CONTEXT");
   need(d.off_capture_fire&&uint64_t(d.off_raw_owner)==expected_owner[c]&&
        uint64_t(d.off_raw_owner)==uint64_t(d.off_raw_live_owner),"B_ENDPOINT_RAW_FULL_OWNER");
   auto& q=packet[c];need(q.boundaries==0&&q.rows<T&&unsigned(d.off_raw_row)==q.rows,"B_ENDPOINT_RAW_ROW_ORDER");
   q.owner=d.off_raw_owner;
   for(unsigned lane=0;lane<P;lane++)q.raw[q.rows*P+lane]=d.off_raw_data[lane];
   q.rows++;
  }
  if(d.off_boundary_valid){
   unsigned c=d.off_boundary_context;auto& q=packet[c];
   need((mask&(1u<<c))&&q.rows==T&&q.boundaries==0&&
        uint64_t(d.off_boundary_owner)==expected_owner[c]&&
        uint64_t(d.off_boundary_owner)==uint64_t(d.off_boundary_live_owner)&&
        q.owner==uint64_t(d.off_boundary_owner),"B_ENDPOINT_BOUNDARY_FULL_OWNER");
   for(unsigned lane=0;lane<P;lane++){q.c0[lane]=d.off_c0[lane];q.c1[lane]=d.off_c1[lane];}
   q.boundaries++;
  }
 }
 void read(unsigned c,unsigned address,uint32_t actual,int32_t reference){
  auto& q=packet[c];need(q.rows==T&&q.boundaries==1&&address<N,"B_ENDPOINT_READ_AFTER_COMPLETE_CAPTURE");
  if(q.seen[address])need(q.actual[address]==actual&&q.reference[address]==uint32_t(reference),"B_ENDPOINT_STABLE_READ");
  else{q.seen[address]=true;q.actual[address]=actual;q.reference[address]=uint32_t(reference);q.read_count++;}
 }
 static std::string hex(const std::vector<uint32_t>& words){
  std::ostringstream s;s<<std::hex<<std::setfill('0');
  for(auto word:words)for(unsigned byte=0;byte<4;byte++)s<<std::setw(2)<<((word>>(8*byte))&255u);
  return s.str();
 }
 void finish(){
  for(unsigned c=0;c<2;c++)if(mask&(1u<<c)){
   auto& q=packet[c];need(q.rows==T&&q.boundaries==1&&q.read_count==N,"B_ENDPOINT_COMPLETE_PACKET");
   auto raw=q.raw;raw.insert(raw.end(),q.c0.begin(),q.c0.end());raw.insert(raw.end(),q.c1.begin(),q.c1.end());
   std::cout<<"B_ENDPOINT_PACKET {\"label\":\""<<label<<"\",\"n\":"<<N<<",\"p\":"<<P
    <<",\"context\":"<<c<<",\"base\":"<<BASES[c]<<",\"owner\":"<<q.owner
    <<",\"rows\":"<<q.rows<<",\"boundaries\":"<<q.boundaries<<",\"words\":"<<q.read_count
    <<",\"raw\":\""<<hex(raw)<<"\",\"actual\":\""<<hex(q.actual)<<"\",\"reference\":\""<<hex(q.reference)<<"\"}\n";
  }
 }
};
static OffloadEndpoint offload;

// A same-DUT special image: (x^(N/2))^2 = x^N = -1 mod (b^N+1).
// The independent worker reference computes the square, rather than inserting
// a synthetic raw endpoint or substituting a different tiny-geometry DUT.
static void offload_sentinel(DUT& d){
 offload.begin(3,{1,1},"sentinel");
 std::array<std::vector<int32_t>,2> input,reference;
 for(unsigned c=0;c<2;c++){
  input[c].assign(N,0);input[c][N/2]=1;
  reference[c]=s4_full_reference::square(input[c],BASES[c],0);
  need(reference[c][0]==-1&&std::all_of(reference[c].begin()+1,reference[c].end(),[](int32_t x){return x==0;}),"B_ENDPOINT_INDEPENDENT_SENTINEL");
 }
 clear(d);d.rst_n=0;edge(d);need(!d.error&&!d.busy&&!d.read_valid&&!d.canonical_ready,"B_ENDPOINT_SENTINEL_RESET");
 d.rst_n=1;clear(d);edge(d);
 for(unsigned c=0;c<2;c++)for(unsigned a=0;a<N;a++){
  clear(d);d.host_context=c;d.host_addr=a;d.write_data=uint32_t(input[c][a]);d.load_we=1;edge(d);
  need(!d.error&&!d.read_valid&&!d.canonical_ready,"B_ENDPOINT_SENTINEL_LOAD");
 }
 clear(d);d.start_contexts=d.batch_mode=3;d.base=uint64_t(BASES[0])|(uint64_t(BASES[1])<<32);
 d.warm_count=1ull|(1ull<<32);edge(d);need(d.busy==3&&!d.error,"B_ENDPOINT_SENTINEL_START");
 std::array<unsigned,2> next{},done{};uint64_t age=0;
 for(age=1;age<3*11ull*N+100000;age++){
  clear(d);int selected=-1;
  for(unsigned c=0;c<2;c++)if((d.canonical_ready&(1u<<c))&&next[c]<N){selected=int(c);break;}
  if(selected>=0){d.read_en=1;d.host_context=unsigned(selected);d.host_addr=next[selected];}
  edge(d);need(!d.error,"B_ENDPOINT_SENTINEL_DUT_ERROR");
  for(unsigned c=0;c<2;c++)if(d.done&(1u<<c)){
   done[c]++;need((d.canonical_ready&(1u<<c))&&!(d.busy&(1u<<c)),"B_ENDPOINT_SENTINEL_ATOMIC_PUBLICATION");
   need(lane64(d.canonical_cycles,c)==10ull*N&&lane64(d.image_copy_cycles,c)==N+3,"B_ENDPOINT_SENTINEL_CANONICAL_COPY_COST");
  }
  if(selected>=0){
   unsigned c=unsigned(selected),a=next[c];int32_t expected=reference[c][a];uint32_t sign=expected<0?0xffffffffu:0;
   need(d.read_valid&&d.read_context==c&&uint64_t(d.read_owner)==offload.expected_owner[c]&&
        d.read_data[0]==uint32_t(expected)&&d.read_data[1]==sign&&d.read_data[2]==sign,"B_ENDPOINT_SENTINEL_PROTECTED_SIGNED96");
   offload.read(c,a,d.read_data[0],expected);next[c]++;
  }else need(!d.read_valid,"B_ENDPOINT_SENTINEL_NO_UNPUBLISHED_READ");
  if(d.canonical_ready==3&&next[0]==N&&next[1]==N)break;
 }
 need(age<3*11ull*N+100000&&done[0]==1&&done[1]==1&&!d.busy&&
      uint32_t(d.completed_squares)==1&&uint32_t(d.completed_squares>>32)==1,"B_ENDPOINT_SENTINEL_FINITE_ONE_SQUARE");
 offload.finish();
 std::cout<<"B_ENDPOINT_SENTINEL_PASS {\"n\":"<<N<<",\"p\":"<<P<<",\"squares\":2,\"reads\":"<<2*N<<",\"special\":true,\"signed96\":true,\"independent_reference\":true}\n";
}
