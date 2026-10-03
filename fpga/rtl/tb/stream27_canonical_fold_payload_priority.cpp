// Exact simulation-only priority probes; no production source edits.
#define main fold_payload_existing_main
#include "stream27_canonical_fold_payload.cpp"
#undef main
#include "Vgenefer_stream27_canonical_fold_payload_pair_v1___024root.h"

#define PARENT(member) h.d.rootp->genefer_stream27_canonical_fold_payload_pair_v1__DOT__parent_dut__DOT__ ## member
#define LOCAL(member) h.d.rootp->genefer_stream27_canonical_fold_payload_pair_v1__DOT__local_dut__DOT__ ## member

static void load_under(H& h,uint32_t base,uint32_t word){
 h.reset();h.clear();h.d.base=base;
 for(unsigned r=0;r<T;r++){
  h.d.load_valid=1;h.d.load_row=r;for(unsigned b=0;b<P;b++)h.d.load_data[b]=word;
  h.edge();need(!h.d.local_error&&!h.d.local_busy,"FOLD_PAYLOAD_PRIORITY_LEGAL_LOAD");
 }
 h.clear();h.d.base=599;for(unsigned b=0;b<P;b++)h.d.c0[b]=h.d.c1[b]=0;
}

int main(int argc,char** argv){try{
 H h(argc,argv);
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(h.context,h.d);
 need(argc==2&&std::string(argv[1])=="--priority","FOLD_PAYLOAD_PRIORITY_ARGUMENTS");
 // Genuine protocol-only double fault: digit valid at LOADbase5000, invalid
 // at accepted BEGINbase599, and value2500+c0598 exceeds the fold range.
 load_under(h,5000,2500);h.d.c0[0]=598;h.d.begin_canonical=1;h.edge();
 need(h.d.local_busy&&!h.d.local_error,"FOLD_PAYLOAD_PRIORITY_ACCEPTED_BEGIN");
 h.clear();h.edge();h.edge();
 need(PARENT(state)==3&&LOCAL(state)==3&&PARENT(stored_digit_bad)&&LOCAL(stored_digit_bad)&&
      LOCAL(fold_range_payload)&&PARENT(process_bad)&&LOCAL(process_bad)&&
      PARENT(process_code)==6&&LOCAL(process_code)==6&&!h.d.local_error,
      "FOLD_PAYLOAD_DIGIT_BEFORE_INTERNAL_PREEDGE");
 h.edge();h.quarantine(6);
 unsigned internal=0;
 // Simulation-only correction0-FF mutations after legal BEGIN/before VALUE.
 // Same actual FF in each DUT; no payload/valid/state/error/owner is forced.
 for(int32_t q:{1797,-1797,INT32_MIN,INT32_MAX}){
  load_under(h,599,0);h.d.begin_canonical=1;h.edge();h.clear();
  need(PARENT(state)==1&&LOCAL(state)==1&&!h.d.local_error,"FOLD_PAYLOAD_INTERNAL_BEGIN_FIRST");
  PARENT(correction0)[0]=uint32_t(q);LOCAL(correction0)[0]=uint32_t(q);
  h.edge();h.edge();
  const uint64_t expected=uint64_t(int64_t(q))&((1ull<<34)-1);
  const uint64_t expected_remainder=uint64_t(int64_t(q)+(q<0?1198:-1198))&((1ull<<34)-1);
  const unsigned expected_q=q<0?6u:2u; // signed3 -2 versus +2
  need(PARENT(correction0)[0]==uint32_t(q)&&LOCAL(correction0)[0]==uint32_t(q)&&
       PARENT(value)==expected&&LOCAL(fold_q_payload)==expected_q&&
       LOCAL(fold_remainder_payload)==expected_remainder&&
       !PARENT(stored_digit_bad)&&!LOCAL(stored_digit_bad)&&LOCAL(fold_range_payload)&&
       PARENT(process_code)==7&&LOCAL(process_code)==7&&!h.d.local_error,
       "FOLD_PAYLOAD_ACTUAL_SIGNED_VALUE_INTERNAL_PREEDGE");
  h.edge();h.quarantine(7);internal++;
 }
 h.reads=h.images=0;auto x=input();h.image(x);h.all(x);h.sample();
 need(internal==4&&h.reads==256,"FOLD_PAYLOAD_PRIORITY_RECOVERY_COUNTS");
 std::cout<<"FOLD_PAYLOAD_PRIORITY_PASS protocol_digit_internal_cases=1 digit_code=6 correction_FF_internal_cases=4 internal_code=7 signed_extrema=1 exact_PROCESS_origin=1 recovery_signed96_reads=256 paired_edges=1 production_mutated=0 simulation_only=1 os_threads_peak="<<peak_os_threads<<"\n";
 return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
