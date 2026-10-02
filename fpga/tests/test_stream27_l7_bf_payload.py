import random
import json
import unittest
from fpga.reference import stream27_l7_bf_payload as s

class PayloadTests(unittest.TestCase):
    def test_exact_source_delta(self):
        v=s.verify();self.assertEqual(v['numeric_source_reset_bits_removed'],195)
        self.assertEqual(v['E0_to_E5'],5);self.assertFalse(v['physical_saving_claim'])
    def test_dirty_model_all_fields_all_ages(self):
        for p in s.oracle.FIELDS:
            rows=s.events(p)
            for seed in range(4):
                old=s.Core(p,free=False,seed=seed);new=s.Core(p,free=True,seed=seed+71);pending=[]
                for edge,row in enumerate(rows):
                    reset,valid,gs,u,v,w,tag,cancel=row
                    if not reset or cancel:pending=[]
                    elif valid:pending.append((edge+5,*s.oracle.butterfly(u,v,w,p,gs),tag))
                    a,b=old.tick(row),new.tick(row);self.assertEqual(a,b,(p,seed,edge))
                    due=bool(pending and pending[0][0]==edge);self.assertEqual(a[0],due)
                    if due:self.assertEqual(a[1:],pending.pop(0)[1:])
                self.assertFalse(pending)
    def test_typed_counter_negative(self):
        for p in s.oracle.FIELDS:
            _,c=s.corpus(p)
            text=f'PASS_L7_BF_PAYLOAD P={p} '+' '.join(f'{k}={v}' for k,v in c.items())+' outputs=2 latency=5 ii=1\n'
            self.assertEqual(s.validate(text,'',0,{'p':p},{})['status'],'PASS_expected_contracts')
            for bad in (text.replace('latency=5','latency=4'),text.replace(f'dirty={c["dirty"]}','dirty=0')):
                with self.assertRaises(ValueError):s.validate(bad,'',0,{'p':p},{})
    def test_invalid_dirty_inputs_do_not_publish(self):
        for p in s.oracle.FIELDS:
            core=s.Core(p,free=True,seed=0x123)
            for row in [(0,1,1,(1<<28)-1,(1<<28)-1,(1<<27)-1,0xffffffff,0)]+[(1,0,1,(1<<28)-1,0,(1<<27)-1,42,0)]*20:
                self.assertEqual(core.tick(row),(False,0,0,0))
    def test_field_binding_keeps_multiplier_roots_calendar(self):
        from fpga.reference import stream27_timing_field_native as normal
        from fpga.reference import stream27_l7_resetfree_mont as mont_cut
        pin='ee144c0fdd5c84f58cb0ca392eccb472878978cc029992608fb95b69e9dd0414'
        for field in range(3):
            before=normal.field_bundle(8,16,field,pin);after=s.bind(before)
            self.assertEqual(before['geometry'],after['geometry']);self.assertEqual(before['parameters'],after['parameters'])
            for name,text in before['files'].items():
                if name==s.Path(s.PARENT).name:self.assertEqual(after['files'][name],s.derived())
                else:self.assertEqual(s.ident(after['files'][name],s.NEW_NAME,s.OLD_NAME),text)
            self.assertEqual(s.bind(before,enabled=0),before)
            with self.assertRaisesRegex(ValueError,'ISOLATED'):s.bind(mont_cut.bind(before))
    def test_explicit_mutant_anchors_and_counter_controls(self):
        files,top,sv,cc=s.mutant_files();self.assertIn(top.encode(),files[sv])
        self.assertIn(b'local_rst_n',files[sv]);self.assertIn(b'in_valid(in_valid&&!cancel)',files[sv])
        self.assertIn(b'need(detected==31',files[cc])
        for p in s.oracle.FIELDS:
            _,c=s.corpus(p);text=f'PASS_L7_BF_PAYLOAD_MUTANTS P={p} '+' '.join(f'{k}={v}' for k,v in c.items())+' detected=31 outputs=2 latency=5 ii=1\n'
            s.validate_mutants(text,'',0,dict(p=p),{})
            with self.assertRaisesRegex(ValueError,'TYPED'):s.validate_mutants(text.replace('detected=31','detected=30'),'',0,dict(p=p),{})
    def test_actual_command_token_grammar(self):
        m,files=s.role(s.oracle.FIELDS[0]);s.preflight(m,files)
        self.assertEqual(m['steps'][0]['argv'][1],'{root}/vectors/l7-bf-payload.txt')
        m['steps'][0]['argv'][1]='{source_root}/vectors/l7-bf-payload.txt'
        with self.assertRaisesRegex(ValueError,'unknown command token'):s.preflight(m,files)
    def test_prepared_field_probe_keeps_parent_controls(self):
        parent=s.ROOT/'artifacts/s4-l7-resetfree-parent-field-p16-f0-source-v1/project'
        candidate=s.ROOT/'artifacts/s4-l7-bf-payload-field-p16-f0-source-v1/project'
        if not candidate.exists():self.skipTest('Source-only fit project not yet prepared')
        for name in ('probe.qsf','probe.qpf','probe.sdc','run.tcl'):
            self.assertEqual((parent/name).read_bytes(),(candidate/name).read_bytes())
        m=json.loads((candidate/'manifest.json').read_text())
        self.assertEqual(m['core_parameters'],json.loads((parent/'manifest.json').read_text())['core_parameters'])
        self.assertEqual(m['comparison']['parent_workers'],4)
        self.assertFalse(m['comparison']['Mont_reset_only_or_L3b_combined'])
        changed=[]
        for name in m['source_sha256']:
            a=(parent/'rtl'/name).read_text();b=(candidate/'rtl'/name).read_text()
            if a!=b:changed.append(name)
            if name==s.Path(s.PARENT).name:self.assertEqual(b,s.derived())
            else:self.assertEqual(s.ident(b,s.NEW_NAME,s.OLD_NAME),a)
        self.assertEqual(len(changed),3)
        self.assertEqual((candidate/'rtl'/s.Path(s.MULT).name).read_bytes(),(s.ROOT/s.MULT).read_bytes())
    def test_component_fit_gate_not_whole_qualification(self):
        self.assertEqual(len(s.fit_gate_ids()),6)
        self.assertEqual(len(s.field_gate_ids()),8)
        self.assertTrue(all('-aw16-' not in qid for qid in s.fit_gate_ids()))
        self.assertTrue(any('-aw16-' in qid for qid in s.field_gate_ids()))

if __name__=='__main__':unittest.main()
