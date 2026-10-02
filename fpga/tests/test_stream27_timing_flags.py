import unittest
from fpga.reference import stream27_timing_flags as timing
from fpga.reference import stream27_host_chain_flags as host
from fpga.reference import stream27_shared_field_flags as field

FLAGS=dict(boundary_inputreg=1,descriptor_fifo_ff=1,quarantine_replicas=1,
           final_gs_inputreg=1,canonical_localbase=1,carry_localbase=1)


class SourceTests(unittest.TestCase):
    def test_zero_complete_parent(self):
        self.assertEqual(timing.prepare_field(256,8,0),field.prepare(256,8,0))
        self.assertEqual(timing.prepare(256,8,canonical_pipe_stages=1),
                         host.prepare(256,8,canonical_pipe_stages=1))

    def test_inverse_only_last_stage_tags_and_roots(self):
        for n in (32,256):
            old=timing.prepare_field(n,8,0)
            b=timing.bind_field(old,final_gs_inputreg=1)
            before=next(s for name,s in old['files'].items() if name.startswith('genefer_stream28_merged_gs_'))
            after=next(s for name,s in b['files'].items() if name.startswith('genefer_stream28_merged_gs_'))
            stage=n.bit_length()-2;start=before.index(f' if(1)begin: stage{stage}\n')
            self.assertEqual(before[before.index(') ('):start],after[after.index(') ('):after.index(f' if(1)begin: stage{stage}\n')])
            last=after[after.index(f' if(1)begin: stage{stage}\n'):]
            for token in ('logic [6:0] slot_pipe,start_pipe','generation_pipe[0:6]',
                          'slot_pipe[6]','start_pipe[6]','generation_pipe[6]','k<7;',
                          'genefer_stream27_merged_final_gs_pair_inputreg_v1 #('):
                self.assertIn(token,last)
            scales=[line for line in before.splitlines() if '.UPPER_SCALE(' in line]
            self.assertEqual(scales,[line for line in after.splitlines() if '.UPPER_SCALE(' in line])
            for name,text in old['files'].items():
                if 'root' in name:self.assertEqual(b['files'][name],text)
            self.assertEqual(b['geometry']['sink_accept'],old['geometry']['sink_accept']+1)
            self.assertEqual(b['geometry']['pointwise_accept'],old['geometry']['pointwise_accept'])

    def test_whole_source_join_and_flags(self):
        for n in (32,256):
            standalone=timing.prepare(n,8,**FLAGS)
            paired=timing.prepare(n,8,paired=True,**FLAGS)
            for name,text in standalone['files'].items():self.assertEqual(paired['files'].get(name),text)
            self.assertEqual(len(paired['rtl_sources'])-len(standalone['rtl_sources']),11)
            for key in ('BOUNDARY_INPUTREG','DESCRIPTOR_FIFO_FF','QUARANTINE_REPLICAS',
                        'FINAL_GS_INPUTREG','CANONICAL_LOCALBASE','CARRY_LOCALBASE'):
                self.assertEqual(standalone['parameters'][key],1)
                self.assertIn('parameter int '+key+'=1',standalone['files'][standalone['top']+'.sv'])
            roots=[text for name,text in standalone['files'].items() if name.startswith('genefer_stream27_shared_warm_')]
            self.assertEqual(len(roots),3)
            for root in roots:
                self.assertIn('fault_replicas (',root)
                self.assertIn('signed_boundary_inputreg_v1 #(',root)
                self.assertIn('_inputreg_v1 inverse_transform (',root)

    def test_small_feedback_explicit_extra_edge(self):
        old=host.prepare(32,8,canonical_pipe_stages=1)
        b=timing.prepare(32,8,**FLAGS)
        self.assertEqual(b['geometry']['warm_interval'],129)
        self.assertEqual(b['geometry']['first_digit'],123)
        self.assertEqual(b['geometry']['carry_done'],130)
        self.assertEqual(b['geometry']['feedback_delay'],5)
        warm=next(s for name,s in b['files'].items() if name.startswith('genefer_stream27_warm_chain_'))
        self.assertIn('logic [4:0] fifo_valid,fifo_start',warm)
        self.assertIn('fifo_owner[4]',warm)
        self.assertIn('d<5;',warm)
        self.assertEqual(b['cycle_contract']['host_done']-old['cycle_contract']['host_done'],1)

    def test_full_geometry_scalar_ledger(self):
        old=field.parent.geometry(65536,8)
        boundary=field.boundary_geometry(old,allow_recalendar=True)
        new=timing.inverse_geometry(boundary)
        self.assertEqual((new['first_digit'],new['warm_interval'],new['carry_done']),(16653,16654,24848))
        self.assertEqual(new['correction_cache_latency'],37)
        self.assertEqual(new['feedback_delay'],0)
        self.assertEqual(new['cache_margin'],old['cache_margin']-1)
        self.assertEqual(2*(new['carry_done']-old['carry_done'])+7*(new['warm_interval']-old['warm_interval']),9)
        self.assertEqual(3*new['warm_interval']-4,49958)


if __name__=='__main__':unittest.main()
