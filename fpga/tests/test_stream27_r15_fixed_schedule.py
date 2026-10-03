import unittest
from reference import stream27_r15_fixed_schedule_bind as bind
from reference import stream27_r15_fixed_schedule_model as model


class FixedSchedule(unittest.TestCase):
    def test_disabled_exact_and_source(self):
        for n in (256,65536):
            parent=bind.capture(n)
            self.assertEqual(bind.bind(parent,0),parent)
            child=bind.bind(parent,1)
            self.assertEqual(child['geometry'],parent['geometry'])
            self.assertEqual(len(child['files']),58)
            self.assertEqual(child['parameters']['FIXED_SCHEDULE'],1)
            changed=sum(child['generated_sha256'].get(name)!=value for name,value in parent['generated_sha256'].items())
            self.assertEqual(changed,2)
            self.assertIn('r15_calendar_bad',child['files'][next(k for k in child['files'] if 'warm_contexts_' in k)])

    def test_actual_phase_clock_and_tail(self):
        for n in (256,65536):
            g=bind.capture(n)['geometry'];i,r,b=model.constants(g)
            c=model.Calendar(i,r,b);remaining=2;enabled=False
            c.edge(cold_accept=True)
            observed=[]
            for age in range(1,3*i+r+1):
                if age in (g['first_digit']+1,i+g['first_digit']+1,2*i+g['first_digit']+1):
                    enabled=remaining!=0
                f,s,a=c.proposal(active=True,remaining=remaining,feedback_enabled=enabled)
                expected=any(k*i-1<=age<k*i-1+r for k in (1,2))
                self.assertEqual(f,expected,(n,age))
                self.assertEqual(s,age in (i-1,2*i-1))
                self.assertEqual(a,age in (b,i+b))
                if age in (i,2*i):remaining-=1
                c.edge(active=True,remaining=remaining)
                if f:observed.append(age)
            self.assertEqual(len(observed),2*r)
            c.edge(reset=True)
            self.assertEqual(c.proposal(active=False,remaining=0,feedback_enabled=False),(False,False,False))

    def test_descriptor_and_fault_priority(self):
        # No external idle advances the unarmed calendar. At the required
        # proposal edge missing descriptor remains an old framing fault.
        c=model.Calendar(215,16,214)
        for _ in range(10000):c.edge()
        self.assertFalse(c.armed)
        c.edge(cold_accept=True)
        for _ in range(213):c.edge(active=True,remaining=1)
        self.assertEqual(c.proposal(active=True,remaining=1,feedback_enabled=True),(True,True,True))
        command_valid=False
        self.assertTrue(c.proposal(active=True,remaining=1,feedback_enabled=True)[1] and not command_valid)
        self.assertEqual(c.proposal(active=True,remaining=1,feedback_enabled=True,local_error=True),(False,False,False))


if __name__=='__main__':unittest.main()
