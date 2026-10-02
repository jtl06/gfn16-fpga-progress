"""Synthetic protocol fixtures only: no tiled fit exists at test creation."""
from pathlib import Path
import shutil
import subprocess
import unittest
from synthesis.tiled_control_audit import summarize, coordinates


def fixture(lanes=64):
    kw=(2*lanes-1).bit_length()
    widths={'pairing_e':(kw-1).bit_length(), 'orientation_e':1,
            'folded_root_bank_d':kw, 'rotation_d':(kw-1).bit_length()}
    rows=['TILE_AUDIT\tBEGIN\t1\t*control_tiles*']
    for tile in range(lanes//8):
        for family,width in widths.items():
            for bit in range(width):
                ident=f'{tile}-{family}-{bit}'
                name=f'synthetic|control_tiles[{tile}].{family}[{bit}]'
                rows.append(f'TILE_AUDIT\tREG\t{ident}\t{name}\tFF_X{tile}_Y2_N0')
    rows.append('TILE_AUDIT\tEND\t1')
    return '\n'.join(rows)


class TiledAudit(unittest.TestCase):
    def test_folded_global_baseline_is_not_eight_tiles(self):
        lines=fixture().splitlines()
        text='\n'.join(x.replace('control_tiles[0].','') for x in lines
                       if x.startswith('TILE_AUDIT\tBEGIN') or x.startswith('TILE_AUDIT\tEND')
                       or 'control_tiles[0].' in x)
        result=summarize(text,64,'folded')
        self.assertEqual(result['expected_control_bits'],14)
        self.assertTrue(result['logical_bit_presence_complete'])
        self.assertFalse(result['physical_locality_proven'])
        self.assertFalse(summarize(text,64)['logical_bit_presence_complete'])
        with self.assertRaises(ValueError):summarize(text,64,'other')

    def test_complete_does_not_claim_physical_success(self):
        for lanes,bits in [(16,24),(64,112)]:
            report=summarize(fixture(lanes),lanes)
            self.assertEqual(report['expected_control_bits'],bits)
            self.assertTrue(report['logical_bit_presence_complete'])
            for field in ('physical_locality_proven','timing_closure_proven',
                          'capture_fit_provenance_verified'):
                self.assertFalse(report[field])

    def test_missing_and_empty(self):
        text=fixture().replace('TILE_AUDIT\tREG\t0-pairing_e-0', 'IGNORED\tREG\t0-pairing_e-0')
        self.assertEqual(summarize(text,64)['missing_bits'],[[0,'pairing_e',0]])
        self.assertEqual(len(summarize('TILE_AUDIT\tBEGIN\t1\tx\nTILE_AUDIT\tEND\t1',64)['missing_bits']),112)

    def test_truncated_unknown_and_duplicate(self):
        for text in (fixture().rsplit('\n',1)[0],fixture()+'\nTILE_AUDIT\tREG\tx\tx\tx',
                     fixture().replace('TILE_AUDIT\tEND\t1','TILE_AUDIT\tBAD'),
                     fixture().replace('TILE_AUDIT\tEND\t1','TILE_AUDIT\tBEGIN\t1\tx')):
            with self.assertRaises(ValueError): summarize(text,64)
        row=fixture().splitlines()[1]
        with self.assertRaises(ValueError):summarize(fixture().replace('TILE_AUDIT\tEND',row+'\nTILE_AUDIT\tEND'),64)

    def test_endpoint_and_edge_counts_are_distinct(self):
        rows='TILE_AUDIT\tEDGE\t0-pairing_e-0\te\tcomb_mux\tcomb\tCOMB_X0_Y2_N1\n'
        rows+='TILE_AUDIT\tKEEPER\t0-pairing_e-0\tarithmetic[8].butterfly|pre_w[0]\treg\tFF_X10_Y2_N0\n'
        result=summarize(fixture().replace('TILE_AUDIT\tEND',rows+'TILE_AUDIT\tEND'),64)
        self.assertEqual(len(result['nonlocal_pairing_endpoints']),1)
        self.assertEqual(result['registers'][0]['direct_edge_count'],1)
        self.assertEqual(result['registers'][0]['reachable_keeper_count'],1)
        self.assertIsNone(result['registers'][0]['output_pin_edge_count'])

    def test_output_pin_edges_are_separate_and_complete(self):
        rows='TILE_AUDIT\tQPIN\t0-pairing_e-0\tx|q\tFF_X0_Y2_N0\t1\n'
        rows+='TILE_AUDIT\tQEDGE\t0-pairing_e-0\te2\tmux|dataa\tpin\tCOMB_X10_Y2_N1\n'
        text=fixture().replace('TILE_AUDIT\tEND',rows+'TILE_AUDIT\tEND')
        r=summarize(text,64)['registers'][0]
        self.assertEqual(r['output_pin_edge_count'],1)
        self.assertEqual(r['direct_edge_count'],0)
        with self.assertRaisesRegex(ValueError,'Incomplete output-pin'):
            summarize(text.replace('TILE_AUDIT\tQEDGE','IGNORED\tQEDGE'),64)

    def test_duplicates_visible_and_multiple_scopes_rejected(self):
        row='TILE_AUDIT\tREG\ttoolcopy\tsynthetic|control_tiles[0].pairing_e[0]~DUPLICATE\tFF_X1_Y2_N0\n'
        result=summarize(fixture().replace('TILE_AUDIT\tEND',row+'TILE_AUDIT\tEND'),64)
        self.assertEqual(result['observed_registers'],113)
        self.assertTrue(result['logical_bit_presence_complete'])
        with self.assertRaises(ValueError):
            summarize(fixture().replace('synthetic|control_tiles[1]','other|control_tiles[1]'),64)

    def test_unknown_geometry_location_and_orphan(self):
        self.assertEqual(coordinates('FF_X30_Y4_N20'),[30,4])
        self.assertIsNone(coordinates('unknown'))
        self.assertFalse(summarize(fixture().replace('pairing_e','unrecognized'),64)['logical_bit_presence_complete'])
        with self.assertRaises(ValueError):summarize(fixture(),32)
        with self.assertRaises(ValueError):
            summarize(fixture().replace('TILE_AUDIT\tEND','TILE_AUDIT\tKEEPER\torphan\tx\treg\tloc\nTILE_AUDIT\tEND'),64)

    @unittest.skipUnless(shutil.which('tclsh'),'Tcl interpreter required for mocked exporter')
    def test_tcl_mock_only_no_quartus_or_netlist(self):
        source=Path(__file__).resolve().parents[1]/'synthesis/tiled_control_audit.tcl'
        # Fake command responses exercise Tcl syntax/serialization, not Quartus.
        script=r'''
proc get_registers {pattern} {return r}
proc get_node_info {option node} {
    if {$option eq "-name"} {
        if {$node eq "r"} {return {synthetic|control_tiles[0].orientation_e}}
        return {arithmetic[0].butterfly|pre_w[0]}
    }
    if {$option eq "-location"} {return FF_X1_Y2_N0}
    if {$option eq "-type"} {return reg}
    if {$option eq "-fanout_edges"} {return edge}
    error "unexpected query"
}
proc get_edge_info {option edge} {return dst}
proc get_fanouts {reg} {return dst}
proc foreach_in_collection {var items body} {uplevel 1 [list foreach $var $items $body]}
'''
        result=subprocess.run(['tclsh'],input=script+'\nsource {'+str(source)+'}\n',
                              text=True,capture_output=True,check=True)
        self.assertEqual(result.stderr,'')
        report=summarize(result.stdout,64)
        self.assertEqual(report['observed_registers'],1)
        self.assertEqual(report['registers'][0]['reachable_keeper_count'],1)


if __name__=='__main__':unittest.main()
