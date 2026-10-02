import unittest
from fpga.reference import stream27_host_core_v1 as parent
from fpga.reference import stream27_host_core_v2 as current


class CurrentHostPublication(unittest.TestCase):
    def test_only_root_publication_changes(self):
        for n in (32,256):
            a=parent.prepare(n);b=current.prepare(n)
            self.assertEqual(a['cycle_contract'],b['cycle_contract'])
            for name,text in a['files'].items():
                if name!=a['top']+'.sv':self.assertEqual(b['files'][name],text)
            s=b['files'][b['top']+'.sv']
            self.assertIn('state==IDLE && image_published && child_ready && !error',s)
            self.assertIn('if(state==IDLE && !start && load_we && !error)image_published<=0;',s)
            self.assertIn('COPY_DRAIN:begin state<=IDLE;done<=1;image_published<=1;',s)


if __name__=='__main__':unittest.main()
