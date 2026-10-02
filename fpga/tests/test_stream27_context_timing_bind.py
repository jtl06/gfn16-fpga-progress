import hashlib
import json
import re
import unittest
from fpga.reference import stream27_context_timing_bind as timing
from fpga.reference import stream27_host_contexts as host


FLAGS=dict(corr_serial_bfs=2,mont_factored=1,cold_launch_fence=1,explicit_net_declarations=1)


class TimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parents={n:host.prepare(n,16,allow_full_constants=n==65536,**FLAGS)
                     for n in (32,256,65536)}
        cls.candidates={n:timing.bind(b,enabled=1) for n,b in cls.parents.items()}

    def test_default_deep_copy_and_captured_parents_exact(self):
        for n,parent in self.parents.items():
            copy=timing.bind(parent)
            self.assertEqual(copy,parent)
            self.assertIsNot(copy['files'],parent['files'])
        for n,relative,key,generated in (
                (256,'artifacts/s4-p16-c2-explicit-aw8-normal-v1','r84_explicit_small','generated_sha256'),
                (65536,'artifacts/s4-p16-c2-explicit-full-normal-v1','r84','production_generated_sha256')):
            manifest=json.loads((timing.ROOT/relative/'manifest.json').read_text())
            self.assertEqual(self.parents[n]['generated_sha256'],manifest[key][generated])

    def test_real_counted_calendars_and_no_feedback_resize(self):
        for n,expected in ((32,(77,116,158,163,163,76,4,81)),
                           (256,(79,153,195,214,214,78,18,107)),
                           (65536,(4207,8417,8459,12558,8460,78,0,4230))):
            b=self.candidates[n];g=b['geometry'];plan=b['two_context_schedule']
            keys=('pointwise_accept','sink_accept','first_digit','carry_done','warm_interval',
                  'correction_cache_latency','feedback_delay')
            self.assertEqual(tuple(g[k] for k in keys)+(plan['context_offset'],),expected)
            self.assertEqual(g['feedback_delay'],self.parents[n]['geometry']['feedback_delay'])
            self.assertEqual(g['cache_margin'],30 if n==65536 else 0)
            self.assertEqual(plan['launch_gaps'],[g['warm_interval']//2,g['warm_interval']-g['warm_interval']//2])
            host=b['files'][b['top']+'.sv']
            cold_b=next(x['accept'] for x in plan['correction'] if x['tag'][0]==1 and x['tag'][3]==0)
            self.assertEqual(cold_b,8232 if n==65536 else expected[-1])
            self.assertIn(f'CONTEXT_OFFSET={expected[-1]},SECOND_CORRECTION={cold_b}',host)
            for counts in ((3,5),(3,14),(16,1)):
                cohort=timing.schedule(g,counts)
                self.assertLessEqual(cohort['lease_peak'],4)
                self.assertTrue(all(x['margin']>=0 for x in cohort['correction']))
                for context in (0,1):
                    starts=[x['start'] for x in cohort['lease_allocation'] if x['context']==context]
                    self.assertTrue(all(y-x==g['warm_interval'] for x,y in zip(starts,starts[1:])))

    def test_full_owners_profiles_and_intrinsic_accept_authority(self):
        b=self.candidates[256];p=self.parents[256]
        arith=next(k for k in p['files'] if k.startswith('genefer_stream27_threefield_carry_'))
        before=p['files'][arith];after=b['files'][arith]
        restored=after
        for c in b['context_timing']['field_contracts']:
            f=re.search(r'_f([012])_',c['parent_top'])[1]
            restored=restored.replace(f'genefer_stream27_shared_warm_aw8_p16_f{f}_v1_timing_c2_v1 #',c['parent_top']+' #')
        restored=restored.replace('genefer_stream27_blockcarry_lane_localbase_v1 #','genefer_stream27_blockcarry_lane_param_v1 #')
        self.assertEqual(restored,before)
        for name,text in b['files'].items():
            if name.startswith('genefer_stream27_shared_warm_'):
                for anchor in ('A_table[0:3]','.PAYLOAD_W(27)) boundary (',
                               '.GEN_W(25)) forward_transform (','.GEN_W(25)) inverse_transform (',
                               '.BANKS(4)','.pointwise_owner({pointwise_bank,fwd_generation})'):
                    self.assertIn(anchor,text)
                self.assertRegex(text,re.escape('if('+timing.fault.SETTER+')')+r'\s+controller_error<=1;')
                self.assertIn('.fault_set('+timing.fault.SETTER+')',text)
        self.assertIn('profile_reciprocal[field_context[0]]',after)
        self.assertIn('profile_base[field_context[0]]',after)
        self.assertIn('frame_profile_ok=config_valid[context_in]',after)

    def test_final_metadata_root_scales_and_shared_children(self):
        for n,b in self.candidates.items():
            p=self.parents[n];aw=n.bit_length()-1
            old_roots={name:text for name,text in p['files'].items() if 'root_rom' in name or 'root_packed' in name}
            self.assertTrue(old_roots)
            self.assertEqual({name:b['files'][name] for name in old_roots},old_roots)
            for f in range(3):
                old=next(name for name in p['files'] if name.startswith('genefer_stream28_merged_gs_') and f'_f{f}_' in name)
                new=old[:-3]+'_c2_inputreg_v1.sv';text=b['files'][new]
                start=text.index(f' if(1)begin: stage{aw-1}\n');last=text[start:]
                self.assertIn('generation_pipe[0:6]',last)
                self.assertIn('k<7;k=k+1)generation_pipe',last)
                self.assertEqual(last.count('genefer_stream27_merged_final_gs_pair_inputreg_v1 #('),8)
                self.assertEqual(re.findall(r'UPPER_SCALE\([^)]*\)',text),re.findall(r'UPPER_SCALE\([^)]*\)',p['files'][old]))
                for stage in range(aw-1):
                    pos=text.index(f' if(1)begin: stage{stage}\n')
                    end=text.index(f' if(1)begin: stage{stage+1}\n',pos)
                    self.assertIn('generation_pipe[0:5]',text[pos:end])
            for name in ('genefer_stream27_montgomery_factored_v1.sv',
                         'genefer_montgomery_mul27_sparse_pipe.sv','genefer_stream27_epoch_protocol_contexts_v1.sv'):
                self.assertEqual(b['files'][name],p['files'][name])

    def test_compiled_closure_no_forward_implicit_driver_regression(self):
        for b in self.candidates.values():
            self.assertEqual(len(b['rtl_sources']),58)
            source=re.sub(r'//[^\n]*|/\*.*?\*/','', '\n'.join(b['files'].values()),flags=re.S)
            definitions=dict(re.findall(r'\bmodule\s+(\w+)\b(.*?)\bendmodule\b',source,flags=re.S))
            # Frozen donor files include unused legacy definitions. Check the
            # reachable roster, rather than turning old uninstantiated debt
            # into a false missing-child result for this successor.
            pending=[b['top']];seen=set()
            while pending:
                module=pending.pop()
                if module in seen:continue
                self.assertIn(module,definitions);seen.add(module)
                pending+=re.findall(r'\b((?:genefer_|merged_stream27_)\w+)\s+(?:#\([^;]*?\)\s+)?\w+\s*\(',definitions[module])
            self.assertIn('genefer_stream27_mul_select_token_c2_factored_v1',seen)
            for name,text in b['files'].items():
                if name.startswith('genefer_stream27_threefield_carry_'):
                    self.assertLess(text.index('wire frame_profile_ok,field_input_valid;'),text.index('.in_slot_valid(field_input_valid)'))
                    self.assertIn('assign frame_profile_ok=',text)
                if name.startswith('genefer_stream27_shared_warm_'):
                    self.assertLess(text.index('wire [31:0] protocol_correction_base;'),text.index('boundary_base='))
            self.assertEqual(b['generated_sha256'],{name:hashlib.sha256(text.encode()).hexdigest() for name,text in b['files'].items()})

    def test_aw8_capture_copy_witness_and_own_first_edges(self):
        g=self.candidates[256]['geometry'];first=[204,204+g['warm_interval']//2]
        a_warm=first[0]+2*g['warm_interval']+g['carry_done']+1
        b_capture=first[1]+13*g['warm_interval']+g['first_digit']+1
        copy_first=a_warm+g['rows']+6+9*256
        self.assertLess(copy_first+8,b_capture)
        self.assertLess(b_capture+g['rows'],copy_first+256-8)
        self.assertEqual(first,[204,311])
        self.assertEqual([204,204+self.candidates[65536]['geometry']['warm_interval']//2],[204,4434])


if __name__=='__main__':unittest.main()
