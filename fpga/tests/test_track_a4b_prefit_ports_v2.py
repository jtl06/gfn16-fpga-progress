"""Source-port consistency only; no mapped-netlist or timing claim."""
import copy
import json
from pathlib import Path
import re
import unittest
from fpga.tools.prefit_structural_guard_v1 import source_inventory

FPGA = Path(__file__).resolve().parents[1]
ROOT = FPGA/'results/throughput-20260929/track-a4b-prefit-source-v1/project'
SPEC = FPGA/'results/throughput-20260929/track-a4b-prefit-source-v2/inventory.json'


def check(spec):
    result = source_inventory(ROOT, spec)
    if result['findings']:
        raise ValueError('unjustified source transfer')
    text = (ROOT/'rtl/genefer_track_a4_core_v4.sv').read_text()
    declared = set()
    for match in re.finditer(r'^    logic (.*);$', text, re.M):
        body = re.sub(r'\[[^]]+\]', '', match[1]).strip()
        declared.update(part.strip() for part in body.split(','))
    mapped = spec['core_internal_port_groups']
    if set(mapped) | set(spec['source_only_unused_core_wires']) != declared:
        raise ValueError('all declared core internal port wires must be mapped')
    transfers = {item['id']: item for item in spec['transfers']}
    if any(name not in transfers[group]['signals'] for name, group in mapped.items()):
        raise ValueError('mapping must name actual declared transfer signal')
    if spec['source_only_unused_core_wires'] != ['square_busy']:
        raise ValueError('only exact unused square_busy wire exclusion')
    return result


class A4bPortInventory(unittest.TestCase):
    def test_exact_inventory(self):
        result = check(json.loads(SPEC.read_text()))
        self.assertEqual(len(result['transfers']), 25)
        self.assertEqual(len(result['stage_ids']), 19)

    def test_omitted_port_and_unjustified_control_fail(self):
        base = json.loads(SPEC.read_text())
        for name in base['core_internal_port_groups']:
            changed = copy.deepcopy(base)
            del changed['core_internal_port_groups'][name]
            with self.assertRaises(ValueError): check(changed)
        changed = copy.deepcopy(base)
        transfer = next(t for t in changed['transfers'] if t['id']=='field_protocol_rejection')
        del transfer['exception']
        with self.assertRaises(ValueError): check(changed)


if __name__ == '__main__': unittest.main()
