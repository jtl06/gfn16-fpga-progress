import unittest
from fpga.reference.stream27_field_square_vectors import corpus, FIRST_OUTPUT, NEXT_FRAME


class FieldSquareCalendar(unittest.TestCase):
    def test_schema_physical_cancellation_reset_and_sink_race(self):
        text,metadata=corpus();rows=[list(map(int,line.split())) for line in text.splitlines()[1:]]
        self.assertEqual(len(rows),metadata['events'])
        self.assertTrue(all(len(row)==56 for row in rows))
        cases={case['name']:rows[case['first_event']:case['first_event']+case['events']] for case in metadata['cases']}
        normal=cases['b1000000000-signed-boundaries']
        self.assertEqual([i for i,row in enumerate(normal) if row[32]],list(range(FIRST_OUTPUT+1,FIRST_OUTPUT+5)))
        killed=cases['cancel0']
        self.assertEqual(sum(row[32] for row in killed),4)
        self.assertEqual(sum(row[45] for row in killed),0)
        between=cases['cancel88']
        self.assertTrue(between[88][34])  # output87 was advisory eligible
        self.assertFalse(between[89][45]) # consuming edge88 sees new generation
        for age in range(94):
            case=cases[f'reset{age}']
            self.assertFalse(case[age+1][32] or case[age+1][45])
            self.assertEqual(sum(row[32] for row in case if row[36]==200),4)
        coherent=cases['coherent-reload-gap0']
        self.assertFalse(any(row[35] for row in coherent))
        self.assertEqual(sum(row[32] for row in coherent),8)
        self.assertTrue(coherent[NEXT_FRAME+1][2])
        for name,case in cases.items():
            if name.startswith('fault-'):
                self.assertTrue(any(row[35] for row in case),name)


if __name__=='__main__':unittest.main()
