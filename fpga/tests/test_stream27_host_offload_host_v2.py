import struct
import unittest

from fpga.reference import stream27_host_offload_host_v2 as host
from fpga.reference import stream27_host_offload_model_v1 as frozen
from fpga.reference.stream27_canonical_image_model_v1 import independent_integer_oracle


class HostWire(unittest.TestCase):
    def test_profile_exact_and_reserved_widths(self):
        for n in (32,256,65536):
            for base in (host.minimum_base(n,16),1000000000):
                for gen in (0,7,255):
                    expected=frozen.profile_payload_bytes(frozen.profile(n,16,base,gen))
                    self.assertEqual(host.profile_make(n,base,gen),expected)
                    self.assertEqual(host.profile_validate(n,expected),(base,gen))
                    bad=bytearray(expected);bad[31]^=0x80
                    with self.assertRaisesRegex(host.HostError,'EXACT_PROFILE'):host.profile_validate(n,bytes(bad))

    def test_cold_all_bytes_match_frozen_spec(self):
        for n in (32,256):
            for base in (host.minimum_base(n,16),1000000000):
                for context in (0,1):
                    digits=[(j*j+73*j+5)%base for j in range(n)];digits[n//3]=-1
                    k=2*n+384;c0=[(-1 if j&1 else 1)*(base-1) for j in range(16)]
                    c1=[(-1 if j&1 else 1)*k for j in range(16)]
                    profile=host.profile_make(n,base,7);owner=(65535<<8)|7
                    actual=host.cold_write(n,profile,context,owner,host.pack32(digits),host.pack32(c0+c1),
                        expected_context=context,expected_owner=owner)
                    packet=frozen.prepare_cold(digits,c0,c1,frozen.profile(n,16,base,7),context=context,epoch=65535)
                    self.assertEqual(actual,frozen.cold_payload_bytes(packet))

    def test_final_normal_special_and_independent_integer(self):
        for n in (32,256):
            for base in (host.minimum_base(n,16),1000000000):
                T=n//16;profile=host.profile_make(n,base,7);owner=(19<<24)|(65535<<8)|7
                cases=[([0]*n,[-1]+[0]*15,[0]*16),([base-1]*n,[1]+[0]*15,[0]*16)]
                cases.append(([(j*j+7*j+11)%base for j in range(n)],
                    [(base-1)*(-1 if j&1 else 1) for j in range(16)],
                    [(2*n+384)*(-1 if j&1 else 1) for j in range(16)]))
                for digits,c0,c1 in cases:
                    raw=host.pack32([digits[lane*T+row] for row in range(T) for lane in range(16)]+c0+c1)
                    result=host.final_decode(n,profile,1,owner,raw,expected_context=1,expected_owner=owner)
                    packet=frozen.decode_final_payload(raw,frozen.profile(n,16,base,7),context=1,owner=owner)
                    old=frozen.finalize(packet,expected_context=1,expected_owner=owner)
                    self.assertEqual(result.wire,host.pack32(old.digits))
                    self.assertEqual(result.carries,old.carries);self.assertEqual(result.special,old.special)
                    self.assertEqual(result.wire,host.pack32(independent_integer_oracle(digits,c0,c1,base)))

    def test_full_owner_context_generation_no_trimming(self):
        n=32;base=1009;profile=host.profile_make(n,base,7);owner=(19<<24)|(65535<<8)|7
        raw=host.pack32([3]*n+[0]*32)
        for bad in (owner^1,owner^(1<<8),owner^(1<<24),owner|(1<<56)):
            with self.assertRaisesRegex(host.HostError,'FULL56_OWNER'):
                host.final_decode(n,profile,1,bad,raw,expected_context=1,expected_owner=owner)
        with self.assertRaisesRegex(host.HostError,'CONTEXT'):
            host.final_decode(n,profile,0,owner,raw,expected_context=1,expected_owner=owner)

    def test_raw_ranges_and_exact_lengths(self):
        n=32;base=1009;profile=host.profile_make(n,base,7);owner=7
        raw=host.pack32([3]*n+[0]*32)
        for bad in (raw[:-4],raw+b'\0\0\0\0'):
            with self.assertRaisesRegex(host.HostError,'FINAL_EXACT_LENGTH'):
                host.final_decode(n,profile,0,owner,bad,expected_context=0,expected_owner=owner)
        bad=bytearray(raw);struct.pack_into('<I',bad,4*(n-1),base)
        with self.assertRaisesRegex(host.HostError,'FINAL_DIGIT_RANGE'):
            host.final_decode(n,profile,0,owner,bytes(bad),expected_context=0,expected_owner=owner)
        bad=bytearray(raw);struct.pack_into('<I',bad,4*(n+31),2*n+385)
        with self.assertRaisesRegex(host.HostError,'CORRECTION_RANGE'):
            host.final_decode(n,profile,0,owner,bytes(bad),expected_context=0,expected_owner=owner)
        with self.assertRaisesRegex(host.HostError,'COLD_SIGNED_DIGIT_RANGE'):
            host.cold_write(n,profile,0,owner,host.pack32([-2]+[0]*(n-1)),host.pack32([0]*32),
                expected_context=0,expected_owner=owner)

    def test_atomic_intake_partial_owner_reset_and_recovery(self):
        n=32;profile=host.profile_make(n,1009,7);owner=7;raw=host.pack32([3]*n+[0]*32)
        packet=host.AtomicIntake(n,profile,0,owner,'final');packet.append(raw[:4],offset=0,context=0,owner=owner)
        with self.assertRaisesRegex(host.HostError,'INTAKE_PARTIAL'):packet.commit(context=0,owner=owner)
        self.assertIsNone(packet.published)
        with self.assertRaisesRegex(host.HostError,'INTAKE_QUARANTINE'):packet.append(raw,offset=0,context=0,owner=owner)
        packet=host.AtomicIntake(n,profile,0,owner,'final');packet.append(raw,offset=0,context=0,owner=owner)
        packet.reset()
        with self.assertRaisesRegex(host.HostError,'INTAKE_QUARANTINE'):packet.commit(context=0,owner=owner)
        new_profile=host.profile_make(n,1009,8);packet=host.AtomicIntake(n,new_profile,0,8,'final')
        with self.assertRaisesRegex(host.HostError,'INTAKE_OWNER'):packet.append(raw,offset=0,context=0,owner=owner)
        self.assertIsNone(packet.published)
        packet=host.AtomicIntake(n,new_profile,0,8,'final')
        for offset in range(0,len(raw),4):packet.append(raw[offset:offset+4],offset=offset,context=0,owner=8)
        result=packet.commit(context=0,owner=8)
        self.assertEqual(result.wire,host.pack32([3]*n));self.assertIs(packet.published,result)

    def test_reset_one_context_leaves_peer_intake_unchanged(self):
        profile=host.profile_make(32,1009,7);raw=host.pack32([5]*32+[0]*32)
        a=host.AtomicIntake(32,profile,0,7,'final');b=host.AtomicIntake(32,profile,1,7,'final')
        a.append(raw[:4],offset=0,context=0,owner=7)
        b.append(raw,offset=0,context=1,owner=7);a.reset()
        result=b.commit(context=1,owner=7)
        self.assertEqual(result.wire,host.pack32([5]*32));self.assertIsNone(a.published)


if __name__=='__main__':unittest.main()
