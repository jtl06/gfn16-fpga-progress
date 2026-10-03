// Private reset/negative successor; exact paired production leaf files unchanged.
#define main fold_payload_existing_main
#include "stream27_canonical_fold_payload.cpp"
#undef main

int main(int argc,char** argv){try{
 H h(argc,argv);
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(h.context,h.d);
 need(argc==2,"FOLD_PAYLOAD_FAULT_ARGUMENTS");
 if(std::string(argv[1])=="--wrong-word"){
  normal(h);h.clear();h.d.read_req=1;h.d.read_address=0;h.edge();h.d.read_req=0;h.edge();h.word(0,0,true);
  throw std::runtime_error("FOLD_PAYLOAD_WRONG_WORD_MISSED");
 }
 need(std::string(argv[1])=="--bounds","FOLD_PAYLOAD_FAULT_MODE");
 // Reset before the real first READ/VALUE/PROCESS edges and final VALUE/PROCESS.
 // Fold payload itself is not forced/zeroed; the ordinary FSM resets eligibility.
 unsigned resets=0,recovery_reads=0;
 for(unsigned target:{1u,2u,3u,9*N-1,9*N}){
  auto x=input();h.image(x); // Establish a prior completed image first.
  h.reset();h.load(x);h.begin();
  for(unsigned age=1;age<target;age++){h.clear();h.edge();
   need(h.d.local_busy&&!h.d.local_error&&!h.d.local_done,"FOLD_PAYLOAD_PRE_RESET_BUSY");}
  h.clear();h.d.rst_n=0;h.edge();
  need(!h.d.local_busy&&!h.d.local_done&&!h.d.local_image_valid&&!h.d.local_read_valid&&!h.d.local_error,
       "FOLD_PAYLOAD_PHASE_RESET_INVALIDATION");
  h.d.rst_n=1;h.clear();for(unsigned k=0;k<8;k++){h.edge();
   need(!h.d.local_done&&!h.d.local_image_valid&&!h.d.local_read_valid&&!h.d.local_error,
        "FOLD_PAYLOAD_STALE_TUPLE_INELIGIBLE");}
  h.image(x);h.all(x);resets++;recovery_reads+=N;
 }
 need(resets==5&&recovery_reads==1280,"FOLD_PAYLOAD_PHASE_RESET_COUNTS");
 h.reads=h.images=0;bounds(h);h.sample();
 std::cout<<"FOLD_PAYLOAD_PHASE_RESET_PASS events=5 first_READ_VALUE_PROCESS=3 final_VALUE_PROCESS=2 quiet_edges=40 recovery_signed96_reads=1280 paired_edges=1 payload_zero_assumed=0 os_threads_peak="<<peak_os_threads<<"\n";
 return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
