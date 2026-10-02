from datetime import datetime,timezone
import unittest
from cloud.manual_status import summarize


class ManualCloudStatusTests(unittest.TestCase):
    def setUp(self):
        self.plan={"workers":[{"name":"worker","id":"123","zone":"zone"}],"approved_pilot_budget_usd":30}
        self.instance={"name":"worker","id":"123","creationTimestamp":"2026-09-30T01:00:00Z",
                       "status":"RUNNING","scheduling":{},"disks":[{"boot":True,"autoDelete":True,"diskSizeGb":"200"}]}

    def test_estimate_is_not_billing_or_automatic_action(self):
        result=summarize(self.plan,self.instance,datetime(2026,9,30,3,tzinfo=timezone.utc))
        self.assertEqual(result["estimated_lifetime_cost_usd"],1.5)
        self.assertEqual(result["remaining_planning_allowance_usd"],25.5)
        self.assertFalse(result["actual_billing_verified"])
        self.assertFalse(result["hard_billing_cap"])
        self.assertIsNone(result["runtime_limit"])
        self.assertEqual(result["action"],"read_only_no_background_guard_no_stop_no_deletion")

    def test_budget_threshold_only_reports(self):
        result=summarize(self.plan,self.instance,datetime(2026,10,1,13,tzinfo=timezone.utc))
        self.assertTrue(result["budget_action_needed"])
        self.assertEqual(result["remaining_planning_allowance_usd"],0)
        self.assertIn("read_only",result["action"])

    def test_different_instance_or_clock_is_rejected(self):
        with self.assertRaises(ValueError):summarize(self.plan,{**self.instance,"id":"124"},datetime.now(timezone.utc))
        with self.assertRaises(ValueError):summarize(self.plan,self.instance,datetime(2026,9,29,tzinfo=timezone.utc))
