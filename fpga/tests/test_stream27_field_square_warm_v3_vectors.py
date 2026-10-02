import unittest
from fpga.reference.stream27_field_square_warm_v3_vectors import corpus


class WarmIndependentCalendar(unittest.TestCase):
    def test_overlap_late_admission_deadline_and_reset(self):
        text,meta=corpus();rows=[list(map(int,line.split())) for line in text.splitlines()[1:]]
        cases={entry['name']:rows[entry['first_event']:entry['first_event']+entry['events']] for entry in meta['cases']}
        self.assertEqual(meta['peak_owners'],2)
        for name in ('two-owner-start20','two-owner-start4','crossed-old-correction-new-base','epoch-wrap'):
            data=cases[name]
            self.assertFalse(any(row[35] for row in data),name)
            self.assertEqual(max(row[62] for row in data),2,name)
            self.assertEqual(sum(row[32] for row in data),8,name)
            self.assertEqual(sum(row[45] for row in data),8,name)
        crossed=cases['crossed-old-correction-new-base'][5]
        self.assertEqual((crossed[56],crossed[58],crossed[63],crossed[64]),(1,0,1,1))
        self.assertFalse(any(row[35] for row in cases['latest-correction']))
        for name in ('same-edge-cache-deadline','missing-correction'):
            self.assertEqual(next(i for i,row in enumerate(cases[name]) if row[35]),44)
        self.assertTrue(any(row[35] for row in cases['correction-spacing3']))
        self.assertTrue(any(row[35] for row in cases['third-owner-overflow']))
        self.assertEqual(sum(row[32] for row in cases['cancel0']),8)
        self.assertEqual(sum(row[45] for row in cases['cancel0']),0)
        for age in range(114):
            data=cases[f'reset{age}']
            self.assertEqual(data[age+1][62],0)
            self.assertEqual(sum(row[32] for row in data if row[60]==4321),4)
        for name,data in cases.items():
            if name.startswith('fault-'):self.assertTrue(any(row[35] for row in data),name)


if __name__=='__main__':unittest.main()
