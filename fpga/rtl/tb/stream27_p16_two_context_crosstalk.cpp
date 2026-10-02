// Full-size native-only word-route mutant. Production RTL and reference remain
// unchanged; the peer is fully verified while the mutation is armed.
#define main r84_unchanged_normal_entry
#include "stream27_p16_two_context_full_native.cpp"
#undef main

int main(int argc,char**argv){try{
 VerilatedContext context;gfn16_runtime::configure(context,argc,argv);DUT d{&context};
 if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(context,d);
 need(argc==1&&gfn16_runtime::matches(context,d),"R84_CROSSTALK_ARGUMENTS_THREADS");
 const auto begin=std::chrono::steady_clock::now();d.mutant_enable=0;
 s4_full_reference::self_check();
 std::array<Image,2> input={initial(0),initial(1)},reference=input;
 for(unsigned c=0;c<2;c++)for(unsigned k=0;k<COUNT;k++)reference[c]=s4_full_reference::square(reference[c],BASES[c],BITS[c][k]);
 Result joint=run(d,3,input,reference);
 // All original joint/publication/owner checks passed before arming a single
 // output-word bit corruption, not a RAM/configuration or oracle modification.
 d.mutant_enable=1;
 for(unsigned address=0;address<N;address++){
  clear(d);d.read_en=1;d.host_context=1;d.host_addr=address;edge(d);
  need(!d.error&&!d.busy&&d.canonical_ready==3,"R84_CROSSTALK_PEER_PUBLICATION");
  need(read(d,1,address,reference[1])==joint.image[1][address],"R84_CROSSTALK_PEER_FULL_IMAGE");
 }
 clear(d);d.read_en=1;d.host_context=0;d.host_addr=17;edge(d);
 need(d.read_valid&&!d.read_context&&uint64_t(d.read_owner)==owner(0),"R84_CROSSTALK_METADATA_UNCHANGED");
 need(Word{d.read_data[0],d.read_data[1],d.read_data[2]}==
      Word{joint.image[0][17][0]^1u,joint.image[0][17][1],joint.image[0][17][2]},"R84_CROSSTALK_EXACT_ONE_BIT");
 bool rejected=false;
 try{(void)read(d,0,17,reference[0]);}
 catch(const std::runtime_error& error){
  need(std::string(error.what())=="R84_FULL_SIGNED96_REFERENCE ctx=0 address=17","R84_CROSSTALK_EXACT_TYPED_MISMATCH");rejected=true;
 }
 need(rejected,"R84_CROSSTALK_MISSING_TYPED_MISMATCH");
 clear(d);d.read_en=1;d.host_context=1;d.host_addr=17;edge(d);
 need(read(d,1,17,reference[1])==joint.image[1][17],"R84_CROSSTALK_PEER_POST_REJECTION");
 clear(d);edge(d);need(!d.error&&!d.read_valid&&d.canonical_ready==3,"R84_CROSSTALK_DRAIN");
 const double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
 std::cout<<"R84_C2_CROSSTALK_PASS {\"aw\":16,\"p\":16,\"contexts\":2,\"bases\":["<<BASES[0]<<","<<BASES[1]
  <<"],\"squares\":4,\"peer_verified_words\":"<<N<<",\"mutated_context\":0,\"mutated_address\":17,\"typed_mismatches\":1,\"signed96\":true,\"peer_bit_identical\":true,\"metadata_unchanged\":true,\"native_output_word_only\":true,\"model_threads\":"<<d.threads()<<",\"seconds\":"<<seconds<<"}\n";
 d.final();return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
