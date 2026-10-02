import json
import unittest
from fpga.reference import stream27_l3b_ct_field_probe as p


class MatchedFieldProjects(unittest.TestCase):
    def test_actual_prepared_pair_controls_and_source_delta(self):
        roots=[p.ROOT/f'artifacts/s4-l3b-ct-composed-field-{name}-f0-v1/project' for name in ('parent','candidate')]
        old,new=[json.loads((root/'manifest.json').read_text()) for root in roots]
        for key in ('top','device','compile_processors','seed','clock_period_ns','core_parameters','geometry'):
            self.assertEqual(old[key],new[key])
        self.assertEqual(old['compile_processors'],6)
        self.assertEqual(old['clock_period_ns'],10)
        for name in ('probe.qpf','probe.sdc','run.tcl'):
            self.assertEqual((roots[0]/name).read_bytes(),(roots[1]/name).read_bytes())
        leaf=p.native.binding.NEW.split('/')[-1]
        extra='set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+leaf+'\n'
        self.assertEqual((roots[1]/'probe.qsf').read_text().removesuffix(extra),(roots[0]/'probe.qsf').read_text())
        changed=[name for name,pin in old['source_sha256'].items() if new['source_sha256'][name]!=pin]
        self.assertEqual(len(changed),1);self.assertTrue(changed[0].startswith('genefer_stream28_merged_ct_'))
        self.assertEqual(set(new['source_sha256'])-set(old['source_sha256']),{leaf})

    def test_actual_standing_tickets_are_field_only_with_real_native_binding(self):
        tickets=[]
        for name in ('parent','candidate'):
            path=p.ROOT/f'queue/standing-fits/tickets/s4-l3b-ct-composed-field-{name}-f0-v1.json'
            tickets.append(json.loads(path.read_text()))
        for ticket in tickets:
            self.assertEqual(ticket['scope'],'component_probe')
            self.assertEqual(ticket['purpose'],'p16_diet')
            self.assertEqual(ticket['slot_shapes'],dict(aws6=['a','b']))
            self.assertEqual(ticket['source_contract'],dict(exemption='component_sizing_probe'))
            self.assertEqual(ticket['mode'],'full')
        self.assertEqual(tickets[0]['native_source_gate'],p.PARENT_GATE)
        self.assertEqual(tickets[1]['native_source_gate'],p.CT_GATE)
        self.assertEqual(tickets[0]['settings'],tickets[1]['settings'])


if __name__=='__main__':unittest.main()
