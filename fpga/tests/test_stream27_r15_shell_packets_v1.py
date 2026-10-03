from pathlib import Path
import unittest
from fpga.reference.stream27_r15_shell_packets_v1 import FIELDS,RESP,pack,unpack,canonical_a_record
ROOT=Path(__file__).resolve().parents[1]


class PacketTests(unittest.TestCase):
    def test_fields_disjoint_roundtrip_and_reserved_refusal(self):
        for table in (FIELDS,RESP):
            used=0
            for shift,width in table.values():
                bits=((1<<width)-1)<<shift
                self.assertEqual(used&bits,0);used|=bits
            v={k:(1<<w)-1 for k,(s,w) in table.items()}
            self.assertEqual(unpack(table,pack(table,**v)),v)
            reserved=next(i for i in range(512) if not(used>>i)&1)
            with self.assertRaisesRegex(ValueError,'RESERVED'):unpack(table,1<<reserved)

    def test_canonical_record_signed96_and_complete_owner(self):
        owner=0x123456789abcde
        for value in (-1,0,604832955,(1<<94)+3):
            record=canonical_a_record(1,0xabcdef01,owner,65535,value)
            raw=record.to_bytes(32,'little')
            self.assertEqual(int.from_bytes(raw[0:4],'little'),0x52314101)
            self.assertEqual(int.from_bytes(raw[4:8],'little'),0xabcdef01)
            self.assertEqual(int.from_bytes(raw[8:16],'little'),owner)
            self.assertEqual(int.from_bytes(raw[16:20],'little'),65535)
            self.assertEqual(int.from_bytes(raw[20:32],'little',signed=True),value)

    def test_source_fences_and_no_field_payload_storage(self):
        t=(ROOT/'rtl/kernel/genefer_stream27_r15_core_transport_v1.sv').read_text()
        for s in ('token_lease==dc_next_lease-32\'d1','cache_owner[ctx]==owner',
                  'cache_lease[ctx]==token_lease','if(!cmd_empty)',
                  'if(command_accept)','read_context!=ctx || read_owner!=owner',
                  'canonical_ready[ctx]','dc_word_ready'):
            self.assertIn(s,t)
        self.assertNotIn('[0:N',t)
        reset=(ROOT/'rtl/kernel/genefer_stream27_r15_link_reset_v1.sv').read_text()
        self.assertIn("session_counter==32'hffffffff",reset)
        self.assertIn('session_counter<=session_counter+32\'d1',reset)
        self.assertNotIn('if(!external_reset_n)session_counter',reset)


if __name__=='__main__':unittest.main()
