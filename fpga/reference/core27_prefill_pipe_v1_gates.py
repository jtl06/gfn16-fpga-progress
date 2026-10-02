"""Additive T5b observers/harnesses, derived from pinned T5 gates; source only."""
import hashlib
from pathlib import Path
from .core27_prefill_pipe_v1_structure import ROOT, CORE, PARENT, generate, once

PINS = {
 'rtl/tb/core27_prefill_probe_v3.sv':'37d050be4529614203b9520eecb52a3b69c2d34bf9db1ec3997c69930720d922',
 'rtl/tb/core27_prefill_tail_probe_v3.sv':'88e0b95c015773011fbee44359ad7fcd5e7679910d5457315a8908b7b96bb238',
 'rtl/tb/core27_prefill_normal_v3.cpp':'b95f54c977fb73e97e6d70a09307a37ef7d75b17d3aff04dc5a5c09d4047f791',
 'rtl/tb/core27_prefill_normal_v3_threaded.cpp':'a3e95e1d0de659bcdba1f3e35c268299689bee2d53002285d3b7ef9a36e59a5c',
 'rtl/tb/core27_prefill_adversarial_v1.cpp':'14661ac736180b91247cea4552d2d88cc608b67ba6cad849c2e4d690f4c15478',
}
NORMAL = 'core27_prefill_pipe_probe_v1'
TAIL = 'core27_prefill_pipe_tail_probe_v1'
BRIDGE = 'core27_prefill_pipe_fault_bridge_v1'


def pinned(root, name):
    raw=(Path(root)/name).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PINS[name]: raise ValueError('gate ancestor drift: '+name)
    return raw.decode()


def observer(text):
    # This history starts at the ACTUAL carry RAM commit, never a candidate FF.
    text=once(text,'logic [4:0] observed_valid;', 'logic [7:0] observed_valid;')
    text=text.replace('observed_addr[0:4]', 'observed_addr[0:7]').replace('observed_data[0:4]', 'observed_data[0:7]')
    text=once(text,'uses five clock delays', 'uses eight clock delays')
    text=once(text,'observed_valid[3:0],source_commit_valid','observed_valid[6:0],source_commit_valid')
    text=once(text,'d<5;d=d+1','d<8;d=d+1')
    text=text.replace('observed_valid[4]','observed_valid[7]').replace('observed_addr[4]','observed_addr[7]').replace('observed_data[4]','observed_data[7]')
    text=once(text,'if(dut.state==CORE_CARRY_WAIT && !dut.core_fault && !dut.prefill_fault)begin',
        'if(dut.state==CORE_CARRY_WAIT)begin')
    text=once(text,'    logic tail_host_error;', '    logic tail_host_error,quarantined;')
    text=once(text,'image_base<=0;operation_base<=0;tail_host_error<=0;',
        'image_base<=0;operation_base<=0;tail_host_error<=0;quarantined<=0;')
    text=once(text,'        end else begin\n            if((dut.state==CORE_CARRY_WAIT',
        '''        end else begin
            // Fault-edge writes, if any, still MUST match the independent old
            // committed-row history below. No writes survive the flush edge.
            if(quarantined)begin
                if(dut.ntt_prefilled || actual_we[0]!=0 || actual_we[1]!=0 || actual_we[2]!=0)
                    $fatal(1,"T5B_MONITOR_QUARANTINE_WRITE");
            end
            if((dut.state==CORE_CARRY_WAIT || dut.state==CORE_PREFILL_CHECK) &&
               (dut.core_fault || dut.prefill_fault))quarantined<=1;
            if((dut.state==CORE_CARRY_WAIT''')
    return text


def bridge(text):
    for a,b in (
      ('module '+CORE+' #(', 'module '+BRIDGE+' #('),
      ('input logic clk, rst_n, load_we, read_en, start,',
       'input logic clk, rst_n, load_we, read_en, start,\n    input logic [2:0] sim_host_error,\n    input logic sim_carry_error,'),
      ('logic carry_load,carry_read,carry_start,carry_valid,carry_busy,carry_done,carry_error;',
       'logic carry_load,carry_read,carry_start,carry_valid,carry_busy,carry_done,carry_error;\n    logic native_carry_error;\n    assign carry_error=native_carry_error | sim_carry_error;'),
      ('logic [2:0] ntt_host_error,ntt_scalar_valid;',
       'logic [2:0] ntt_host_error,ntt_scalar_valid;\n    logic [2:0] native_ntt_host_error;\n    assign ntt_host_error=native_ntt_host_error | sim_host_error;'),
      ('.host_error(ntt_host_error[f])','.host_error(native_ntt_host_error[f])'),
      ('.error(carry_error)','.error(native_carry_error)')):
        text=once(text,a,b)
    return '// Simulation-only fault bridge. Never a physical top.\n'+text


def sources(root=ROOT):
    out={}
    for ancestor,top,child in [('core27_prefill_probe_v3',NORMAL,CORE),('core27_prefill_tail_probe_v3',TAIL,BRIDGE)]:
        text=observer(pinned(root,'rtl/tb/'+ancestor+'.sv'))
        text=once(text,'module '+ancestor+' #(', 'module '+top+' #(')
        text=once(text,(PARENT if top==NORMAL else 'core27_prefill_fault_bridge')+' #(',child+' #(')
        out['rtl/tb/'+top+'.sv']=text
    out['rtl/tb/'+BRIDGE+'.sv']=bridge(generate(root))
    text=pinned(root,'rtl/tb/core27_prefill_normal_v3.cpp').replace('core27_prefill_probe_v3',NORMAL)
    text=once(text,'uint64_t((n+15)/16)+6','uint64_t((n+15)/16)+9')
    text=text.replace('ceil(N/16)+6 clocks.','ceil(N/16)+9 clocks.')
    # The abort point follows the final conversion write, rather than stopping
    # three cycles early after the pipeline extension.
    text=once(text,'(n+15)/16+6','(n+15)/16+9')
    out['rtl/tb/core27_prefill_pipe_normal_v1.cpp']=text
    text=pinned(root,'rtl/tb/core27_prefill_normal_v3_threaded.cpp')
    text=text.replace('core27_prefill_probe_v3',NORMAL).replace('core27_prefill_normal_v3.cpp','core27_prefill_pipe_normal_v1.cpp')
    out['rtl/tb/core27_prefill_pipe_normal_threaded_v1.cpp']=text
    text=pinned(root,'rtl/tb/core27_prefill_adversarial_v1.cpp').replace('core27_prefill_tail_probe_v3',TAIL)
    text=text.replace("argv[3][0]<='6'", "argv[3][0]<='9'").replace('tail age 0..6 required','tail age 0..9 required')
    text=once(text,'d.conversion_cycles==(fast?0:8)','d.conversion_cycles==(fast?0:11)')
    out['rtl/tb/core27_prefill_pipe_tail_v1.cpp']=text
    return out


def validate(root=ROOT):
    out=sources(root)
    for name,text in out.items():
        if (Path(root)/name).read_text()!=text: raise ValueError('T5b gate derivation: '+name)
    return {name:hashlib.sha256(text.encode()).hexdigest() for name,text in out.items()}


if __name__=='__main__':
    import argparse,json
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--emit-patch',action='store_true')
    args=parser.parse_args()
    if args.emit_patch:
        items=sources()
        if any((ROOT/name).exists() for name in items): raise ValueError('fresh gates required')
        print('*** Begin Patch')
        for name,text in items.items():
            print('*** Add File: '+str(ROOT/name))
            for line in text.splitlines():print('+'+line)
        print('*** End Patch')
    else:print(json.dumps(validate(),indent=2))
