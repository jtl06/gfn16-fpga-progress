"""Exact host-ABI successor of the frozen soak loop, with A-next diagnostics."""
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PARENT='rtl/tb/core27_t5b_soak_v1.cpp'
PIN='c4972670a55bbb0c7b039e7a0175ee6918e5a95f3e0dd4a5a96c7dbc7175fab7'
CHILD='rtl/tb/anext_soak_v1.cpp'
def once(t,a,b):
    if t.count(a)!=1:raise ValueError('single soak ABI anchor '+a[:90])
    return t.replace(a,b)
def expected():
    raw=(ROOT/PARENT).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('frozen soak harness identity')
    t=raw.decode().replace('genefer_square_core27_stream_prefetch_r2_host_broadcast_orient8_rootfused_crtmont_prefill_pipe_v1','genefer_anext_core_v1')
    t=t.replace('// Additive T5b E2E-2 driver: same frozen host loop, separately pinned model.','// A-next command-host soak: same donor checkpoint protocol, distinct cycle/ABI contract.')
    a=t.index('using I = __int128_t;');b=t.index('struct Check')
    t=t[:a]+'''static void require(bool ok, const std::string& message) {
    if (!ok) throw std::runtime_error(message);
}
'''+t[b:]
    t=once(t,'&& base >= 2*n+5 && base <= 1000000000','&& base >= std::max(2*n+5,(2*(2*n+384)+2)/3+1) && base <= 1000000000')
    a=t.index('        auto idle =');b=t.index('        unsigned readbacks = 0;')
    t=t[:a]+'''        d.cmd_valid=0;d.rsp_ready=0;d.cmd_opcode=0;d.cmd_address=0;
        d.cmd_word=0;d.cmd_base=base;d.cmd_double=0;
        auto command=[&](unsigned opcode,unsigned address,int32_t word,bool bit){
            require(d.cmd_ready && !d.rsp_valid,"SOAK_COMMAND_READY");
            d.cmd_opcode=opcode;d.cmd_address=address;d.cmd_word=word;
            d.cmd_base=base;d.cmd_double=bit;d.cmd_valid=1;tick();d.cmd_valid=0;
            uint64_t waited=0;while(!d.rsp_valid && waited<65536+uint64_t(64)*n){
                require(!d.cmd_ready,"SOAK_COMMAND_BACKPRESSURE");tick();++waited;
            }
            require(d.rsp_valid && !d.rsp_error && !d.fault_sticky && d.rsp_opcode==opcode,"SOAK_COMMAND_RESPONSE");
            if(opcode==5)require(waited==d.square_cycles+2,"SOAK_COMMAND_CYCLE_ALIGNMENT");
            const int32_t result=int32_t(d.rsp_word);const auto generation=d.rsp_generation;
            tick();require(d.rsp_valid && d.rsp_generation==generation && int32_t(d.rsp_word)==result && !d.rsp_error,"SOAK_RESPONSE_HOLD");
            d.rsp_ready=1;tick();d.rsp_ready=0;return result;
        };
        d.rst_n=0;tick();d.rst_n=1;tick();
        require(!d.busy && !d.rsp_valid && !d.image_valid && !d.prefill_valid,"SOAK_RESET");
        command(0,0,0,false);
        for(unsigned i=0;i<n;++i){
            auto value=checks.front().digits[i];
            if(negative_load && i==0)value=value==-1?0:(value+1)%base;
            command(1,i,int32_t(value),false);
        }
'''+t[b:]
    a=t.index('            require(!d.busy && !d.error,');b=t.index('            canonical(actual, base);')
    t=t[:a]+'''            require(!d.busy && !d.fault_sticky,"SOAK_READBACK_IDLE");
            std::vector<int64_t> actual(n);
            for(unsigned i=0;i<n;++i){
                const int32_t value=command(2,i,0,false);
                require(value>=-1 && int64_t(value)<int64_t(base),"SOAK_READ_DIGIT_RANGE");
                actual[i]=value;
            }
            require(!d.prefill_valid,"SOAK_CANONICAL_READ_INVALIDATES_PREFILL");
'''+t[b:]
    t=t.replace('"SOAK_CHECK {','"ANEXT_SOAK_CHECK {')
    t=once(t,'unsigned next_check = 1, doubles = 0;','unsigned next_check = 1, doubles = 0, cold_prefill = 0;')
    t=once(t,'        const uint64_t timeout_cycles = 65536+uint64_t(64)*n;\n','')
    a=t.index('            d.base = base;');b=t.index('            total_cycles += elapsed;',a)
    t=t[:a]+'''            const bool cold=!d.prefill_valid;
            command(5,0,0,bits[k]=='1');
            const uint64_t elapsed=d.square_cycles;
            const uint64_t groups=std::max(uint64_t(1),uint64_t(n)/128);
            const uint64_t expected_ntt=2*uint64_t(aw)*(groups+9)+std::max(uint64_t(1),uint64_t(n)/64)+13;
            const uint64_t expected_post=n/16+62;
            const uint64_t expected_prefill=cold?n/16+10:0;
            const uint64_t expected_control=cold?7:5;
            require(d.image_valid && d.prefill_valid && d.profile_loads==(k==0) && d.profile_hits==(k!=0),"SOAK_PERSISTENT_PROFILE_CACHE");
            require(d.ntt_cycles==expected_ntt && d.post_cycles==expected_post && d.prefill_cycles==expected_prefill && d.root_cycles==(k==0?9u:0u) && d.seed_setup_cycles==0,"SOAK_ANEXT_PHASES");
            require(elapsed==d.prefill_cycles+d.root_cycles+d.ntt_cycles+d.post_cycles+expected_control,"SOAK_ANEXT_ACCOUNTING");
            const unsigned step=start+k+1;cold_prefill+=cold;
            std::cout << "ANEXT_SOAK_STEP {\\"case_id\\":\\"" << case_id << "\\",\\"step\\":" << step
                << ",\\"bit\\":" << (bits[k]=='1') << ",\\"cycles\\":" << elapsed
                << ",\\"prefill\\":" << d.prefill_cycles << ",\\"roots\\":" << d.root_cycles
                << ",\\"ntt\\":" << d.ntt_cycles << ",\\"post\\":" << d.post_cycles << ",\\"control\\":" << expected_control
                << ",\\"profile_loads\\":" << unsigned(d.profile_loads) << ",\\"profile_hits\\":" << unsigned(d.profile_hits) << "}\\n";
'''+t[b:]
    t=once(t,'// No reset or host reload between operations. Readbacks preserve\n            // controller/cache state; the uninterrupted gate uses this loop.','// No reset/reload between operations. Canonical readback preserves\n            // roots and digit image, but invalidates field prefill by contract.')
    t=t.replace('"SOAK_PASS {','"ANEXT_SOAK_PASS {')
    t=once(t,'<< ",\\"cold\\":1,\\"warm\\":" << bits.size()-1 << "}\\n";','<< ",\\"cold_prefill\\":" << cold_prefill << ",\\"warm_prefill\\":" << bits.size()-cold_prefill\n            << ",\\"cache_cold\\":1,\\"cache_warm\\":" << bits.size()-1 << "}\\n";')
    return t
def verify():
    if (ROOT/CHILD).read_text()!=expected():raise ValueError('uncontrolled soak command ABI delta')
    return dict(source_only=True,donor_numeric_protocol_unchanged=True,canonical_read_invalidates_prefill=True,native_pass=False)
