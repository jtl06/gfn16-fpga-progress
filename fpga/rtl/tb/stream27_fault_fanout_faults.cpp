// Independent fault/calendar oracle for the actual bounded P8 warm field.
// Normal numerical values are qualified by the separately submitted NTT role.
#include "s4_fault_fanout_config.h"
#include <verilated.h>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
static void need(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
static void clear(DUT& d){
    d.in_slot_valid=0;d.frame_start=0;d.correction_valid=0;d.context_enabled=1;
    d.generation_in=7;d.live_generation=7;d.base_in=1000000000;d.epoch_in=0;
    d.correction_epoch=0;d.correction_generation=7;d.debug_drop_forward=0;d.debug_mask_replica_set=0;
    for(unsigned lane=0;lane<P;++lane){d.data_in[lane]=0;d.c0_in[lane]=0;d.c1_in[lane]=0;}
}
static void replicas(const DUT& d){
    need(d.monitor_quarantine==(d.monitor_original_fault?3:0),"S4_FAULT_FANOUT_REPLICA_ORIGIN_EDGE");
}
static void reset(DUT& d){
    d.clk=0;clear(d);d.rst_n=0;d.eval();d.clk=1;d.eval();
    need(!d.out_error && !d.monitor_original_fault && !d.monitor_quarantine && !d.out_slot_valid &&
         !d.commit_valid && !d.owner_count,"S4_FAULT_FANOUT_ONE_EDGE_RESET");
    d.clk=0;d.rst_n=1;d.eval();
}
static void drive_frame(DUT& d,unsigned tick){
    clear(d);d.in_slot_valid=tick<T;d.frame_start=tick==0;d.correction_valid=tick==0;
}
static void failed_tail(DUT& d){
    for(unsigned j=0;j<16;++j){
        d.clk=0;clear(d);d.in_slot_valid=1;d.frame_start=1;d.correction_valid=1;d.epoch_in=1;d.eval();
        need(!d.frame_accept && !d.correction_accept && d.out_error && d.monitor_quarantine==3,
             "S4_FAULT_FANOUT_STICKY_FAILED_ADMISSION");
        d.clk=1;d.eval();replicas(d);
        need(!d.out_slot_valid && !d.commit_valid && d.out_error,"S4_FAULT_FANOUT_QUIET16_STALE_TAIL");
    }
}
struct Counts {unsigned cases=0,normal_frames=0,normal_rows=0,legal_origin_commits=0,canceled_rows=0,reset_aborts=0;};
static void normal(DUT& d,Counts& c){
    reset(d);unsigned physical=0,commits=0;
    for(unsigned tick=0;tick<SINK+T+8;++tick){
        d.clk=0;drive_frame(d,tick);d.eval();
        need(bool(d.frame_accept)==(tick==0) && bool(d.correction_accept)==(tick==0),"S4_FAULT_FANOUT_NORMAL_ADMISSION");
        need(!d.fault_pending && !d.out_error,"S4_FAULT_FANOUT_NORMAL_PRE_FAULT");
        d.clk=1;d.eval();replicas(d);need(!d.out_error,"S4_FAULT_FANOUT_NORMAL_REGISTERED_FAULT");
        need(bool(d.out_slot_valid)==(tick>=FIRST && tick<FIRST+T),"S4_FAULT_FANOUT_NORMAL_PHYSICAL_CALENDAR");
        need(bool(d.commit_valid)==(tick>=SINK && tick<SINK+T),"S4_FAULT_FANOUT_NORMAL_COMMIT_CALENDAR");
        if(d.out_slot_valid){
            need(d.out_epoch==0 && d.generation_out==7 && d.output_row==tick-FIRST,"S4_FAULT_FANOUT_NORMAL_PHYSICAL_TAG");
            for(unsigned word=0;word<WORDS;++word)need(d.data_out[word]==0,"S4_FAULT_FANOUT_ZERO_PHYSICAL_WORD");
            ++physical;
        }
        if(d.commit_valid){
            need(d.commit_epoch==0 && d.commit_generation==7,"S4_FAULT_FANOUT_NORMAL_COMMIT_TAG");
            for(unsigned word=0;word<WORDS;++word)need(d.commit_data[word]==0,"S4_FAULT_FANOUT_ZERO_COMMIT_WORD");
            ++commits;
        }
    }
    need(physical==T && commits==T && !d.owner_count,"S4_FAULT_FANOUT_NORMAL_DRAIN");
    ++c.cases;++c.normal_frames;c.normal_rows+=physical;
}
static void missing_first(DUT& d,Counts& c){
    reset(d);
    for(unsigned tick=0;tick<=POINTWISE;++tick){
        d.clk=0;drive_frame(d,tick);d.debug_drop_forward=1;d.eval();
        if(tick<POINTWISE)need(!d.fault_pending && !d.out_error,"S4_FAULT_FANOUT_MISSING_FIRST_TOO_EARLY");
        else need(d.fault_pending && !d.out_error && !d.monitor_quarantine && d.owner_count==1,
                  "S4_FAULT_FANOUT_ACTUAL_MISSING_FIRST_ORIGIN");
        d.clk=1;d.eval();replicas(d);
        need(bool(d.out_error)==(tick==POINTWISE),"S4_FAULT_FANOUT_MISSING_FIRST_REGISTERED_EDGE");
    }
    need(d.monitor_quarantine==3 && !d.commit_valid,"S4_FAULT_FANOUT_MISSING_FIRST_QUARANTINE");
    failed_tail(d);++c.cases;
}
static void legal_origin_tail(DUT& d,Counts& c){
    reset(d);
    for(unsigned tick=0;tick<=SINK;++tick){
        d.clk=0;drive_frame(d,tick);
        if(tick==SINK)d.frame_start=1; // genuine invalid orphan start; old sink is legal
        d.eval();
        if(tick==SINK){
            need(d.fault_pending && !d.out_error && d.monitor_protocol_commit && !d.monitor_quarantine,
                 "S4_FAULT_FANOUT_LEGAL_ORIGIN_COMMIT_PREDICATE");
        }else need(!d.fault_pending && !d.out_error,"S4_FAULT_FANOUT_TAIL_PRE_BASELINE");
        d.clk=1;d.eval();replicas(d);
        if(tick==SINK){
            need(d.out_error && d.monitor_original_fault && d.monitor_quarantine==3 && d.commit_valid,
                 "S4_FAULT_FANOUT_ACCEPTED_ORIGIN_TAIL_NOT_ROLLED_BACK");
            need(d.commit_epoch==0 && d.commit_generation==7 && d.commit_frame_start,
                 "S4_FAULT_FANOUT_ORIGIN_TAIL_TAG");
            for(unsigned word=0;word<WORDS;++word)need(d.commit_data[word]==0,"S4_FAULT_FANOUT_ORIGIN_TAIL_WORD");
            ++c.legal_origin_commits;
        }
    }
    failed_tail(d);++c.cases;
}
static void reset_pending(DUT& d,unsigned age,Counts& c){
    reset(d);
    for(unsigned tick=0;tick<age;++tick){d.clk=0;drive_frame(d,tick);d.eval();d.clk=1;d.eval();replicas(d);need(!d.out_error,"S4_FAULT_FANOUT_RESET_PRE_BASELINE");}
    // Assert between edges before the next accepting posedge. Previously
    // accepted commits remain accepted; reset revokes future validity only.
    d.clk=0;d.rst_n=0;clear(d);d.in_slot_valid=1;d.frame_start=1;d.correction_valid=1;d.eval();
    need(!d.frame_accept && !d.correction_accept && !d.out_slot_valid && !d.commit_valid && !d.monitor_quarantine,
         "S4_FAULT_FANOUT_ASYNC_RESET_REVOKES_VALIDITY");
    d.clk=1;d.eval();d.clk=0;d.rst_n=1;clear(d);d.eval();
    for(unsigned j=0;j<FIRST+T+8;++j){
        d.clk=0;clear(d);d.eval();d.clk=1;d.eval();replicas(d);
        need(!d.out_slot_valid && !d.commit_valid && !d.out_error && !d.owner_count,"S4_FAULT_FANOUT_RESET_LONG_STALE_TAIL");
    }
    ++c.cases;++c.reset_aborts;normal(d,c);
}
static void canceled_raw_tail(DUT& d,Counts& c){
    reset(d);unsigned physical=0;
    for(unsigned tick=0;tick<SINK+T+16;++tick){
        d.clk=0;drive_frame(d,tick);d.context_enabled=tick<SINK;d.eval();
        d.clk=1;d.eval();replicas(d);
        need(!d.out_error && !d.monitor_quarantine,"S4_FAULT_FANOUT_CANCEL_IS_NOT_MALFORMED");
        need(bool(d.out_slot_valid)==(tick>=FIRST && tick<FIRST+T),"S4_FAULT_FANOUT_CANCELED_RAW_TAIL_CALENDAR");
        need(!d.commit_valid,"S4_FAULT_FANOUT_CANCEL_COMMIT_REJECTION");
        if(d.out_slot_valid){
            need(bool(d.out_eligible)==(tick<SINK) && d.out_epoch==0 && d.generation_out==7,
                 "S4_FAULT_FANOUT_CANCELED_RAW_TAIL_TAG");++physical;
        }
    }
    need(physical==T && !d.owner_count,"S4_FAULT_FANOUT_CANCELED_RAW_DRAIN");
    ++c.cases;c.canceled_rows+=physical;
}
static void footer(const Counts& c){
    need(c.cases==9 && c.normal_frames==4 && c.normal_rows==4*T && c.legal_origin_commits==1 &&
         c.canceled_rows==T && c.reset_aborts==2,"S4_FAULT_FANOUT_FIXED_SCENARIO_COUNTS");
    std::cout<<"S4_FAULT_FANOUT_FAULT_PASS aw=8 p=8 field=2 cases=9 normal_frames=4 normal_rows="<<4*T
        <<" missing_first="<<POINTWISE<<" fault_origins=2 legal_origin_commits=1 reset_aborts=2 reset_ages=10,"<<FIRST+2
        <<" quiet_tail=16 canceled_rows="<<T<<" recovery_frames=3\n";
}
int main(int argc,char** argv){try{
    VerilatedContext context;context.threads(1);context.commandArgs(argc,argv);DUT d{&context};
    if(argc==2 && std::string(argv[1])=="--runtime-probe"){
        std::cout<<"{\"context_threads\":"<<context.threads()<<",\"model_threads\":"<<d.threads()<<",\"expected_threads\":1}\n";
        return context.threads()==1 && d.threads()==1?0:2;
    }
    const bool negative=argc==2 && std::string(argv[1])=="--negative-replica-origin";
    need(argc==1 || negative,"S4_FAULT_FANOUT_ARGUMENTS");
    Counts c;normal(d,c);missing_first(d,c);legal_origin_tail(d,c);
    reset_pending(d,10,c);reset_pending(d,FIRST+2,c);canceled_raw_tail(d,c);normal(d,c);footer(c);
    if(negative){
        reset(d);d.in_slot_valid=1;d.frame_start=1;d.data_in[0]=d.base_in;d.debug_mask_replica_set=1;d.eval();
        need(d.fault_pending && !d.out_error,"S4_FAULT_FANOUT_NEGATIVE_BASELINE_ORIGIN");d.clk=1;d.eval();
        need(d.out_error && !d.monitor_quarantine,"S4_FAULT_FANOUT_NEGATIVE_REAL_SETTER_MUTATION");
        d.final();std::cerr<<"S4_FAULT_FANOUT_TYPED_REPLICA_ORIGIN expected=3 actual=0\n";return 41;
    }
    d.final();return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
