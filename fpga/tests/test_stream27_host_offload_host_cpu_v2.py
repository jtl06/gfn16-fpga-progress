"""Pure source/envelope tests, not native C or full-N numerical execution."""
import json
import unittest

from fpga.reference import stream27_host_offload_host_benchmark_output_v2 as output
from fpga.reference import stream27_host_offload_host_cpu_prepare_v3 as prepare


class CpuPacket(unittest.TestCase):
    def test_source_exact_unmodified_rtl_and_config(self):
        manifest,files=prepare.role()
        donor=json.loads((prepare.DONOR/'manifest.json').read_bytes())
        expected=dict(donor['build'],cpp_source=prepare.CPP)
        self.assertEqual(manifest['build'],expected)
        self.assertEqual(len(manifest['build']['sv_sources']),67)
        for name in manifest['build']['sv_sources']:
            self.assertEqual(files[name],(prepare.DONOR/'source/fpga'/name).read_bytes())
        self.assertEqual(manifest['steps'][0]['argv'],['{exe}','--host-selfcheck'])
        self.assertEqual(manifest['steps'][0]['expected_stderr'],'')
        self.assertEqual(manifest['steps'][1]['argv'],['{exe}','--host-benchmark'])
        self.assertFalse(manifest['r14_host_cpu']['chip_equivalence'])

    def test_runtime_and_early_worker_guard_before_full_math(self):
        source=(prepare.ROOT/prepare.CPP).read_text()
        self.assertLess(source.index('gfn16_runtime::configure'),source.index('DUT model(&context)'))
        self.assertNotIn('.eval(',source)
        self.assertLess(source.index('gethostname'),source.index('return r14_host_cpu_benchmark(3)'))
        helper=(prepare.ROOT/prepare.HELPER).read_text()
        self.assertNotIn('.eval(',helper)
        self.assertIn('std::chrono::steady_clock',helper)
        self.assertIn('std::clock()',helper)
        self.assertIn('r14_host_selfcheck()',helper)

    def test_parser_has_no_project_import(self):
        source=(prepare.ROOT/prepare.VALIDATOR).read_text()
        self.assertNotIn('from fpga',source)
        self.assertNotIn('from .',source)
        self.assertNotIn('numpy',source)

    def test_exact_envelope_rejects(self):
        config=output.config(3)
        for args in [('PASS\n','',0),('R14_HOST_CPU_PASS {}\n','',0),
                     ('R14_HOST_CPU_PASS {}\n','warning\n',0),
                     ('R14_HOST_CPU_PASS {}\n','',1),
                     ('R14_HOST_CPU_PASS {}\nextra\n','',0)]:
            with self.assertRaises(ValueError):output.validate(*args,config,{})
        for config in (output.config(True),output.config(0),dict(output.config(3),extra=1)):
            with self.assertRaises(ValueError):output.validate('','',0,config,{})

    def test_actual_collected_bytes_and_output_negatives(self):
        # Read/hash already-collected bytes only: no full-size numerical array
        # reconstruction, C/HDL/native execution or model recomputation here.
        folder=prepare.ROOT/'queue/evidence/s4-r14-host-cpu-q1-v3/attempt-0/collected/output/native'
        path=folder/'r14-host-cpu-synthetic-full-timing.log'
        if not path.exists():self.skipTest('actual worker output not collected yet')
        stdout=path.read_text();config=output.config(3)
        self.assertEqual(output.validate(stdout,'',0,config,{})['status'],'PASS_expected_contracts')
        good=json.loads(stdout.removeprefix('R14_HOST_CPU_PASS '))
        variants=[]
        for key,value in [('host','unadmitted'),('n',256),('p',8),('selfchecks',300),
                          ('header_sha256','0'*64),('special',True),('promotion_allowed',True),
                          ('native_core_equivalence',True),('backend_seconds',0.0),
                          ('transport_seconds',0.0),('overlap_seconds',0.0),('prp_wall_seconds',0.0),
                          ('profile_wall',[float('nan')]*3),('cold_cpu',[-1]*3),('final_wall',[60]*3)]:
            bad=dict(good);bad[key]=value;variants.append(bad)
        for position in (0,len(good['final_wire_hex'])-1):
            bad=dict(good);wire=bad['final_wire_hex']
            bad['final_wire_hex']=wire[:position]+('1' if wire[position]=='0' else '0')+wire[position+1:]
            variants.append(bad)
        bad=dict(good);bad['profile_wire_hex']='0'*64;variants.append(bad)
        bad=dict(good);bad['final_wire_hex']=bad['final_wire_hex'][:-8];variants.append(bad)
        self.assertEqual(len(variants),19)
        for bad in variants:
            text='R14_HOST_CPU_PASS '+json.dumps(bad)+'\n'
            with self.assertRaises(ValueError):output.validate(text,'',0,config,{})


if __name__=='__main__':unittest.main()
