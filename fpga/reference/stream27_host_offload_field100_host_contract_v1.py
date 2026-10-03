"""Private R14-F source/scalar host-ABI reuse guard, not native qualification.

Reads frozen FIELD100 captures only. No compiler, NTT, full-size digit array,
benchmark, cloud operation or inherited chip-equivalence result is executed.
"""
import hashlib
import json
from pathlib import Path
import re

from fpga.reference import stream27_host_offload_host_v2 as host
from fpga.reference import stream27_host_offload_model_v1 as frozen

ROOT=Path(__file__).resolve().parents[1]
HEADER='rtl/tb/stream27_host_offload_host_v2.h'
HEADER_PIN='7679e85713662635476124b0bad2e91954a08d8a27dd3f25db127b23da9d0720'
PARENTS={256:('aw8-normal','dd8d9196a5ac79381b8e701d021d19a067dde4d319b15799b13f8d8f61441a00'),
         65536:('full-normal-v2','f5f0617d989b64bb965b612a0d0cb8b6074c1ecd4f85f01ed66f970dfbf521f2')}
BASE=ROOT/'results/throughput-20260929/trackS-c2-protected-field100-native-v1'
PRIMES=(104857601,69206017,67239937)
SETUP='genefer_stream27_blockcarry_setup_param_v1.sv'
SETUP_PIN='c9ba8163c8bb43afecf1afee07a8a55c4eb89539318cf235b83508ab692f4f26'
CHIP='reference/stream27_host_offload_field100_v1.py'
CHIP_PIN='6a9920ca2b704145553ed9f5fc13d0e6f97de78b0f89a960801bf7919b184633'
LEAF='rtl/kernel/genefer_stream27_host_offload_ingress_field100_v1.sv'
LEAF_PIN='c2d3e209fe13b988b38667781d0691f0b1944b643366d563bf86477307e451bc'


def need(ok,why):
    if not ok:raise ValueError('R14_F_HOST_CONTRACT_'+why)


def sha(raw):return hashlib.sha256(raw.encode() if isinstance(raw,str) else raw).hexdigest()


def captured(n):
    need(n in PARENTS,'N256_FULL_ONLY')
    directory,pin=PARENTS[n];raw=(BASE/directory/'production-bundle.json').read_bytes()
    need(sha(raw)==pin,'FROZEN_FIELD100_CAPTURE')
    bundle=json.loads(raw)
    need(len(bundle['files'])==58 and all(sha(text)==bundle['generated_sha256'][name]
         for name,text in bundle['files'].items()),'FIELD100_SOURCE_BYTES')
    return bundle


def field_domain(bundle,offload=False):
    n=bundle['geometry']['n'];need(n in PARENTS and bundle['geometry']['p']==16,'GEOMETRY')
    fields=[(name,text) for name,text in bundle['files'].items()
            if name.startswith('genefer_stream27_shared_warm_aw') and
               (not offload or 'off_cold_slot' in text)]
    need(len(fields)==3,'THREE_ORDINARY_FIELDS')
    for name,text in fields:
        match=re.search(r'_f([0-2])_',name);need(match is not None,'FIELD_INDEX')
        prime=PRIMES[int(match.group(1))]
        need(f".P(32'd{prime})" in text and
             f"if(digit_base<32'd{host.minimum_base(n,16)}" in text and
             f"32'd{2*n+384}" in text,'PRIME_BASE_AND_K')
        for lane in range(16):
            reverse=sum(((lane>>bit)&1)<<(3-bit) for bit in range(4))
            need(f'ordered_c0[{32*lane}+:32]=c0_in[{32*reverse}+:32]' in text and
                 f'ordered_high[{32*lane}+:32]=high_correction[{32*reverse}+:32]' in text,
                 'EXACT_NATURAL_CORRECTION_REVERSE4')
    need(sha(bundle['files'][SETUP])==SETUP_PIN,'SAME_R96_A77_SETUP')
    return n


def new_chip_source():
    need(sha((ROOT/CHIP).read_bytes())==CHIP_PIN and sha((ROOT/LEAF).read_bytes())==LEAF_PIN,
         'FROZEN_NEW_R14_F_SOURCE')
    from fpga.reference import stream27_host_offload_field100_v1 as chip
    old=(ROOT/'rtl/kernel/genefer_stream27_host_offload_ingress_v1.sv').read_text()
    new=(ROOT/LEAF).read_text();authority=' always_ff @(posedge clk or negedge rst_n)'
    need(old[old.index(authority):]==new[new.index(authority):],
         'SAME_OWNER_PROFILE_ATOMIC_RESET_AUTHORITY')
    need('image[{context_in,RW\'(row_index)}]<=word_data[26:0]' in new and
         'read_q<=image[{row_context,row_address}]' in new and
         "row_data[(f*P+lane)*32+:32]={5'd0,read_q}" in new,
         'SAME_COLD_WORD_MAPPING_ONE_EDGE_RAM')
    for n in PARENTS:
        parent=captured(n);disabled=chip.prepare(n,host_offload=0)
        need(disabled==parent,'F_OFF_LITERAL_FIELD100')
        enabled=chip.prepare(n,host_offload=1);field_domain(enabled,offload=True)
        need(enabled['parameters']==dict(parent['parameters'],HOST_OFFLOAD=1),
             'F_ON_NO_ADDED_RELAY_OR_ARITHMETIC_PROFILE')
        need(all(enabled['files'][name]==text for name,text in parent['files'].items()),
             'F_PARENT58_RETAINED')
        top='\n'.join(text for text in enabled['files'].values() if 'off_source_planes' in text)
        need('assign off_raw_owner=final_owner' in top and 'assign off_raw_data=digit_data' in top and
             'assign off_c0=next_c0;assign off_c1=next_c1' in top and
             "{19'd0,coefficient_limit}==off_expected_limit" in '\n'.join(enabled['files'].values()),
             'SAME_RAW_NATURAL_CARRY_OWNER_AND_EXACT_PROFILE')
    return dict(compiler=CHIP,compiler_sha256=CHIP_PIN,leaf=LEAF,leaf_sha256=LEAF_PIN,
                literal_FIELD100_OFF=True,cold_RAM_response_edges=1,host_ABI_changed=False)


def verify():
    header=(ROOT/HEADER).read_bytes();need(sha(header)==HEADER_PIN,'FROZEN_C_ABI')
    text=header.decode()
    need(not any(key in text for key in ('INTERVAL','FIRST_DIGIT','CARRY_DONE',
         'INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG','FORWARD_INGRESS_REG')),
         'C_API_HAS_NO_CLOCK_OR_RELAY_DEPENDENCE')
    rows=[];profiles=0
    for n in PARENTS:
        bundle=captured(n);field_domain(bundle)
        need(not any(bundle['parameters'].get(key,0) for key in
             ('INVERSE_INGRESS_REG','TERM_JOIN_TRANSPORT_REG','FORWARD_INGRESS_REG')),
             'LITERAL_FIELD100_RELAY_OFF')
        for base in (host.minimum_base(n,16),604832956,999999937,1000000000):
            for generation in (0,255):
                need(host.profile_make(n,base,generation)==frozen.profile_payload_bytes(
                     frozen.profile(n,16,base,generation)),'EXACT_SCALAR_PROFILE_WORDS')
                profiles+=1
        rows.append(dict(n=n,p=16,rows=n//16,min_base=host.minimum_base(n,16),K=2*n+384,
            cold_words=3*n+96,raw_words=n+32,canonical_words=n,profile_words=8,
            field100_interval=bundle['geometry']['warm_interval'],
            first_digit=bundle['geometry']['first_digit'],carry_done=bundle['geometry']['carry_done']))
    return dict(status='PASS_source_scalar_host_ABI_reuse_only',header=HEADER,header_sha256=HEADER_PIN,
        new_chip_source=new_chip_source(),
        scalar_profiles=profiles,geometry=rows,high_correction_unscaled=True,
        context_bits=1,owner_bits=56,ordinal_bits=32,epoch_bits=16,generation_bits=8,
        host_code_changed=False,new_native_or_benchmark_run=False,
        old_R14_chip_evidence_inherited=False,new_R14_F_native_required=True,
        transport_or_GL_implemented=False,promotion_allowed=False)


if __name__=='__main__':print(json.dumps(verify(),indent=2))
