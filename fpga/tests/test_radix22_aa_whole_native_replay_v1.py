"""Pure saved-output/resource negatives only; no HDL/native/full-N arithmetic."""
import copy
import json
import unittest
from fpga.reference import radix22_aa_whole_native_replay_v1 as a


class WholeNativeReplayTests(unittest.TestCase):
    def evidence(self,id):
        done=json.loads((a.ROOT/'queue/done'/(id+'.json')).read_text())
        root=a.Path(done['result']['evidence'])/'output/native'
        report=json.loads((root/'report.json').read_text())
        return done,root,report

    def test_actual_caps_then_five_wrong_caps_reject(self):
        done,_,report=self.evidence(a.IDS[1]);a.limits(report,done)
        for key,value in [('memory_max_bytes',4<<30),('swap_max_bytes',1),('cpu_max',['max','100000']),
                          ('physical_cores',[[0,0],[0,0]]),('affinity',[0])]:
            r=copy.deepcopy(report);r['limits'][key]=value
            with self.assertRaises(ValueError):a.limits(r,done)
        for key,value in [('MainPID','1'),('ControlGroup','/live'),('InvocationID','0'*32),('RuntimeMaxUSec','infinity')]:
            d=copy.deepcopy(done);d['result']['properties'][key]=value
            with self.assertRaises(ValueError):a.limits(report,d)

    def test_saved_whole_outputs_then_typed_mutants_reject(self):
        for id in a.IDS[1:]:
            _,root,report=self.evidence(id);manifest=json.loads((root/'approved-manifest.json').read_text())
            step=manifest['steps'][0];spec=step['validator'];row=report['steps'][-1]
            raw=(root/row['log']).read_text();sources=a.unpack(root/'sources.tar.gz')
            assets={name:sources[path].decode() for name,path in spec['assets'].items()}
            validator=a.representative if id==a.IDS[-1] else a.small
            self.assertEqual(validator.validate(raw,'',0,spec['config'],assets),report['validations'][step['name']])
            for wrong in (raw.replace('ntt=', 'ntt=9',1),raw.replace('hold_checks=', 'hold_checks=9',1),
                          '\n'.join(raw.splitlines()[:-1])+'\n',raw+raw.splitlines()[-1]+'\n'):
                with self.assertRaises((ValueError,AssertionError)):validator.validate(wrong,'',0,spec['config'],assets)
            with self.assertRaises((ValueError,AssertionError)):validator.validate(raw,'unexpected\n',0,spec['config'],assets)
            with self.assertRaises((ValueError,AssertionError)):validator.validate(raw,'',1,spec['config'],assets)


if __name__=='__main__':unittest.main()
