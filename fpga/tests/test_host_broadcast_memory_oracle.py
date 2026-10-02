"""Independent schedule arithmetic checks; no RTL, runner, or result imports."""
import hashlib
from pathlib import Path
import struct
import unittest

from fpga.reference import host_broadcast_memory_oracle as o


def bitwise_random(state):
    bits=[(state>>i)&1 for i in range(32)]
    for shift in (13,-17,5):
        original=bits
        bits=[original[i]^(original[i-shift] if 0<=i-shift<32 else 0) for i in range(32)]
    return sum(bit<<i for i,bit in enumerate(bits))


def arithmetic_counts(aw):
    """Second count-only calculation: closed-form fixed phases plus PRNG flags.

    No flat-memory engine, transaction methods, or hash trace are reused.
    PRNG here operates on individual bits instead of Python word shifts.
    """
    n=1<<aw;rows=(n+15)//16;active=min(n,16);masks=(0,1,0x8000,0x8001,0x5555,0xaaaa,0xffff)
    directed=rows*sum((m&((1<<active)-1)).bit_count() for m in masks)
    runtime=2*sum(min(16,1<<lg) for lg in range(1,aw+1))
    result=dict(edges=8*n+rows*7*(2+int(n>16))+4*aw+1239+int(aw>=5),
        read_words=13*n+(rows*7 if n>16 else 0)+runtime,
        written_words=2*n+directed+runtime,vector_reads=rows*7+2*aw,vector_writes=rows*7+2*aw,
        masked_poison=rows*7*16-directed+32*aw-runtime,
        clipped=rows*sum((m>>active).bit_count() for m in masks)+32*aw-runtime,
        descriptor_errors=4+int(aw>=5),profile_checks=6,busy_checks=2,
        quarters=(1<<min(4,rows))-1,halves=1 if n<=64 else 3)
    state=0x91bb27+aw
    for round_number in range(1200):
        draw=[]
        for _ in range(25):state=bitwise_random(state);draw.append(state)
        size=(0,1,aw,aw+1,min(4,aw))[draw[0]%5]
        address=draw[2]%n
        if round_number%2:address&=~15
        extent=(1<<size) if 1<=size<=aw else 0
        scalar_write,scalar_read,vector_write,vector_read=(bool(x&1) for x in draw[3:7])
        mask=draw[8]&65535;request=vector_write or vector_read
        valid=bool(extent and address%16==0 and address<extent)
        width=max(0,min(16,extent-address));used=(mask&((1<<width)-1)).bit_count()
        if request:
            if not valid:result['descriptor_errors']+=1
            elif vector_write:
                result['vector_writes']+=1;result['written_words']+=used
                result['clipped']+=(mask>>width).bit_count()
            elif vector_read:result['vector_reads']+=1;result['read_words']+=used
        elif scalar_write:result['written_words']+=1
        elif scalar_read:result['read_words']+=1
    return result,state


class HostBroadcastOracleTests(unittest.TestCase):
    def test_exact_bench_pin_no_source_changes(self):
        o.verify_bench_source(Path(__file__).resolve().parents[1]/'rtl/tb/host_broadcast_memory_pair.cpp')

    def test_uint32_rng_against_independent_bits(self):
        self.assertEqual(o.xorshift32(1),270369)
        for start in (0,1,0xffffffff,0x91bb28,0x91bb2c,0x91bb2f,0x91bb37):
            a=b=start
            for _ in range(100):a=o.xorshift32(a);b=bitwise_random(b);self.assertEqual(a,b)

    def test_clear_preserves_nonstrobes_and_addresses_truncate(self):
        model=o.MemorySchedule(1,1)
        model.set(host_addr=3,vector_addr=16,size_log2=33,vector_lane_mask=0x10001,write_data=0xdeadbeef,load_we=1)
        model.clear()
        self.assertEqual((model.s['host_addr'],model.s['vector_addr'],model.s['size_log2'],model.s['vector_lane_mask']),(1,0,1,1))
        self.assertEqual(model.s['write_data'],0xdeadbeef)
        self.assertTrue(all(model.s[k]==0 for k in o.STROBES))

    def test_invalid_size_does_not_disable_scalar_but_vector_suppresses_scalar(self):
        m=o.MemorySchedule(5,1);m.set(size_log2=0,load_we=1,host_addr=1,write_data=7);m.ordinary()
        self.assertEqual(m.memory[1],7)
        m.set(vector_load_we=1,vector_addr=0,write_data=0xffffffff);m.ordinary()
        self.assertEqual(m.memory[1],7);self.assertEqual(m.count['descriptor_errors'],1)

    def test_uninitialized_reads_fail_and_reset_does_not_invent_zeros(self):
        m=o.MemorySchedule(5,1);m.set(read_en=1)
        with self.assertRaises(ValueError):m.ordinary()
        m.clear();m.set(load_we=1,host_addr=0,write_data=3);m.ordinary();m.reset()
        m.set(read_en=1)
        with self.assertRaises(ValueError):m.ordinary()

    def test_masked_poison_clipping_and_initialized_read_mask(self):
        m=o.MemorySchedule(5,1);m.set(size_log2=1,vector_load_we=1,vector_lane_mask=0xffff,
            vector_write_data=[5,6]+[0xffffffff]*14);m.ordinary()
        self.assertEqual(m.count['written_words'],2);self.assertEqual(m.count['masked_poison'],14)
        self.assertEqual(m.count['clipped'],14)
        m.clear();m.set(vector_read_en=1);m.ordinary();self.assertEqual(m.count['read_words'],2)

    def test_AW1_5_8_all_fields_count_invariance_and_second_oracle(self):
        for aw in (1,5,8):
            expected,state=arithmetic_counts(aw);traces=[]
            for field,p in o.FIELDS.items():
                result=o.expected_result(aw,field)
                self.assertEqual(result['counts'],dict(aw=aw,p=p,**expected))
                self.assertEqual(result['prng_final_state'],state);self.assertEqual(result['prng_calls'],30000)
                self.assertEqual(result['schedule_events']['fuzz'],1200)
                self.assertEqual(result['schedule_events']['scan'],6*(1<<aw))
                self.assertEqual(result['final_memory_sha256'],hashlib.sha256(b''.join(struct.pack('<I',
                    (i*2654435761+0x56789)%p) for i in range(1<<aw))).hexdigest())
                traces.append(result['trace_sha256'])
            self.assertEqual(len(set(traces)),3)

    def test_full_AW16_P1_against_second_oracle(self):
        result=o.expected_result(16,1);counts,state=arithmetic_counts(16)
        self.assertEqual(result['counts'],dict(aw=16,p=o.FIELDS[1],**counts))
        self.assertEqual(result['prng_final_state'],state)
        self.assertEqual(result['schedule_events']['scan'],6*65536)
        self.assertEqual(result['schedule_events']['directed_write'],4096*7)

    def test_footer_is_exact_order_and_scope_not_observed(self):
        result=o.expected_result(1)
        self.assertEqual(o.canonical_footer(result),
            'PASS host_broadcast_memory_pair aw=1 p=104857601 edges=1273 read_words=225 written_words=403 vector_reads=143 vector_writes=265 masked_poison=134 clipped=1797 descriptor_errors=526 profile_checks=6 busy_checks=2 quarters=1 halves=1')
        self.assertIn('no RTL execution',result['scope'])


if __name__=='__main__':unittest.main()
