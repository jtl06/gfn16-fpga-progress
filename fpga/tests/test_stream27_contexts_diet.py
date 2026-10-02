import hashlib
import json
import unittest
from fpga.reference import stream27_contexts_diet_schedule as calendar
from fpga.reference import stream27_threefield_contexts as arithmetic
from fpga.reference import stream27_warm_contexts as warm
from fpga.reference import stream27_host_contexts as host

FLAGS=dict(corr_serial_bfs=2,mont_factored=1)
ZERO={
    (arithmetic.SELF,32,8):'80efce503fd830409b341b56d19583bff9594455a4ac64936a173a5d69ee819b',
    (arithmetic.SELF,32,16):'2fa28462de25be114a406deb4c542bbbc95343df2657d52ecf63349264bdcfd8',
    (warm.SELF,32,8):'8c9d2b190bf2c1090629fcc9c4e35be3c2b40e93833646c36b79b822415016a4',
    (warm.SELF,256,16):'9d592c9b5f5fb3e12ad70a115cc8fcf91e0800660fa1c270e6809818882efb5d',
    (host.SELF,32,8):'ace319160e05ce34fdead361d03e9e0439710e1085951daaad1be4a63015cc94',
    (host.SELF,32,16):'5e880cbdf904426536220eecdf1d32968b4d5e826a414eb9ebe156f05189b6cc',
    (host.SELF,256,16):'6cd69d060dd978b990c549e844aaf574cb1264132ac701ef5d14f0b6c7eefab8',
}


class SourceTests(unittest.TestCase):
    def test_default_rtl_maps_byte_identical(self):
        for module in (arithmetic,warm,host):
            for (path,n,p),pin in ZERO.items():
                if path!=module.SELF:continue
                b=module.prepare(n,p)
                digest=hashlib.sha256(json.dumps(b['generated_sha256'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
                self.assertEqual(digest,pin)

    def test_actual_diet_flags_reach_all_real_fields(self):
        for module in (arithmetic,warm,host):
            for n in (32,256):
                kwargs=dict(FLAGS,cold_launch_fence=1) if module is host else FLAGS
                b=module.prepare(n,16,**kwargs)
                for key,value in (('CORR_SERIAL_BFS',2),('MONT_FACTORED',1),('COMM_STAGE_SHARED_MLAB',1)):
                    self.assertEqual(b['parameters'][key],value)
                    self.assertIn(f'{key}={value}',b['files'][b['top']+'.sv'])
                roots=[text for name,text in b['files'].items() if name.startswith('genefer_stream27_shared_warm_')]
                self.assertEqual(len(roots),3)
                for text in roots:
                    self.assertIn('CORR_SERIAL_BFS=2',text)
                    self.assertIn('MONT_FACTORED=1',text)
                    self.assertIn('COMM_STAGE_SHARED_MLAB=1',text)
                    self.assertIn('.GEN_W(27)) correction_transform',text)
                    self.assertIn('A_table[0:3]',text)
                self.assertIn('genefer_stream27_montgomery_factored_v1.sv',b['files'])
                self.assertIn('genefer_montgomery_mul27_sparse_pipe.sv',b['files']) # exact CRT closure
                self.assertEqual(b['geometry']['correction_cache_latency'],75 if n==32 else 77)

    def test_full_period_and_shared_ports_for_odd_intervals(self):
        for n,interval,gaps,cold_b,feedback in ((32,161,[80,81],80,[2,2]),
                (256,212,[106,106],106,[16,16]),(65536,8459,[4229,4230],8233,[0,0])):
            plan=calendar.schedule(n,16,counts=(3,5))
            self.assertEqual(plan['per_context_interval'],interval)
            self.assertEqual(plan['launch_gaps'],gaps)
            self.assertEqual(plan['correction'][1]['accept'],cold_b)
            self.assertEqual(plan['feedback_peak_rows'],feedback)
            for ctx in (0,1):
                starts=[x['start'] for x in plan['lease_allocation'] if x['context']==ctx]
                self.assertTrue(all(b-a==interval for a,b in zip(starts,starts[1:])))
            self.assertTrue(all(c['margin']>=0 for c in plan['correction']))

    def test_counted_feedback18_preserves_owner_and_authority(self):
        b=warm.prepare(256,16,**FLAGS);text=b['files'][b['top']+'.sv']
        for token in ('logic [17:0] fifo_valid,fifo_start','fifo_owner[0:17]',
                      'feedback_owner=fifo_owner[17]','fifo_valid[16:0],feedback_issue','d<18;'):
            self.assertIn(token,text)
        self.assertIn('command_index[feedback_context*32+:32]!=launched[feedback_context]',text)
        self.assertIn('latched_count[0:1]',text)

    def test_first_cold_reservation_fenced_until_actual_first(self):
        b=host.prepare(32,16,cold_launch_fence=1);text=b['files'][b['top']+'.sv']
        self.assertIn('(!anchor_valid && !first_cold_inflight)',text)
        self.assertIn('if(!anchor_valid)first_cold_inflight<=1;',text)
        self.assertIn('if(!anchor_valid)begin first_cold_inflight<=0;anchor_valid<=1;',text)
        self.assertIn('COLD_LAUNCH_FENCE=1',text)
        for rows in (2,4,16):
            reserved=False;anchor=False;requests=[]
            for edge in range(rows+5):
                request=not anchor and not reserved
                if request:requests.append(edge);reserved=True
                if edge==rows+2:anchor=True;reserved=False
            self.assertEqual(requests,[0])

    def test_host_uses_actual_diet_calendar_not_undieted_plan(self):
        for n,offset,second,delay,interval in ((32,80,80,4,161),(256,106,106,18,212)):
            b=host.prepare(n,16,**FLAGS,cold_launch_fence=1);text=b['files'][b['top']+'.sv']
            self.assertIn(f'CONTEXT_OFFSET={offset},SECOND_CORRECTION={second}',text)
            self.assertEqual(b['geometry']['feedback_delay'],delay)
            self.assertEqual(b['geometry']['warm_interval'],interval)
            self.assertEqual(b['two_context_schedule']['launch_gaps'],[interval//2,interval-interval//2])
            self.assertIn('.row_write_owner(final_owner)',text)
            self.assertIn('canonical_ready=published & {2{!error}}',text)
        with self.assertRaisesRegex(ValueError,'EXPLICIT_COLD_FENCE'):host.prepare(32,16,**FLAGS)


if __name__=='__main__':unittest.main()
