import unittest
from synthesis.ntt_ram_placement import summarize


HEADER=['Name','Type','Port A Depth','Port A Width','Implementation Port A Depth',
        'Implementation Port A Width','Implementation Bits','M20K blocks','Location']
def table(rows):
    return '\n'.join('; '+' ; '.join(x)+' ;' for x in [['Fitter RAM Summary'],HEADER]+rows)
def ram(kind='data',width='32',locations='M20K_X8_Y10_N0, M20K_X20_Y30_N0'):
    return [f'field_lane[1].engine|child|memories[2].{kind}_ram|auto','M20K','1024',width,
            '1024',width,str(1024*int(width)),'2.000',locations]


class RamPlacementTests(unittest.TestCase):
    def test_coordinate_span_is_only_descriptive(self):
        r=summarize(table([ram(),ram('middle','27')]))
        self.assertEqual(r['ram_count'],2)
        self.assertEqual(r['rams'][0]['bounds'],[8,10,20,30])
        self.assertEqual(r['groups'][0]['max_per_bank_grid_span'],32)
        self.assertFalse(r['physical_locality_improvement_proven'])
        self.assertEqual(r['groups'][1]['physical_widths'],[27])

    def test_bad_locations_counts_or_duplicates_fail(self):
        for locations in ('','unknown','M20K_X8_Y10_N0','M20K_X8_Y10_N0, M20K_X8_Y10_N0'):
            with self.assertRaises(ValueError):summarize(table([ram(locations=locations)]))
        with self.assertRaises(ValueError):summarize(table([ram(),ram()]))

    def test_unrelated_memory_is_not_ntt(self):
        other=ram();other[0]='carry_unit|ram'
        with self.assertRaises(ValueError):summarize(table([other]))

    def test_standalone_and_direct_field_scopes(self):
        a=ram();a[0]='memories[0].data_ram|auto'
        b=ram();b[0]='field_lane[2].engine|memories[1].data_ram|auto'
        r=summarize(table([a,b]))
        self.assertEqual([x['field'] for x in r['rams']],[None,2])

    def test_missing_or_ambiguous_table_rejected(self):
        for text in ('',table([]),table([ram()])+'\n'+table([ram('post')])):
            with self.assertRaises(ValueError):summarize(text)


if __name__=='__main__':unittest.main()
