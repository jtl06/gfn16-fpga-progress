import random
import unittest
from fpga.reference import stream27_host_offload_field100_v1 as f

class Tests(unittest.TestCase):
    def test_literal_field100_off(self):
        from fpga.reference import stream27_protected_relay13_bind as relay
        for n in (256,65536):
            b=f.capture(n);self.assertEqual(f.prepare(n),b)
            disabled=relay.prepare(n,enabled=0)
            self.assertEqual(b['files'],disabled['files']);self.assertEqual(b['parameters'],disabled['parameters'])
            self.assertNotIn('relay13',b['top'])
        with self.assertRaises(ValueError):f.prepare(relay13_enabled=1)
    def test_on_exact_reversal_and_interface(self):
        for n in (256,65536):
            parent=f.capture(n);b=f.prepare(n,host_offload=1)
            self.assertEqual(len(b['files']),66)
            self.assertTrue(all(b['files'][k]==v for k,v in parent['files'].items()))
            renames={k[:-3]:r['new_file'][:-3] for k,r in b['host_offload']['source_edits'].items()}
            for old,r in b['host_offload']['source_edits'].items():
                text=b['files'][r['new_file']]
                for a,c in renames.items():text=text.replace(c,a)
                self.assertEqual(f.reverse(text,r['edits']),parent['files'][old])
            self.assertEqual(b['parameters'],dict(parent['parameters'],HOST_OFFLOAD=1))
            self.assertIn('parameter int HOST_OFFLOAD=0',b['files'][b['top']+'.sv'])
            self.assertIn('genefer_stream27_host_offload_ingress_field100_v1',b['files'][renames[parent['top']]+'.sv'])
    def test_single_port_banks_and_unchanged_authority(self):
        new=(f.ROOT/f.LEAF).read_text();old=(f.ROOT/'rtl/kernel/genefer_stream27_host_offload_ingress_v1.sv').read_text()
        self.assertEqual(new[new.index(' always_ff @(posedge clk or negedge rst_n)'):],old[old.index(' always_ff @(posedge clk or negedge rst_n)'):])
        self.assertIn('logic [26:0] image[0:2*T-1];',new)
        self.assertEqual(new.count('image['),3) # declaration, one write, one read per fixed generated bank
        self.assertNotIn('image[field_index]',new)
        self.assertIn("image[{context_in,RW'(row_index)}]<=word_data[26:0]",new)
        self.assertIn('read_q<=image[{row_context,row_address}]',new)
        self.assertNotIn('read_q<=0',new)
    def test_banked_address_bijection_full_event_only(self):
        for n in (256,65536):
            t=n//16;addresses={(field,lane,ctx*t+row) for field in range(3) for ctx in range(2) for lane in range(16) for row in range(t)}
            self.assertEqual(len(addresses),6*n)
            self.assertEqual(max(a[2] for a in addresses),2*t-1)
    def test_bank_read_write_collision_and_hold(self):
        # Pure event model, N256 only. Old and new structures read old data on
        # same-edge same-address writes and hold outputs without read enable.
        rng=random.Random(106);old={};new={};oldq=None;newq=None;t=16
        for tick in range(4000):
            fld,lane,ctx,row=rng.randrange(3),rng.randrange(16),rng.randrange(2),rng.randrange(t)
            we=rng.randrange(2);re=rng.randrange(2);rctx=ctx if tick%3==0 else rng.randrange(2);rrow=row if tick%3==0 else rng.randrange(t)
            if re:
                oldq=tuple(old.get((a,rctx,b,rrow)) for a in range(3) for b in range(16))
                newq=tuple(new.get((a,b,rctx*t+rrow)) for a in range(3) for b in range(16))
            if we:old[fld,ctx,lane,row]=tick;new[fld,lane,ctx*t+row]=tick
            self.assertEqual(oldq,newq)
if __name__=='__main__':unittest.main()
