"""Fault-source closure and honest scope only; native tests are remote."""
import unittest
from fpga.reference import stream27_protected_relay13_full_fault as full
from fpga.reference import stream27_protected_relay13_full_early_cache as cache
from fpga.reference import stream27_protected_relay13_crosstalk as cross

class ProtectedRelay13FaultMetadataTests(unittest.TestCase):
    def test_full_contracts_keep_production_and_count2_reset_scope(self):
        m,f=full.role('contracts');scope=m['protected_relay13_full_fault']
        self.assertEqual(len(m['build']['sv_sources']),59)
        self.assertEqual(m['build']['parameters']['CRT_TRANSPORT_REG'],0)
        self.assertEqual(scope['original_interval'],8464)
        self.assertTrue(scope['production_rtl_unchanged'])
        self.assertTrue(scope['full_count2_reset_does_not_epoch_wrap'])
        self.assertFalse(scope['shared_fault_peer_recovery'])
        self.assertIn('epoch_wrap=0',f[full.CPP].decode())
        self.assertEqual(m['steps'][-1]['expected_returncode'],1)

    def test_cache_retains_shared_F1_F2_leaf_and_only_F0_probe(self):
        original,old=full.role('contracts');m,f=cache.role()
        shared='rtl/'+cache.TERM+'.sv'
        self.assertIn(shared,m['build']['sv_sources'])
        self.assertEqual(f[shared],old[shared])
        delta=m['protected_relay13_full_fault']['diagnostic_rtl_delta']
        self.assertEqual(len(m['build']['sv_sources']),60)
        self.assertEqual(len(delta),2)
        self.assertTrue(m['protected_relay13_full_fault']['eventual_duplicate_abort_only'])
        self.assertTrue(m['protected_relay13_full_fault']['origin_age_validation_not_proved'])
        self.assertTrue(all(f[n]==old[n] for n in original['build']['sv_sources'] if n not in delta))

    def test_crosstalk_is_stateless_output_only(self):
        m,f=cross.role()
        text=f['rtl/'+m['build']['top']+'.sv'].decode()
        self.assertNotIn('always',text)
        self.assertIn("native_read_data ^ 96'd1",text)
        self.assertTrue(m['relay13_crosstalk']['no_RAM_or_configuration_fault_claim'])
        self.assertEqual(len(m['build']['sv_sources']),59)

if __name__=='__main__':unittest.main()
