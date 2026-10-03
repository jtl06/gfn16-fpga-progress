import unittest
from fpga.reference import stream27_r15_protocol_age_component_v1 as native
from fpga.reference import stream27_r15_protocol_age_bind as binder


class ProtocolComponentSource(unittest.TestCase):
    def test_primitive_literal_diagnostic_reverse(self):
        m,f=native.role();parent=binder.capture(256)['files'][binder.LEAF]
        old=f['rtl/kernel/r15_age_component_old.sv'].decode()
        reverse=old.replace('module r15_age_component_old #(','module '+binder.LEAF[:-3]+' #(',1)
        reverse=reverse.replace("parameter logic [31:0] RESET_CYCLE=32'b0,\n ",'',1)
        reverse=reverse.replace('cycle_count<=RESET_CYCLE;',"cycle_count<='0;",1)
        self.assertEqual(reverse,parent)
        for p,raw in f.items():self.assertEqual(native.hashlib.sha256(raw).hexdigest(),m['sources'][p])
        self.assertEqual(len(m['build']['sv_sources']),3)

    def test_all_actual_outputs_and_two_reset_seeds(self):
        m,f=native.role();probe=f['rtl/tb/stream27_r15_protocol_age_probe.sv'].decode()
        self.assertEqual(probe.count(".RESET_CYCLE(32'hfffffff0)"),2)
        self.assertEqual(probe.count(".RESET_CYCLE(32'b0)"),2)
        for signal,_ in native.OUTPUTS:self.assertEqual(probe.count('.'+signal+'('),4)
        self.assertEqual(probe.count('.quarantine('),4)
        self.assertNotIn('force ',probe)
        cpp=f[native.CPP].decode()
        self.assertLess(cpp.index('gfn16_runtime::configure(context,argc,argv)'),cpp.index('p=new Vstream27_r15_protocol_age_probe'))
        self.assertIn('old_owner_count==(kind==0?1:2)',cpp)
        self.assertFalse(m['scope']['billions_native_edges'])

    def test_exact_mutants_and_expected_nonzero(self):
        m,f=native.role();a,af=native.role('bad-allocation');s,sf=native.role('bad-stop')
        path='rtl/kernel/r15_age_component_new.sv'
        self.assertEqual(af[path].replace(b"32'd0-32'(POINTWISE_FIRST)",b"32'd1-32'(POINTWISE_FIRST)",1),f[path])
        self.assertEqual(sf[path].replace(b'if(valid[i] && !stop)begin\n    pw_age_q',b'if(valid[i])begin\n    pw_age_q',1),f[path])
        for negative in (a,s):
            self.assertEqual(negative['steps'][0]['expected_returncode'],1)
            self.assertEqual(negative['steps'][0]['expected_stderr'],'R15_AGE_NATIVE_EQUIVALENCE\n')
            self.assertFalse(negative['scope']['independent_review'])


if __name__=='__main__':unittest.main()
