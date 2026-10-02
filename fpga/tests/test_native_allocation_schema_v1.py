import copy
import unittest
import tempfile
from pathlib import Path
from fpga.tools import native_allocation_schema_v1 as a


class AllocationTests(unittest.TestCase):
    def setUp(self):
        self.request=dict(cores=dict(min=1,max=4),threads=1,ram_gib=dict(base=1,per_core=.5),scratch_gib=4,est_minutes=3)
        self.topology={str(cpu):[0,cpu%4] for cpu in range(8)}
        self.limits=dict(max_physical_cores=4,max_memory_bytes=8*a.GIB,available_memory_bytes=16*a.GIB,
            memory_floor_bytes=4*a.GIB,available_scratch_bytes=32*a.GIB,scratch_floor_bytes=10*a.GIB)
        self.bindings=dict(worker_id='gcp-c4d',host='gfn16-pilot-c4d',reservation_epoch=1790842000,
            source_manifest_sha256='a'*64,base_build_key='b'*64,
            profile_sha256='c'*64,tool_sha256={'verilator':'d'*64,'compiler':'e'*64},topology=self.topology)
    def launch(self):return a.bind_allocation(self.request,physical_cores=[[0,0],[0,2]],limits=self.limits,**self.bindings)
    def validate(self,launch,**changes):
        bindings=dict(self.bindings,**changes)
        return a.validate_launch(launch,allocation_sha256=self.launch()['allocation_sha256'],request=self.request,**bindings)
    def test_smt_all_siblings_and_physical_quota(self):
        launch=self.launch();self.validate(launch)
        self.assertEqual(launch['allowed_cpus'],[0,2,4,6]);self.assertEqual(launch['compile_workers'],2)
        self.assertEqual(launch['memory_bytes'],2*a.GIB);self.assertEqual(launch['cpu_quota_percent'],200)
        self.assertTrue(a.check_runtime(launch,affinity=[0,2,4,6],topology=self.topology,memory_max_bytes=2*a.GIB,cpu_quota=200000,cpu_period=100000,swap_max_bytes=0))
    def test_source_profile_build_topology_mismatch(self):
        launch=self.launch()
        for name in ('source_manifest_sha256','base_build_key','profile_sha256'):
            with self.assertRaises(ValueError):self.validate(launch,**{name:'d'*64})
        for key,value in [('worker_id','other-worker'),('reservation_epoch',1790842001),('tool_sha256',{'verilator':'f'*64})]:
            with self.assertRaises(ValueError):self.validate(launch,**{key:value})
        changed=copy.deepcopy(self.topology);changed['4']=[0,3]
        with self.assertRaises(ValueError):self.validate(launch,topology=changed)
    def test_every_grant_field_is_immutable(self):
        for key,value in [('memory_bytes',3*a.GIB),('scratch_bytes',8*a.GIB),('compile_workers',4),('model_threads',2),('allowed_cpus',[0,2]),('cpu_quota_percent',400),('allocated_build_key','e'*64),('unexpected',True)]:
            changed=self.launch();changed[key]=value
            with self.assertRaises(ValueError):self.validate(changed)
    def test_rehashed_allocation_is_not_same_launch(self):
        different=a.bind_allocation(self.request,physical_cores=[[0,1],[0,3]],limits=self.limits,**self.bindings)
        with self.assertRaises(ValueError):self.validate(different)
    def test_core_and_resource_limits(self):
        for cores in ([[0,0],[0,0]],[[0,2],[0,0]],[[0,9]],[],[[False,0]]):
            with self.assertRaises(ValueError):a.bind_allocation(self.request,physical_cores=cores,limits=self.limits,**self.bindings)
        for key,value in [('max_physical_cores',1),('max_memory_bytes',a.GIB),('available_memory_bytes',5*a.GIB),('available_scratch_bytes',13*a.GIB)]:
            limits=dict(self.limits,**{key:value})
            with self.assertRaises(ValueError):a.bind_allocation(self.request,physical_cores=[[0,0],[0,2]],limits=limits,**self.bindings)
    def test_typed_requests_and_d3_remains_blocked(self):
        for key,value in [('cores',{'min':True,'max':4}),('threads',True),('scratch_gib',float('nan')),('ram_gib',{'base':-1,'per_core':1}),('est_minutes',0),('unknown',1)]:
            request=dict(self.request,**{key:value})
            with self.assertRaises(ValueError):a.validate_request(request)
        future=dict(self.request,threads='alloc');a.validate_request(future)
        with self.assertRaisesRegex(ValueError,'D1 refuses'):a.bind_allocation(future,physical_cores=[[0,0]],limits=self.limits,**self.bindings)
    def test_actual_cgroup_and_affinity_negative(self):
        values=dict(affinity=[0,2,4,6],topology=self.topology,memory_max_bytes=2*a.GIB,cpu_quota=200000,cpu_period=100000,swap_max_bytes=0)
        for key,value in [('affinity',[0,2]),('affinity',[0,1,2,4,6]),('memory_max_bytes',4*a.GIB),('cpu_quota',400000),('swap_max_bytes',1),('cpu_period',0)]:
            with self.assertRaises(ValueError):a.check_runtime(self.launch(),**dict(values,**{key:value}))
    def test_no_mutation_and_legacy_exact_two_request(self):
        before=copy.deepcopy((self.request,self.topology,self.limits));self.launch()
        self.assertEqual(before,(self.request,self.topology,self.limits))
        legacy=dict(cores=dict(min=2,max=2),threads=1,ram_gib=dict(base=4,per_core=0),scratch_gib=4)
        value=a.bind_allocation(legacy,physical_cores=[[0,0],[0,1]],limits=self.limits,**self.bindings)
        self.assertEqual(value['compile_workers'],2)
        with self.assertRaises(ValueError):a.bind_allocation(legacy,physical_cores=[[0,0]],limits=self.limits,**self.bindings)
    def test_launch_write_once_pin_and_no_directory_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();receipt=a.write_launch(root,self.launch())
            self.assertEqual(receipt['sha256'],a.hashlib.sha256((root/'allocation.json').read_bytes()).hexdigest())
            before=(root/'allocation.json').read_bytes()
            with self.assertRaises(FileExistsError):a.write_launch(root,self.launch())
            self.assertEqual((root/'allocation.json').read_bytes(),before)
            with self.assertRaises(ValueError):a.write_launch(root/'absent',self.launch())
            self.assertFalse((root/'absent').exists())


if __name__=='__main__':unittest.main()
