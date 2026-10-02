"""Fixed-wide reservations reference existing pairs; no native/transport work."""
import copy
import json
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import patch
from fpga.tools import global_queue_v1 as q


class FixedPlacementTests(unittest.TestCase):
    def setUp(self):
        self.host=q.load_host(q.FPGA/'queue/hosts/azure-f32-q2.json')
        self.host['enabled']=True  # Isolated scheduling fixture; live host may be user-stopped.
        self.host['wide_intake_enabled']=True
        self.host['observed_mem_available_bytes']=64*(1<<30)
        self.wide=self.host['fixed_placements'][0]
        self.observation=dict(free_lanes=[l['id'] for l in self.host['lanes']])

    def test_one_view_not_duplicated_physical_inventory(self):
        self.assertEqual(len(self.host['lanes']),8)
        self.assertEqual(len(q.placement_views(self.host)),10)
        first,second=self.host['fixed_placements']
        self.assertEqual(first['cpus'],list(range(8)))
        self.assertEqual(second['cpus'],list(range(8,16)))
        self.assertFalse(set(first['physical_locks'])&set(second['physical_locks']))
        self.assertEqual(q.placement_members(second),[l['id'] for l in self.host['lanes'][4:]])
        self.assertEqual(self.wide['cpus'],list(range(8)))
        self.assertEqual(len(set(self.wide['physical_locks'])),8)
        self.assertEqual(q.placement_members(self.wide),[l['id'] for l in self.host['lanes'][:4]])

    def test_any_constituent_claim_blocks_wide_but_not_other_pairs(self):
        own=dict(id='wide',dispatch=dict(host=self.host['name'],lane=self.wide['id'],
                 lane_ids=q.placement_members(self.wide),phase='launch_sent',observation_uncertain=True))
        self.assertTrue(q.placement_free(self.host,self.wide,self.observation,[]))
        self.assertFalse(q.placement_free(self.host,self.wide,self.observation,[own]))
        for lane in self.host['lanes'][:4]:
            self.assertFalse(q.placement_free(self.host,lane,self.observation,[own]))
        for lane in self.host['lanes'][4:]:
            self.assertTrue(q.placement_free(self.host,lane,self.observation,[own]))
        partial=dict(id='ordinary',dispatch=dict(host=self.host['name'],lane=self.host['lanes'][1]['id']))
        self.assertFalse(q.placement_free(self.host,self.wide,self.observation,[partial]))

    def test_missing_fresh_physical_lock_observation_blocks_entire_view(self):
        observation=copy.deepcopy(self.observation);observation['free_lanes'].remove(self.wide['lane_ids'][2])
        self.assertFalse(q.placement_free(self.host,self.wide,observation,[]))

    def test_exact_immutable_package_placement_required(self):
        ticket=dict(resources=dict(cores=8,threads=2,ram_gib=8,scratch_gib=4),tool_identity=self.host['tool_identity'],
            package=dict(profile='azure-burst16-thread-wide07-v1',runner='tools/native_threaded_wide_package_v3.py',placement=dict(
                id=self.wide['id'],lane_ids=self.wide['lane_ids'],cpus=self.wide['cpus'])))
        self.assertEqual(len(q.matching_packages(ticket,self.host,self.wide)),1)
        self.assertEqual(q.matching_packages(ticket,self.host,self.host['lanes'][0]),[])
        ticket['package']['placement']['cpus']=list(range(2))
        self.assertEqual(q.matching_packages(ticket,self.host,self.wide),[])

    def test_restart_resolves_all_constituents_and_rejects_drift(self):
        ticket=dict(dispatch=dict(host=self.host['name'],lane=self.wide['id'],lane_ids=self.wide['lane_ids']))
        self.assertEqual(q.dispatch_placement(ticket,self.host)['cpus'],list(range(8)))
        ticket['dispatch']['lane_ids']=self.wide['lane_ids'][:1]
        with self.assertRaisesRegex(ValueError,'immutable constituent'):q.dispatch_placement(ticket,self.host)

    def test_optional_overlay_error_never_disables_ordinary_lanes(self):
        with patch.object(q,'add_fixed_placements',side_effect=ValueError('test invalid experimental profile')):
            host=q.load_host(q.FPGA/'queue/hosts/azure-f32-q2.json')
        self.assertEqual(len(host['lanes']),8)
        self.assertEqual(host['fixed_placements'],[])
        self.assertIn('experimental profile',host['placement_errors'][0])

    def test_intake_hold_applies_only_to_wide_not_inventory_or_claim_resolution(self):
        self.host['wide_intake_enabled']=False
        with patch.object(q,'dependency_state',return_value=(False,'independent fixture dependency')):
            self.assertIn('fixed-wide intake',q.eligible({},self.host,self.wide)[1])
            self.assertEqual(q.eligible({},self.host,self.host['lanes'][4]),(False,'independent fixture dependency'))
            self.host['wide_intake_enabled']=True
            self.assertEqual(q.eligible({},self.host,self.wide),(False,'independent fixture dependency'))
        ticket=dict(dispatch=dict(host=self.host['name'],lane=self.wide['id'],lane_ids=self.wide['lane_ids']))
        self.host['wide_intake_enabled']=False
        self.assertEqual(q.dispatch_placement(ticket,self.host)['cpus'],list(range(8)))

    def test_actual_consumer_registry_required_only_for_new_wide_family(self):
        wide=dict(package=dict(runner=q.CONSUMER_CONTRACT['fixed_wide_runner']))
        ordinary=dict(package=dict(runner='tools/native_class_package_v2.py'))
        with tempfile.TemporaryDirectory() as directory,patch.object(q,'QUEUE',Path(directory)):
            q.require_consumer_adoption(ordinary)
            with self.assertRaisesRegex(ValueError,'actual running consumer'):
                q.require_consumer_adoption(wide)
            state=Path(directory)/'loop-state.json'
            state.write_text(json.dumps(dict(status='running',consumer_contract=q.CONSUMER_CONTRACT)))
            q.require_consumer_adoption(wide)
            state.write_text(json.dumps(dict(status='stopped_control_or_bound',consumer_contract=q.CONSUMER_CONTRACT)))
            with self.assertRaisesRegex(ValueError,'actual running consumer'):
                q.require_consumer_adoption(wide)

    def test_wide_start_is_one_bounded800percent_unit_after_persisted_full_claim(self):
        ticket=dict(id='wide-fixture',resources=dict(cores=8,threads=2,ram_gib=8,scratch_gib=4),
            package=dict(native_root='/fixture/native-wide',max_seconds=3700),dispatch=dict(
                host=self.host['name'],lane=self.wide['id'],lane_ids=self.wide['lane_ids'],unit='fixture-wide.service',phase='staged'))
        events=[]
        def persisted(path,value):events.append(('persist',value['dispatch']['phase'],list(q.claimed_lanes(value))))
        def sent(host,code,directory,name):events.append(('send',shlex.split(code)));return dict(returncode=0)
        with patch.object(q,'atomic',side_effect=persisted),patch.object(q,'ssh',side_effect=sent):
            q.start_worker(ticket,self.host,self.wide,Path('/fixture/evidence'),['fixture-worker'],'/fixture/source')
        self.assertEqual(events[0],('persist','launch_sent',self.wide['lane_ids']))
        sent_events=[event for event in events if event[0]=='send']
        self.assertEqual(len(sent_events),1)
        argv=sent_events[0][1]
        for value in ('AllowedCPUs=0,1,2,3,4,5,6,7','CPUQuota=800%','MemoryMax=8589934592',
                      'MemorySwapMax=0','RuntimeMaxSec=3700','TimeoutStopSec=15','KillMode=control-group'):
            self.assertIn('--property='+value,argv)

    def test_source_closed_wide_pilot_uses_normal_priority_enum(self):
        # Retained never-launched C2 input is only a real closed packaging
        # fixture here, not numerical qualification or permission to resume it.
        original=json.loads((q.FPGA/'queue/done/s4-p16-c2-own100-threadpilot-q1-v1.json').read_text())
        identity=q.expected_identity(original)
        for priority in ('P0','P1','P2','P3'):
            with self.subTest(priority=priority):
                ticket=copy.deepcopy(original);ticket['priority']=priority
                q.validate(ticket)
                self.assertEqual(q.expected_identity(ticket),identity)
        for priority in ('P4','p1',1,None):
            with self.subTest(priority=priority):
                ticket=copy.deepcopy(original);ticket['priority']=priority
                with self.assertRaisesRegex(ValueError,'owner/priority'):
                    q.validate(ticket)
        self.assertEqual(original['result']['status'],'superseded_pending_never_launched')

    def test_wide_primary_priority_never_relaxes_resource_or_source_closure(self):
        original=json.loads((q.FPGA/'queue/done/s4-p16-c2-own100-threadpilot-q1-v1.json').read_text())
        mutations=(('resources',dict(cores=2,threads=1,ram_gib=8,scratch_gib=4)),
                   ('resources',dict(cores=8,threads=8,ram_gib=16,scratch_gib=4)))
        for field,value in mutations:
            ticket=copy.deepcopy(original);ticket['priority']='P1';ticket[field]=value
            with self.subTest(resources=value),self.assertRaisesRegex(ValueError,'bounded matched'):
                q.validate(ticket)
        ticket=copy.deepcopy(original);ticket['priority']='P1'
        q.packages(ticket)[0]['runner_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'closed runner pin'):
            q.validate(ticket)

    def test_actual_public_pending_priority_update_preserves_role_events_and_identity(self):
        original=json.loads((q.FPGA/'queue/done/s4-p16-c2-own100-threadpilot-q1-v1.json').read_text())
        original.pop('result')  # Isolated replay of old intake, never live revival.
        predecessor=q.registry()[original['after'][0]['id']]
        desired=copy.deepcopy(original);desired['priority']='P1'
        identity=q.expected_identity(original)
        with tempfile.TemporaryDirectory() as directory,patch.object(q,'QUEUE',Path(directory)):
            root=Path(directory)
            for state in ('pending','running','done'):(root/state).mkdir()
            q.atomic(root/'loop-state.json',dict(status='running',consumer_contract=q.CONSUMER_CONTRACT))
            q.atomic(root/'done'/(predecessor['id']+'.json'),predecessor)
            q.atomic(root/'pending'/(original['id']+'.json'),original)
            input_path=root/'input.json';q.atomic(input_path,desired)
            self.assertEqual(q.update_pending(input_path)['status'],'pending_updated')
            accepted=json.loads((root/'pending'/(original['id']+'.json')).read_text())
            self.assertEqual(accepted,desired)
            self.assertEqual(q.expected_identity(accepted),identity)
            preserved=list((root/'superseded'/original['id']).glob('*.json'))
            self.assertEqual(len(preserved),1)
            self.assertEqual(json.loads(preserved[0].read_text()),original)

    def test_ready_primary_wide_defers_only_lower_priority_intersecting_backfill(self):
        waiting=dict(id='primary-wide',priority='P1',created='2026-10-02T02:47:00Z')
        backfill=dict(id='backfill',priority='P3',created='2026-10-02T02:48:00Z')
        second=self.host['fixed_placements'][1]
        active=dict(id='active-unchanged',dispatch=dict(host=self.host['name'],lane=second['lane_ids'][1]))
        before=copy.deepcopy(active)
        def ready(ticket,host,lane):return (lane['id']==second['id'],'fixture source/dep eligible')
        selected=dict(max_seconds=3700)
        with patch.object(q,'eligible',side_effect=ready),patch.object(q,'validate'),\
                patch.object(q,'validate_infra_retry'),patch.object(q,'registry',return_value={}),\
                patch.object(q,'matching_packages',return_value=[selected]),patch.object(q,'budget') as budget:
            for lane in self.host['lanes'][4:]:
                self.assertEqual(q.waiting_wide_blocker(backfill,self.host,lane,self.observation,[waiting,backfill],[active]),waiting['id'])
            for lane in self.host['lanes'][:4]:
                self.assertIsNone(q.waiting_wide_blocker(backfill,self.host,lane,self.observation,[waiting,backfill],[active]))
            for priority in ('P0','P1'):
                other=dict(backfill,priority=priority)
                self.assertIsNone(q.waiting_wide_blocker(other,self.host,self.host['lanes'][4],self.observation,[waiting,other],[active]))
            self.assertEqual(active,before)
            budget.assert_called_with(self.host,3715,None,selected)

    def test_fixed_group_deferral_clears_on_free_group_or_removed_pending_job(self):
        waiting=dict(id='primary-wide',priority='P1',created='2026-10-02T02:47:00Z')
        backfill=dict(id='backfill',priority='P3',created='2026-10-02T02:48:00Z')
        lane=self.host['lanes'][4]
        with patch.object(q,'eligible') as eligible:
            self.assertIsNone(q.waiting_wide_blocker(backfill,self.host,lane,self.observation,[waiting,backfill],[]))
            self.assertIsNone(q.waiting_wide_blocker(backfill,self.host,lane,self.observation,[backfill],[]))
            eligible.assert_not_called()

    def test_blocked_dependency_source_or_budget_cannot_protect_fixed_group(self):
        waiting=dict(id='primary-wide',priority='P1',created='2026-10-02T02:47:00Z')
        backfill=dict(id='backfill',priority='P3',created='2026-10-02T02:48:00Z')
        second=self.host['fixed_placements'][1];lane=self.host['lanes'][4]
        active=dict(id='active',dispatch=dict(host=self.host['name'],lane=second['lane_ids'][1]))
        def ready(ticket,host,view):return (view['id']==second['id'],'fixture source/dep eligible')
        with patch.object(q,'eligible',return_value=(False,'dependency waiting')),patch.object(q,'validate') as check:
            self.assertIsNone(q.waiting_wide_blocker(backfill,self.host,lane,self.observation,[waiting,backfill],[active]))
            check.assert_not_called()
        for guarded in ('validate','validate_infra_retry','budget'):
            with self.subTest(guard=guarded),patch.object(q,'eligible',side_effect=ready),\
                    patch.object(q,'validate'),patch.object(q,'validate_infra_retry'),\
                    patch.object(q,'registry',return_value={}),patch.object(q,'matching_packages',return_value=[dict(max_seconds=3700)]),\
                    patch.object(q,'budget'),patch.object(q,guarded,side_effect=ValueError('actual block')):
                self.assertIsNone(q.waiting_wide_blocker(backfill,self.host,lane,self.observation,[waiting,backfill],[active]))

    def test_actual_tick_never_refills_occupied_primary_group_with_backfill(self):
        second=self.host['fixed_placements'][1]
        waiting=dict(id='primary-wide',priority='P1',created='2026-10-02T02:47:00Z',
                     tool_identity='fixture',resources=dict(cores=8,threads=8,ram_gib=8,scratch_gib=4))
        backfill=dict(id='backfill',priority='P3',created='2026-10-02T02:48:00Z',
                      tool_identity='fixture',resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4))
        active=dict(id='active',priority='P3',created='2026-10-02T02:46:00Z',
                    dispatch=dict(host=self.host['name'],lane=second['lane_ids'][1],phase='observed'))
        observation=dict(self.observation,mem_available_bytes=64*(1<<30))
        observation['free_lanes']=[x for x in observation['free_lanes'] if x!=active['dispatch']['lane']]
        def ready(ticket,host,lane):
            return (lane['id']==second['id'] if ticket['id']==waiting['id'] else not lane.get('lane_ids'),'fixture eligible')
        selected=dict(profile='fixture',worker_id='fixture-backfill',max_seconds=3700,ticket_sha256='a'*64)
        with tempfile.TemporaryDirectory() as directory,patch.object(q,'QUEUE',Path(directory)):
            root=Path(directory)
            for state in ('pending','running','done'):(root/state).mkdir()
            q.atomic(root/'pending/primary-wide.json',waiting);q.atomic(root/'pending/backfill.json',backfill)
            q.atomic(root/'running/active.json',active)
            with patch.object(q,'refresh_costs_async'),patch.object(q,'poll'),patch.object(q,'reconcile_dependencies'),\
                    patch.object(q,'automatic_variants'),patch.object(q,'probe',return_value=observation),\
                    patch.object(q,'ssh',return_value={'returncode':0}),patch.object(q,'output'),\
                    patch.object(q,'eligible',side_effect=ready),patch.object(q,'validate'),patch.object(q,'validate_infra_retry'),\
                    patch.object(q,'matching_packages',return_value=[selected]),patch.object(q,'budget'),\
                    patch.object(q,'functional_identity',return_value='b'*64),patch.object(q,'memory_admit'),\
                    patch.object(q,'launch'),patch.object(q,'status'):
                q.tick([self.host])
            claimed=json.loads((root/'running/backfill.json').read_text())
            self.assertFalse(set(q.claimed_lanes(claimed))&set(second['lane_ids']))
            self.assertTrue((root/'pending/primary-wide.json').exists())
            self.assertEqual(json.loads((root/'running/active.json').read_text()),active)

    def test_own_pilot_allocation_is_captured_authority_not_optional_queue_mirror(self):
        pilot=json.loads((q.FPGA/'queue/done/s4-p16-c2-explicit-own100-threadpilot-q2-v1.json').read_text())
        self.assertNotIn('fixed_execution',pilot['package'])
        execution=q.captured_pilot_execution(pilot)
        self.assertEqual(execution['runtime_allocation']['cpus'],list(range(8,16)))
        self.assertEqual(execution['runtime_allocation']['cpu_quota_percent'],800)
        self.assertEqual(execution['runtime_allocation']['memory_bytes'],8<<30)
        for field in ('sha256','manifest_sha256','ticket_sha256'):
            wrong=copy.deepcopy(pilot);wrong['package'][field]='0'*64
            with self.subTest(drift=field),self.assertRaisesRegex(ValueError,'own.*allocation'):
                q.captured_pilot_execution(wrong)
        wrong=copy.deepcopy(pilot);wrong['dependency_gate']['manifest_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'own typed pilot'):
            q.captured_pilot_execution(wrong)
        wrong=copy.deepcopy(pilot);wrong['package']['fixed_execution']=dict(execution,placement={})
        with self.assertRaisesRegex(ValueError,'optional pilot allocation mirror'):
            q.captured_pilot_execution(wrong)


if __name__=='__main__':unittest.main()
