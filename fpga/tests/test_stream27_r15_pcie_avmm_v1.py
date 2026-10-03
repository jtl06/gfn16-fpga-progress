import unittest
from pathlib import Path
from fpga.reference import stream27_r15_pcie_avmm_model_v1 as m
from fpga.reference import stream27_r15_pcie_avmm_native_v1 as native
from fpga.reference.stream27_r15_host_link_model_v1 import Word,encode_word
from fpga.reference.stream27_r15_shell_packets_v1 import FIELDS,RESP,pack,unpack,canonical_a_record


class ApplicationBusTest(unittest.TestCase):
    def test_data_exact_all_owner_bits(self):
        w=Word(0xffffffff,0xfedcba98,1,(1<<56)-1,65567,0xffffffff)
        q=unpack(FIELDS,m.data_command(encode_word(w),65536))
        self.assertEqual([q[k] for k in ('context','session','lease','owner','index','word')],
                         [w.context,w.session,w.lease,w.owner,w.index,w.value])
        for offset in (19,28,31):
            b=bytearray(encode_word(w));b[offset]=255
            with self.assertRaises(ValueError):m.data_command(bytes(b),65536)
        with self.assertRaises(ValueError):m.data_command(encode_word(w),256)

    def test_burst_alignment_range_and_context(self):
        self.assertEqual(m.burst((1<<22)+31*32,1,export=True,n=32),(1,31,1))
        self.assertEqual(m.burst((1<<22)-32,1),(0,131071,1))
        for address,count,export in ((1,1,False),(1<<22,1,False),((1<<22)-32,2,False),(0,0,False),(0,32,False),(31*32,2,True),(1<<23,1,True)):
            with self.assertRaises(ValueError):m.burst(address,count,export=export,n=32)

    def test_selected_snapshots_no_generation_wrap(self):
        s=pack(RESP,core_generation=0x07ff,next_epoch=0x1234abcd,accepted=99,applied=13)
        self.assertEqual(m.snapshot_register(s,'NEXT_GENERATION',0,accepted=17,last_lease=3),256)
        self.assertEqual(m.snapshot_register(s,'NEXT_GENERATION',1,accepted=17,last_lease=3),8)
        self.assertEqual(m.snapshot_register(s,'NEXT_EPOCH',1,accepted=17,last_lease=3),0x1234)
        self.assertEqual(m.snapshot_register(s,'ACCEPTED',0,accepted=17,last_lease=3),17)

    def test_a32_full_body_and_sensitivity(self):
        args=dict(context=1,session=7,owner=0xabcdef01234567,index=65535)
        data=canonical_a_record(**args,word=-(1<<95))
        resp=pack(RESP,op=6,status=0,context=1,session=7,data=data)
        self.assertEqual(m.check_a_response(resp,**args),data)
        for bit in (8,16,32,256,288,320,375,376,384):
            with self.assertRaises(ValueError):m.check_a_response(resp^(1<<bit),**args)

    def test_stalled_beat_not_mutable_or_withdrawable(self):
        h=m.HeldBeat();h.edge(True,(1,2,3),True);h.edge(True,(1,2,3),True)
        with self.assertRaises(ValueError):h.edge(True,(1,2,4),False)
        with self.assertRaises(ValueError):h.edge(False,(1,2,3),False)
        h.edge(False,None,False,reset=True);h.edge(True,(4,5),False)

    def test_source_closed_normal_first_role(self):
        manifest,files=native.role()
        self.assertEqual(manifest['build']['runtime_threads'],1)
        self.assertEqual(manifest['build']['parameters'],{'N':32})
        self.assertFalse(manifest['scope']['whole_compute'])
        self.assertFalse(manifest['scope']['independent_review'])
        self.assertEqual(manifest['steps'][0]['argv'],['{exe}'])
        for path,raw in files.items():self.assertEqual(native.hashlib.sha256(raw).hexdigest(),manifest['sources'][path])
        rtl=files[native.RTL].decode()
        self.assertNotIn('[0:N',rtl)
        self.assertIn('parameter integer N=65536',rtl)
        self.assertIn('waiting_session',rtl)
        self.assertIn('cold_byteenable!=32\'hffffffff',rtl)
        self.assertIn('if(!abort_sent)abort_due<=1',rtl)

    def test_fault_role_literal_frozen_normal(self):
        from fpga.reference import stream27_r15_pcie_avmm_fault_native_v1 as fault
        manifest,files=fault.role()
        self.assertEqual(manifest['test_role'],'deliberate_fault')
        self.assertEqual(manifest['build']['cpp_source'],fault.CPP)
        frozen=native.BASE/'normal-v1/source/fpga'
        self.assertEqual(files[native.RTL],(frozen/native.RTL).read_bytes())
        self.assertEqual(files[native.CPP],(frozen/native.CPP).read_bytes())
        self.assertIn('cases=27 invalid_records=15',manifest['steps'][0]['expected_stdout'])

    def test_v2_origin_guard_exact_reversal_and_negative(self):
        from fpga.reference import stream27_r15_pcie_avmm_v2 as v2
        old=(native.BASE/'normal-v1/source/fpga'/native.RTL).read_bytes().decode()
        new=v2.source().decode()
        back=new.replace(' wire held_violation=(ctrl_stalled && ctrl_payload!=held_ctrl) ||\n'
             '   (cold_stalled && cold_payload!=held_cold) ||\n'
             '   (export_stalled && export_payload!=held_export);\n','')
        back=back.replace('!protocol_error && !held_violation &&','!protocol_error &&')
        back=back.replace('!cmd_valid && !waiting && !held_violation','!cmd_valid && !waiting')
        self.assertEqual(back,old)
        normal,normal_files=v2.role();fault,fault_files=v2.role('fault')
        self.assertEqual(normal_files[native.RTL],fault_files[native.RTL])
        self.assertIn('cases=28 invalid_records=18',fault['steps'][0]['expected_stdout'])
        negative,_=v2.role('fault',missing_origin_mask=True)
        self.assertEqual(negative['steps'][0]['expected_returncode'],1)
        self.assertEqual(negative['steps'][0]['expected_stderr'],'R15_AVMM_FAULT_VALID_A_LEAK\n')

    def test_registered_error_origin_counterexample(self):
        # Pure binary source-calendar fact, not native publication proof.
        for old_error in (False,True):
            for held_violation in (False,True):
                v1_publish=not old_error
                v2_publish=not(old_error or held_violation)
                self.assertFalse(v2_publish and held_violation)
                if not old_error and held_violation:self.assertTrue(v1_publish)

    def test_v3_read_dontcare_reversal_and_new_normal(self):
        from fpga.reference import stream27_r15_pcie_avmm_v3 as v3
        from fpga.reference import stream27_r15_pcie_avmm_v2 as v2
        old=v2.source().decode();new=v3.source().decode()
        self.assertEqual(new.replace("(ctrl_write?ctrl_writedata:32'b0)",'ctrl_writedata'),old)
        normal,files=v3.role();fault,faultfiles=v3.role('fault')
        self.assertEqual(files[native.RTL],faultfiles[native.RTL])
        self.assertIn('read_dontcare=4',normal['steps'][0]['expected_stdout'])
        self.assertIn('R15_AVMM_READ_DONTCARE_OVERREJECTION',files[native.CPP].decode())
        self.assertIn('!held_violation',files[native.RTL].decode())

    def test_v4_first_beat_burst_ownership(self):
        from fpga.reference import stream27_r15_pcie_avmm_v4 as v4
        from fpga.reference import stream27_r15_pcie_avmm_v3 as v3
        new=v4.source().decode();old=v3.source().decode()
        back=new.replace("{(cold_left==0?cold_address:64'b0),cold_write,cold_writedata,cold_byteenable,(cold_left==0?cold_burstcount:5'b0)}",
                         '{cold_address,cold_write,cold_writedata,cold_byteenable,cold_burstcount}')
        for field in ('cold_address[63:22]!=0','cold_address[4:0]!=0','cold_burstcount==0'):
            back=back.replace('(cold_left==0 && '+field+')',field)
        anchor='        (cold_writedata[31:0]!=32\'h52315000'
        back=back.replace(anchor,'        (cold_left!=0 && (cold_address!=cold_base || cold_burstcount!=cold_total)) ||\n'+anchor)
        self.assertEqual(back,old)
        normal,f=v4.role();fault,ff=v4.role('fault')
        self.assertEqual(f[native.RTL],ff[native.RTL])
        self.assertFalse(normal['scope']['constantBurstBehavior'])
        self.assertIn('cold_dontcare=2',normal['steps'][0]['expected_stdout'])
        self.assertIn('0xffffffffffffffe1ull',f[native.CPP].decode())

    def test_v5_progress_and_descriptor_header_separation(self):
        from fpga.reference import stream27_r15_pcie_avmm_v5 as v5
        normal,f=v5.role();fault,ff=v5.role('fault')
        self.assertEqual(f[native.RTL],ff[native.RTL])
        self.assertIn('||(ctrl_active&&!ctrl_waitrequest)',f[native.RTL].decode())
        self.assertIn("ctrl_address!=64'h70",f[native.RTL].decode())
        self.assertIn('R15_AVMM_CROSSBUS_PROGRESS',f[native.CPP].decode())
        self.assertIn('descriptor_while_load=1',normal['steps'][0]['expected_stdout'])
        # Pure fixed-state counterexample: cold_left>0, deferred control held.
        ctrl_active=True;ctrl_wait=True
        old_cold_wait=ctrl_active
        new_cold_wait=ctrl_active and not ctrl_wait
        self.assertTrue(old_cold_wait);self.assertFalse(new_cold_wait)

    def test_v6_error_credit_and_cursor_retirement(self):
        from fpga.reference import stream27_r15_pcie_avmm_v6 as v6
        normal,f=v6.role();fault,ff=v6.role('fault')
        self.assertEqual(f[native.RTL],ff[native.RTL])
        rtl=f[native.RTL].decode()
        self.assertIn('protocol_error<=1;cold_left<=0',rtl)
        self.assertIn('fault();waiting<=0',rtl)
        self.assertIn('if(waiting && waiting_op==READ_A && export_left!=0)',rtl)
        self.assertIn('cases=39 invalid_records=33',fault['steps'][0]['expected_stdout'])
        self.assertIn('R15_AVMM_BAD_CTRL_COMPLETION',ff['rtl/tb/stream27_r15_pcie_avmm_faults.cpp'].decode())
        negative,_=v6.role('fault',missing_origin_mask=True)
        self.assertEqual(negative['steps'][0]['expected_stderr'],'R15_AVMM_FAULT_VALID_A_LEAK\n')
        self.assertIn('(resp_data[15:8]==0 && resp_data[152])',rtl)
        self.assertIn('!held_violation && !resp_valid',rtl)
        self.assertIn('abort_due||resp_valid||cmd_valid||waiting',rtl)
        self.assertIn('void pre()',f[native.CPP].decode())
        self.assertNotIn('d.clk=0;d.eval();',f[native.CPP].decode())


if __name__=='__main__':unittest.main()
