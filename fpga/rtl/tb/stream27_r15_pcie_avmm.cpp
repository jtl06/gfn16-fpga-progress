#include "Vgenefer_stream27_r15_pcie_avmm_v1.h"
#include "native_runtime_context_v1.h"
#include <array>
#include <cstdint>
#include <deque>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using Packet=std::array<uint32_t,16>;
static void need(bool b,const char* s){if(!b)throw std::runtime_error(s);}
static uint64_t get(const Packet&p,unsigned bit,unsigned width){uint64_t v=0;for(unsigned j=0;j<width;j++)v|=uint64_t((p[(bit+j)/32]>>((bit+j)%32))&1)<<j;return v;}
static void put(Packet&p,unsigned bit,unsigned width,uint64_t v){for(unsigned j=0;j<width;j++){auto&m=p[(bit+j)/32];const uint32_t b=uint32_t(1)<<((bit+j)%32);m=(m&~b)|(((v>>j)&1)?b:0);}}
class Bench{
public:
 VerilatedContext c;Vgenefer_stream27_r15_pcie_avmm_v1 d;
 std::deque<Packet> responses;std::vector<Packet> commands;
 uint32_t session=7,next_lease=1,gen=0,epochs=0x1234abcd,applied=0;
 unsigned aborts=0,reads=0,edges=0;
 bool respond=true,read_not_ready=false;
 uint64_t owners[2]={0,0};uint32_t leases[2]={0,0};
 static VerilatedContext* setup(VerilatedContext&ctx,int argc,char**argv){gfn16_runtime::configure(ctx,argc,argv);return &ctx;}
 Bench(int argc,char**argv):d(setup(c,argc,argv)){
  d.clk=0;d.reset=1;d.link_ready=0;d.ctrl_read=d.ctrl_write=d.cold_write=d.export_read=0;
  d.cmd_ready=1;d.resp_valid=0;d.ctrl_byteenable=15;d.cold_byteenable=~0u;
  for(unsigned i=0;i<3;i++)tick();d.reset=0;d.link_ready=1;tick();
 }
 Packet make_response(const Packet&q){
  Packet p{};unsigned op=get(q,0,4),ctx=get(q,4,1);put(p,0,4,op);put(p,16,1,ctx);
  if(op==1){owners[ctx]=get(q,5,56);leases[ctx]=next_lease++;applied=0;}
  if(op==15){aborts++;put(p,8,8,2);}
  put(p,32,32,session);put(p,64,32,next_lease);put(p,96,16,gen);put(p,112,32,epochs);
  put(p,144,2,3);put(p,146,2,3);put(p,150,2,3);put(p,160,32,applied);
  if(op==6){
   reads++;unsigned idx=get(q,224,32);need(get(q,61,32)==session&&get(q,5,56)==owners[ctx]&&get(q,93,32)==leases[ctx],"R15_AVMM_READ_COMMAND_AUTHORITY");
   if(read_not_ready)put(p,8,8,1);
   else{p[8]=0x52314100|ctx;p[9]=session;p[10]=uint32_t(owners[ctx]);p[11]=owners[ctx]>>32;p[12]=idx;p[13]=0x81230000|idx;p[14]=0x76543210;p[15]=0xfedcba98;}
  }
  return p;
 }
 void tick(){
  d.clk=0;d.resp_valid=respond&&!responses.empty();
  if(d.resp_valid)for(unsigned i=0;i<16;i++)d.resp_data[i]=responses.front()[i];d.eval();
  const bool response=d.resp_valid&&d.resp_ready;
  const bool fire=d.cmd_valid&&d.cmd_ready&&!d.reset;Packet q{};
  if(fire)for(unsigned i=0;i<16;i++)q[i]=d.cmd_data[i];
  if(response)responses.pop_front();
  d.clk=1;d.eval();c.timeInc(1);edges++;
  if(fire){commands.push_back(q);if(get(q,0,4)==0)applied++;else responses.push_back(make_response(q));}
 }
 void idle(unsigned n=8){for(unsigned i=0;i<n;i++)tick();}
 void write(uint32_t addr,uint32_t v){d.ctrl_address=addr;d.ctrl_writedata=v;d.ctrl_write=1;d.clk=0;d.eval();unsigned k=0;while(d.ctrl_waitrequest){tick();d.clk=0;d.eval();need(++k<200,"R15_AVMM_CTRL_TIMEOUT");}tick();d.ctrl_write=0;idle();}
 uint32_t read(uint32_t addr){d.ctrl_address=addr;d.ctrl_read=1;d.clk=0;d.eval();unsigned k=0;while(d.ctrl_waitrequest){tick();d.clk=0;d.eval();need(++k<200,"R15_AVMM_CTRL_TIMEOUT");}tick();d.ctrl_read=0;while(!d.ctrl_readdatavalid){tick();need(++k<200,"R15_AVMM_RESPONSE_TIMEOUT");}auto v=d.ctrl_readdata;idle();return v;}
 void begin(unsigned ctx,uint64_t owner){write(0x10,ctx);write(0x14,owner);write(0x18,owner>>32);write(0x1c,2);write(0x20,1009);write(0x24,1);write(0x50,1);write(0x64,session);write(0x40,1);need(!d.protocol_error,"R15_AVMM_BEGIN");}
 void data(unsigned ctx,uint64_t owner,unsigned idx,unsigned burst=1,bool last=true){
  d.cold_address=0;d.cold_burstcount=burst;d.cold_writedata[0]=0x52315000|ctx;
  d.cold_writedata[1]=session;d.cold_writedata[2]=leases[ctx];d.cold_writedata[3]=owner;d.cold_writedata[4]=owner>>32;
  d.cold_writedata[5]=idx;d.cold_writedata[6]=idx==0?0xffffffffu:idx;d.cold_writedata[7]=0;d.cold_write=1;
  d.clk=0;d.eval();unsigned k=0;while(d.cold_waitrequest){tick();d.clk=0;d.eval();need(++k<200,"R15_AVMM_COLD_TIMEOUT");}
  tick();if(last)d.cold_write=0;
 }
 void commit(){write(0x68,next_lease-1);write(0x40,2);need(!d.protocol_error,"R15_AVMM_COMMIT");}
};

int main(int argc,char**argv){try{
 // Runtime configuration must precede construction even for probe/fault paths.
 Bench b(argc,argv);if(argc==2&&std::string(argv[1])=="--runtime-probe")return gfn16_runtime::probe(b.c,b.d);
 need(gfn16_runtime::matches(b.c,b.d),"R15_AVMM_RUNTIME");
 const bool faults=argc==2&&std::string(argv[1])=="--faults";need(argc==1||faults,"R15_AVMM_ARGV");
 if(faults){
  b.write(0x28,1);b.idle(20);need(b.d.protocol_error&&b.aborts==1,"R15_AVMM_RESERVED_ABORT");
  b.idle(20);need(b.aborts==1,"R15_AVMM_ABORT_LOOP");
  std::cout<<"R15_AVMM_FAULT_PASS reserved_abort=1 one_abort=1 vendor_core=0\n";return 0;
 }
 need(b.read(0)==0x52313541&&b.read(4)==0x10000&&b.read(8)==7,"R15_AVMM_ID_SNAPSHOT");
 b.gen=0x07ff;need(b.read(0x58)==256&&b.read(0x54)==0xabcd,"R15_AVMM_EXHAUSTION_NO_TRUNCATION");
 b.write(0x10,1);need(b.read(0x58)==8&&b.read(0x54)==0x1234,"R15_AVMM_SELECTED_SNAPSHOT");b.gen=0;
 const uint64_t owner0=(uint64_t(1)<<24)|(0xabceu<<8)|1,owner1=(uint64_t(1)<<24)|(0x1235u<<8)|1;
 b.begin(0,owner0);need(b.read(0x5c)==1,"R15_AVMM_BEGIN_LEASE");
 for(unsigned i=0;i<64;i++){if(i<3)b.data(0,owner0,i,3,i==2);else b.data(0,owner0,i);}
 b.idle();need(b.read(0x44)==64&&b.read(0x48)==64,"R15_AVMM_TRANSPORT_PHYSICAL_COUNTS");
 for(const auto&q:b.commands)if(get(q,0,4)==0){auto idx=get(q,224,32);need(get(q,4,1)==0&&get(q,5,56)==owner0&&get(q,61,32)==7&&get(q,93,32)==1&&get(q,256,32)==(idx==0?0xffffffffu:idx),"R15_AVMM_DATA32_EXACT");}
 b.commit();b.begin(1,owner1);for(unsigned i=0;i<64;i++)b.data(1,owner1,i);b.idle();b.commit();
 b.write(0x68,2);b.write(0x6c,3);b.write(0x40,4);
 need(get(b.commands.back(),0,4)==4&&get(b.commands.back(),224,32)==3,"R15_AVMM_START_MASK");
 b.write(0x70,1);b.write(0x74,0x89abcdef);b.write(0x78,1);b.write(0x7c,1);b.write(0x40,7);
 need(get(b.commands.back(),0,4)==7&&get(b.commands.back(),224,32)==0x89abcdef&&get(b.commands.back(),256,32)==1,"R15_AVMM_DESCRIPTOR");
 b.d.export_address=(uint64_t(1)<<22)+32*29;b.d.export_burstcount=3;b.d.export_read=1;
 b.d.clk=0;b.d.eval();need(!b.d.export_waitrequest,"R15_AVMM_EXPORT_READY");b.tick();b.d.export_read=0;
 unsigned seen=0;for(unsigned k=0;k<100&&seen<3;k++){b.tick();if(b.d.export_readdatavalid){need(b.d.export_readdata[0]==0x52314101&&b.d.export_readdata[1]==7&&b.d.export_readdata[2]==uint32_t(owner1)&&b.d.export_readdata[3]==owner1>>32&&b.d.export_readdata[4]==29+seen&&b.d.export_readdata[5]==(0x81230000u|29+seen)&&b.d.export_readdata[7]==0xfedcba98,"R15_AVMM_A32_BODY");seen++;}}
 need(seen==3&&!b.d.protocol_error,"R15_AVMM_EXPORT_DRAIN");
 // Command holding payload remains bit-identical across core FIFO backpressure.
 b.respond=false;b.d.cmd_ready=0;b.d.ctrl_read=1;b.d.ctrl_address=8;b.tick();b.d.ctrl_read=0;
 Packet held{};for(unsigned i=0;i<16;i++)held[i]=b.d.cmd_data[i];for(unsigned k=0;k<11;k++){b.tick();need(b.d.cmd_valid,"R15_AVMM_HELD_VALID");for(unsigned i=0;i<16;i++)need(b.d.cmd_data[i]==held[i],"R15_AVMM_HELD_COMMAND");}
 b.d.cmd_ready=1;b.respond=true;b.idle();need(!b.d.protocol_error,"R15_AVMM_NO_ERROR");
 std::cout<<"R15_AVMM_NORMAL_PASS data_records=128 contexts=2 burst=3 A32=3 snapshot=selected command_hold=11 vendor_core=0\n";
 b.d.final();return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
