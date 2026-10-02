"""Pure source/event tests only: these do not run or simulate HDL."""
import unittest
from fpga.reference import core27_prefill_pipe_v1_structure as design
from fpga.reference import core27_prefill_pipe_v1_gates as gates
from fpga.reference import core27_prefill_pipe_v1_prepare as prep
from fpga.reference import core27_prefill_pipe_v1_mutations as mutations


class PipelineContract(unittest.TestCase):
    def test_eight_negative_recipes_are_single_fault_deltas(self):
        self.assertEqual(len(mutations.NAMES),8)
        for name in mutations.NAMES:
            fresh,mutant,contract=mutations.pair_sources(design.ROOT,name)
            changed={key for key in fresh if fresh[key]!=mutant[key]}
            self.assertEqual(changed,{mutations.CARRY} if name in mutations.TEE_MUTANTS else {mutations.CORE,mutations.BRIDGE})
            self.assertEqual(contract['expected_signal'],6)
            self.assertTrue(contract['lines'])

    def test_exact_sources(self):
        self.assertEqual(design.validate()['source_to_ram_edges'],8)
        self.assertEqual(len(gates.validate()),6)

    def test_enable_has_no_global_combinational_kill(self):
        s=design.generate()
        self.assertIn('assign ntt_load=(state==CONVERT || prefill_window) && field_write_valid[f];',s)
        self.assertIn('assign prefill_commit=prefill_window && (&field_write_valid);',s)
        self.assertIn('assign carry_words[h]=$signed(source_words[h*96+:96]);',s)
        self.assertIn('field_launch_words[f][1]<=field_launch_words[f][0];',s)

    def test_descriptor_data_and_bubbles(self):
        # Independent latency contract: rows are tagged before the pipeline,
        # with unique data in each lane/field. No whole-N arithmetic or NTT.
        for aw in (5,16):
            events={3*i: (i*16,0xffff,tuple((i*37+h)%97 for h in range(48))) for i in range((1<<aw)//16)}
            pipe=[None]*8;got={}
            for edge in range(max(events)+10):
                if pipe[-1] is not None:got[edge]=pipe[-1]
                pipe=[events.get(edge)]+pipe[:-1]
            self.assertEqual(got,{edge+8:row for edge,row in events.items()})

    def test_fault_edge_only_old_admitted_write(self):
        for fault in range(20):
            pipe=[None]*8;failed=False;writes=[]
            for edge in range(30):
                old=pipe[-1]
                if old is not None and not failed:writes.append((edge,old))
                if edge==fault:failed=True
                pipe=[None]*8 if failed else [edge]+pipe[:-1]
            self.assertTrue(all(edge<=fault and row==edge-8 for edge,row in writes))

    def test_reset_discards_every_pipeline_age(self):
        for age in range(10):
            pipe=[None]*8;writes=[]
            for edge in range(20):
                if edge==age:pipe=[None]*8
                if pipe[-1] is not None:writes.append(edge)
                pipe=[0 if edge==0 and age!=0 else None]+pipe[:-1]
            self.assertEqual(writes,[8] if age>8 else [])

    def test_closed_manifest_profiles_and_exact_cycle_delta(self):
        manifests=prep.manifests()
        self.assertEqual(set(manifests),{'aw5-normal','aw5-targeted','aw16-normal'})
        self.assertEqual(len(manifests['aw5-targeted']['steps']),36)
        for aw in (5,16):
            text=manifests[f'aw{aw}-normal']['steps'][0]['expected_stdout']
            first=text.splitlines()[0]
            self.assertIn(f'conversion={(1<<aw)//16+9} ',first)
            self.assertIn('conversion=0 ',text)
        for manifest in manifests.values():
            self.assertEqual(manifest['host'],'aethia')
            self.assertEqual(manifest['probe']['expected_json']['model_threads'],1)

    def test_independent_observer_checks_fault_edge_and_quarantine(self):
        for path,text in gates.sources().items():
            if 'probe' not in path:continue
            self.assertIn('observed_valid[7]',text)
            self.assertIn('T5B_MONITOR_QUARANTINE_WRITE',text)
            self.assertNotIn('CORE_CARRY_WAIT && !dut.core_fault',text)


if __name__=='__main__':unittest.main()
