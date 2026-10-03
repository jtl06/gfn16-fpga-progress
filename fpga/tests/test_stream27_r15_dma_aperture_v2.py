import unittest
from fpga.reference import stream27_r15_dma_aperture_v2 as leaf
from fpga.reference import stream27_r15_dma_aperture_native_v2 as native


class RegisteredCredit(unittest.TestCase):
    def test_exact_source_reverse_no_wait_fault_cone(self):
        raw=leaf.source()
        self.assertEqual(raw.replace(leaf.AFTER,leaf.BEFORE,1),leaf.PARENT.read_bytes())
        # Explicit actual wire cone: response_credit no longer depends on
        # down_rd_fire. Other fan-in is input/FF state, not downstream WAIT.
        for line in raw.decode().splitlines():
            if line.strip().startswith(('wire response_credit=','wire stray_response=','wire current_error=')):
                self.assertNotIn('down_rd_fire',line)
                self.assertNotIn('waitrequest',line)

    def test_conditional_coupled_wait_unique_fixedpoint(self):
        # WAIT = fault OR otherwait; actual endpoint RV is registered. This
        # conditional scalar witness never asserts normal zero-latency traffic.
        saw_old_ambiguity=False;checks=0
        for credit in range(32):
            for hold in (False,True):
                for rv in (False,True):
                    for otherwait in (False,True):
                        old=[];new=[]
                        for fault in (False,True):
                            fire=hold and not(otherwait or fault)
                            if fault==(rv and not(credit or fire)):old.append(fault)
                            if fault==(rv and not credit):new.append(fault)
                        self.assertEqual(len(new),1)
                        saw_old_ambiguity|=len(old)==2;checks+=1
        self.assertTrue(saw_old_ambiguity);self.assertEqual(checks,256)

    def test_source_roles_and_two_exact_negatives(self):
        m,f=native.role();fault,ff=native.role('fault');missing,mf=native.role('missing-mask');bad,bf=native.role('bad-credit')
        rtl=native.parent.RTL;cpp=native.parent.CPP
        self.assertEqual(f[rtl],leaf.source());self.assertEqual(f[cpp],ff[cpp])
        for p,raw in f.items():self.assertEqual(native.hashlib.sha256(raw).hexdigest(),m['sources'][p])
        self.assertEqual(mf[rtl].replace(b'rd_readdata=rd_data_q;',b"rd_readdata=terminal?256'b0:rd_data_q;",1),f[rtl])
        self.assertEqual(bf[rtl].replace(leaf.BEFORE,b' wire response_credit=(rd_expected!=0);',1),f[rtl])
        self.assertEqual(bad['steps'][0]['expected_stderr'],'R15_APERTURE_ZERO_LATENCY_NOT_REJECTED\n')
        self.assertEqual(missing['steps'][0]['expected_returncode'],1)
        self.assertIn('registered_credit=1',m['steps'][0]['expected_stdout'])
        self.assertIn('cases=23',fault['steps'][0]['expected_stdout'])
        self.assertIn('b.read(0x800000-32,1);b.step();',f[cpp].decode())
        self.assertFalse(m['scope']['old_native_outcome_inherited'])


if __name__=='__main__':unittest.main()
