// Separate immutable fault role; the normal-v1 body is included unchanged.
#define main r15_avmm_normal_body_not_called
#include "stream27_r15_pcie_avmm.cpp"
#undef main
#include <functional>

static void offer(Bench&b){
 b.d.cold_address=0;b.d.cold_burstcount=1;b.d.cold_byteenable=~0u;b.d.cold_write=1;
 const uint64_t owner=b.owners[0];b.d.cold_writedata[0]=0x52315000;
 b.d.cold_writedata[1]=b.session;b.d.cold_writedata[2]=b.leases[0];
 b.d.cold_writedata[3]=owner;b.d.cold_writedata[4]=owner>>32;
 b.d.cold_writedata[5]=0;b.d.cold_writedata[6]=1;b.d.cold_writedata[7]=0;
}
static void accept_cold(Bench&b){b.d.clk=0;b.d.eval();need(!b.d.cold_waitrequest,"R15_AVMM_FAULT_OFFER_READY");b.tick();b.d.cold_write=0;b.idle(24);}
static void export_request(Bench&b){
 b.begin(0,0x01000201);for(unsigned i=0;i<64;i++)b.data(0,b.owners[0],i);b.idle();b.commit();
 b.d.export_address=0;b.d.export_burstcount=3;b.d.export_read=1;
 b.d.clk=0;b.d.eval();need(!b.d.export_waitrequest,"R15_AVMM_FAULT_EXPORT_READY");b.tick();b.d.export_read=0;
}

int main(int argc,char**argv){try{
 if(argc==2&&std::string(argv[1])=="--runtime-probe"){Bench b(argc,argv);return gfn16_runtime::probe(b.c,b.d);}
 need(argc==1,"R15_AVMM_FAULT_ARGV");unsigned cases=0,invalid_records=0;
 auto bad=[&](const std::function<void(Bench&)>&test){Bench b(argc,argv);test(b);b.idle(40);need(b.d.protocol_error&&b.aborts==1,"R15_AVMM_FAULT_NOT_DETECTED_OR_ABORT_DUPLICATED");cases++;};
 bad([](Bench&b){b.write(0x28,1);});
 bad([](Bench&b){b.write(0x80,0);});
 bad([](Bench&b){b.d.ctrl_byteenable=7;b.write(0x20,1009);});
 bad([](Bench&b){b.d.ctrl_address=uint64_t(1)<<32;b.d.ctrl_read=1;b.tick();b.d.ctrl_read=0;});
 bad([](Bench&b){b.d.ctrl_address=0;b.d.ctrl_read=b.d.ctrl_write=1;b.tick();b.d.ctrl_read=b.d.ctrl_write=0;});
 bad([](Bench&b){b.write(0x10,2);});
 bad([](Bench&b){b.write(0x18,0xff000000);});
 bad([](Bench&b){b.begin(0,0x01000201);b.write(0x20,1009);});
 bad([](Bench&b){b.write(0x24,256);b.write(0x40,1);});
 for(unsigned kind=0;kind<8;kind++)bad([kind](Bench&b){
  b.begin(0,0x01000201);offer(b);
  switch(kind){case 0:b.d.cold_writedata[7]=1;break;case 1:b.d.cold_writedata[4]|=1u<<24;break;
   case 2:b.d.cold_writedata[0]=0x52315002;break;case 3:b.d.cold_writedata[5]=64;break;
   case 4:b.d.cold_byteenable=0xfffffffe;break;case 5:b.d.cold_address=1;break;
   case 6:b.d.cold_address=uint64_t(1)<<22;break;case 7:b.d.cold_burstcount=0;break;}
  accept_cold(b);
 });
 bad([](Bench&b){b.begin(0,0x01000201);offer(b);b.d.cold_burstcount=3;accept_cold(b);b.write(0x40,2);});
 // Mutation and withdrawal of a stalled VALID beat are independently illegal.
 bad([](Bench&b){b.d.ctrl_read=1;b.d.ctrl_address=8;b.d.cmd_ready=0;b.tick();b.d.ctrl_read=0;b.tick();
  b.d.ctrl_write=1;b.d.ctrl_address=0x20;b.d.ctrl_writedata=1009;b.tick();b.d.ctrl_writedata=1010;b.tick();
  b.d.ctrl_write=0;b.d.cmd_ready=1;});
 bad([](Bench&b){b.d.ctrl_read=1;b.d.ctrl_address=8;b.d.cmd_ready=0;b.tick();b.d.ctrl_read=0;b.tick();
  b.d.cold_write=1;b.d.cold_burstcount=1;b.tick();b.d.cold_write=0;b.tick();b.d.cmd_ready=1;});
 bad([](Bench&b){Packet p{};put(p,0,4,5);b.responses.push_back(p);b.tick();});
 // NonOK read and wrong full owner/magic/session/index each return only INVALID
 // records; remaining accepted burst beats must drain without successful A32.
 for(unsigned kind=0;kind<5;kind++)bad([&](Bench&b){
  export_request(b);b.respond=false;
  for(unsigned k=0;k<10&&b.responses.empty();k++)b.tick();
  need(!b.responses.empty(),"R15_AVMM_FAULT_RESPONSE_CAPTURE");auto&p=b.responses.front();
  switch(kind){case 0:put(p,8,8,1);break;case 1:p[10]^=1;break;case 2:p[8]^=1;break;
   case 3:p[9]^=1;break;case 4:p[12]^=1;break;}
  b.respond=true;unsigned count=0;
  for(unsigned k=0;k<80;k++){b.tick();if(b.d.export_readdatavalid){for(unsigned j=0;j<8;j++)need(b.d.export_readdata[j]==0,"R15_AVMM_FAULT_VALID_A_LEAK");count++;}}
  need(count==3,"R15_AVMM_FAULT_BURST_NOT_DRAINED");invalid_records+=count;
 });
 // Common reset clears caches and local fault/command state. This harness clears
 // its responder queue too; it is NOT an independent CDC/reset drain proof.
 {Bench b(argc,argv);b.begin(0,0x01000201);b.d.reset=1;b.responses.clear();b.tick();b.d.reset=0;b.idle();
  need(!b.d.protocol_error&&!b.d.cmd_valid,"R15_AVMM_RESET_LOCAL_STATE");
  b.d.export_address=0;b.d.export_burstcount=1;b.d.export_read=1;b.tick();b.d.export_read=0;b.idle(30);
  need(b.d.protocol_error&&b.aborts==1,"R15_AVMM_RESET_STALE_CACHE");cases++;}
 need(cases==27&&invalid_records==15,"R15_AVMM_FAULT_COVERAGE");
 std::cout<<"R15_AVMM_FAULT_PASS cases=27 invalid_records=15 one_abort=1 reset_cache=1 vendor_core=0\n";
 return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
