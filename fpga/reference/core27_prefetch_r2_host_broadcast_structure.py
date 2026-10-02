"""Local-only host-payload broadcast candidate and reproducible source proof.

The mask, not a zero payload, controls whether a bank writes. Repeating the
16 host words across four quarters removes payload-zero selection and makes
the upper two 64-lane XOR payload-routing stages identities. All six mask
stages remain necessary. Nominal 32-bit selections exposed for deletion:
64*32 + 2*64*32 = 6144 per field (18432 for three fields). These are NOT ALMs,
measured savings, timing, power, or physical-fit claims; synthesis may already
factor some logic. Broadcasting can increase inactive-net toggling.

Only the new wrapper is a candidate. The frozen child/core are unchanged;
no HDL simulation, integrated candidate, or physical validation is implied.
Future measurement must include the host wrapper, not the raw child probe.
"""
import hashlib
import json
from pathlib import Path

ANCESTOR='genefer_ntt_banked27_prefetch_r2_host_engine'
CANDIDATE='genefer_ntt_banked27_prefetch_r2_host_broadcast_engine'
ANCESTOR_SHA='b0fc9014b73eac3a989ce416b15e8c802a2a2fe54922af3c77489237679e0302'
CHILD='genefer_ntt_banked27_prefetch_r2_engine'
CHILD_SHA='552d273972af97c3363b77df0798e08a962d283869bcc95159f378a0f0070b17'
OLD="assign child_write_data[h*32+:32]=host_group==GW'(h/HOST_LANES) ? vector_write_data[(h%HOST_LANES)*32+:32] : 32'd0;"
NEW='assign child_write_data[h*32+:32]=vector_write_data[(h%HOST_LANES)*32+:32];'


def require(value,message):
    if not value:raise ValueError(message)


def sha(text):return hashlib.sha256(text.encode()).hexdigest()


def transform(original):
    require(sha(original)==ANCESTOR_SHA,'frozen host ancestor identity')
    declaration='module '+ANCESTOR+' #('
    require(original.count(declaration)==1 and original.count(OLD)==1,'ambiguous source delta')
    return original.replace(declaration,'module '+CANDIDATE+' #(').replace(OLD,NEW)


def validate_files(root):
    rtl=Path(root)/'rtl/kernel'
    original=(rtl/(ANCESTOR+'.sv')).read_text();candidate=(rtl/(CANDIDATE+'.sv')).read_text()
    require(candidate==transform(original),'candidate has an unreviewed delta')
    require(sha((rtl/(CHILD+'.sv')).read_text())==CHILD_SHA,'frozen child routing identity')
    return {str(Path('rtl/kernel')/(CANDIDATE+'.sv')):sha(candidate)}


def xor_route(values,bank_xor):
    """Literal six-stage butterfly permutation; works on symbolic payloads."""
    require(len(values)==64 and 0<=bank_xor<128,'route geometry')
    result=list(values)
    for bit in range(6):
        previous=result
        result=[previous[h^(1<<bit)] if (bank_xor>>bit)&1 else previous[h] for h in range(64)]
    return result


def bank_of(address,aw):
    require(1<=aw<=16 and 0<=address<1<<aw,'address domain')
    bank=0
    for bit in range(aw):bank^=((address>>bit)&1)<<(bit%7)
    return bank


def writes(words,mask,quarter,bank_xor,n=65536,child_addr=0,broadcast=False):
    """Combinational accepted-host-write footprint, not an HDL simulation.

    Indexes are physical banks; None means no write, independent of the
    inactive payload. Valid descriptors/start/profile/busy priority remain
    outside this accepted-write function and unchanged by the source proof.
    All 32 payload bits are preserved, including noncanonical poison values.
    """
    require(len(words)==16 and all(type(w) is int and 0<=w<1<<32 for w in words),'full32 payload domain')
    require(0<=mask<1<<16 and 0<=quarter<4 and 0<=bank_xor<128,'mask/quarter/bank domain')
    require(n>=2 and n&(n-1)==0 and n<=65536 and 0<=child_addr<n and child_addr%64==0,'valid child range')
    expanded=[words[h%16] if broadcast or h//16==quarter else 0 for h in range(64)]
    active=[h//16==quarter and bool(mask&(1<<(h%16))) and child_addr+h<n for h in range(64)]
    payload=xor_route(expanded,bank_xor);enabled=xor_route(active,bank_xor)
    return [payload[b%64] if b//64==bank_xor//64 and enabled[b%64] else None for b in range(128)]


def exhaustive_proof():
    """All 128 bank XORs x four host quarters x 64 physical half lanes."""
    checks=0;words=[0xf0000000+i*0x10101 for i in range(16)]
    for bank_xor in range(128):
        for quarter in range(4):
            baseline=writes(words,0xffff,quarter,bank_xor)
            candidate=writes(words,0xffff,quarter,bank_xor,broadcast=True)
            require(baseline==candidate,'enabled-write mismatch')
            for lane in range(64):
                source=lane^(bank_xor&63)
                selected=source//16==quarter
                bank=(bank_xor&64)+lane
                require((candidate[bank] is not None)==selected,'routed-mask mismatch')
                if selected:require(candidate[bank]==words[source%16],'routed payload mismatch')
                checks+=1
    return dict(status='source_and_symbolic_only',comparisons=checks,
        nominal_payload_selections_per_field=6144,nominal_payload_selections_three_fields=18432,
        latency_change=0,payload_bits=32,
        limitation='No RTL simulation, integrated core, physical resource saving, clock, power or throughput claim.')


if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    print(json.dumps(dict(sources=validate_files(root),proof=exhaustive_proof()),indent=2))
