"""Mocked captured-data comparison; never runs HDL or full-size arithmetic."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from fpga.tests.test_r75_thread_pilot import packet
from fpga.tools import global_queue_v1 as q
from fpga.tools import native_thread_wide_compare_v4 as comparison


class P8ComparisonTests(unittest.TestCase):
    def fixture(self,root,count,mutate=None):
        _,m,_,job=packet(count);folder=root/str(count);folder.mkdir()
        allocation=m['fixed_execution']['runtime_allocation'];step=m['steps'][0]['name']
        native=json.loads((q.FPGA/'queue/evidence/s4-p8-canon1-continuous100-normal-q1-v1/attempt-0/collected/output/native/report.json').read_text())['validations'][step]
        report=dict(status='completed_native_commands_unreviewed',host=m['host'],probe=m['probe']['expected_json'],
            model_threads=count,context_threads=count,compile_workers=2,seconds=100.0,
            limits=dict(affinity=allocation['cpus'],physical_cores=allocation['physical_cores'],memory_max_bytes=8<<30,
                swap_max_bytes=0,cpu_max=['800000','100000']),
            exact_build_identity=dict(identity=dict(runtime_allocation=allocation)),validations={step:native},tool_sha256={'verilator':'a'*64})
        report['steps']=[dict(name=name,returncode=0,error=None,seconds=seconds,native_child_usage=dict(
            schema='native-wait4-child-usage-v1',returncode=0,pid=100+count,user_seconds=30.0,system_seconds=2.0,peak_rss_kib=1000))
            for name,seconds in (('build',20.0),(step,80.0 if count==1 else 40.0))]
        if mutate:mutate(m,report)
        manifest=folder/'manifest.json';manifest.write_text(json.dumps(m));job['package']['manifest_sha256']=q.sha(manifest)
        report['manifest_sha256']=q.sha(manifest);path=folder/'output/native/report.json';path.parent.mkdir(parents=True);path.write_text(json.dumps(report))
        gate=dict(id=job['id'],status='PASS_expected_contracts',manifest_sha256=q.sha(manifest),report_sha256=q.sha(path),
            steps=[dict(name=step,validation=native)])
        gate_path=folder/'gate.json';gate_path.write_text(json.dumps(gate))
        job['dependency_gate']=dict(status='PASS_expected_contracts',path=str(gate_path),sha256=q.sha(gate_path))
        placement=m['fixed_execution']['placement'];invocation='a'*32
        job['dispatch']=dict(lane=placement['id'],lane_ids=placement['lane_ids'],invocation=invocation)
        job['result']=dict(evidence=str(folder),properties=dict(InvocationID=invocation,MainPID='0',
            MemoryMax=str(8<<30),MemorySwapMax='0',AllowedCPUs='8-15',CPUUsageNSec='100000000000',MemoryPeak='2000000'))
        return job

    def test_exact_values_cycles_ownership_and_separate_measurements(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);a=self.fixture(root,1);b=self.fixture(root,8)
            value=comparison.compare_p8(a,b)
            self.assertEqual(value['model_wall_speedup'],2)
            self.assertEqual(value['samples'][1]['measurements']['compile']['wall_seconds'],20)
            self.assertFalse(value['long_packet_admission'])

    def test_drift_and_unbound_result_rejected(self):
        for kind in ('value','cycles','source','physical','quota','probe','count','nan'):
            def change(m,r):
                native=next(iter(r['validations'].values()))
                if kind=='value':native['final_actual_sha256']='0'*64
                elif kind=='cycles':native['counts']['candidate_cycles']+=1
                elif kind=='source':m['sources'][m['build']['cpp_source']]='0'*64
                elif kind=='physical':r['limits']['physical_cores']=[[0,0]]*8
                elif kind=='quota':r['limits']['cpu_max']=['200000','100000']
                elif kind=='probe':r['probe']=dict(context_threads=1,model_threads=1,expected_threads=1)
                elif kind=='count':r['model_threads']=4
                else:r['steps'][-1]['seconds']=float('nan')
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);a=self.fixture(root,1);b=self.fixture(root,8,change)
                with self.assertRaises((ValueError,KeyError)):comparison.compare_p8(a,b)


class P16ComparisonTests(unittest.TestCase):
    def fixture(self,root,count,defect=None):
        baseline=q.registry()['s4-p16-diet-continuous100-normal-q1-v1']
        original=Path(baseline['result']['evidence'])
        manifest=json.loads((original/'manifest.json').read_text())
        report=json.loads((original/'output/native/report.json').read_text())
        job=copy.deepcopy(baseline)
        if count==8:
            packet=q.FPGA/'artifacts/r75-p16-thread-pilot/thread8-packet-v1'
            manifest=json.loads((packet/'manifest.json').read_text())
            job=json.loads((q.FPGA/'artifacts/r75-p16-thread-pilot/global-ticket.json').read_text())
            allocation=manifest['fixed_execution']['runtime_allocation'];placement=manifest['fixed_execution']['placement']
            report.update(host='gfn16-azure-sim-f32',probe=manifest['probe']['expected_json'],model_threads=8,context_threads=8,
                limits=dict(affinity=allocation['cpus'],physical_cores=allocation['physical_cores'],memory_max_bytes=8<<30,
                    swap_max_bytes=0,cpu_max=['800000','100000']),exact_build_identity=dict(identity=dict(runtime_allocation=allocation)))
            report['validations'][manifest['steps'][0]['name']]['phase_wall_ms']=dict(candidate_ms=10000,read_ms=2000,reference_ms=500)
            for row in report['steps']:
                row['native_child_usage']=dict(schema='native-wait4-child-usage-v1',pid=12345,returncode=row['returncode'],
                    user_seconds=row['user_seconds'],system_seconds=row['system_seconds'],peak_rss_kib=40000)
            report['steps'][-1]['seconds']=20.0;report['seconds']=report['steps'][1]['seconds']+30.0
            props=copy.deepcopy(baseline['result']['properties']);props.update(InvocationID='e'*32,AllowedCPUs='0-7')
            job['dispatch']=dict(host=report['host'],lane=placement['id'],lane_ids=placement['lane_ids'],invocation='e'*32)
            job['result']=dict(properties=props)
        if defect=='values':report['validations'][manifest['steps'][0]['name']]['final_actual_sha256']='0'*64
        elif defect=='source':manifest['sources'][manifest['build']['cpp_source']]='0'*64
        elif defect=='physical':report['limits']['physical_cores']=[[0,0]]*8
        elif defect=='probe':report['probe']['model_threads']=1
        elif defect=='cycles':report['validations'][manifest['steps'][0]['name']]['counts']['candidate_cycles']+=1
        elif defect=='failed_unit':job['result']['properties']['ExecMainStatus']='1'
        elif defect=='nonfinite':report['steps'][-1]['seconds']=float('nan')
        folder=root/str(count);folder.mkdir();manifest_path=folder/'manifest.json';manifest_path.write_text(json.dumps(manifest))
        job['package']['manifest_sha256']=q.sha(manifest_path);report['manifest_sha256']=q.sha(manifest_path)
        report_path=folder/'output/native/report.json';report_path.parent.mkdir(parents=True);report_path.write_text(json.dumps(report))
        step=manifest['steps'][0]['name']
        gate=dict(id=job['id'],status='PASS_expected_contracts',manifest_sha256=q.sha(manifest_path),report_sha256=q.sha(report_path),
            steps=[dict(name=step,validation=report['validations'][step])])
        gate_path=folder/'gate.json';gate_path.write_text(json.dumps(gate))
        job['dependency_gate']=dict(status='PASS_expected_contracts',path=str(gate_path),sha256=q.sha(gate_path))
        job['result']['evidence']=str(folder)
        return job

    def test_same_p16_source_values_cycles_and_unmatched_host_timing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);a=self.fixture(root,1);b=self.fixture(root,8)
            result=comparison.compare_p16(a,b)
            self.assertIsNone(result['causal_thread_speedup'])
            self.assertNotEqual(result['samples'][0]['host'],result['samples'][1]['host'])
            self.assertEqual(result['samples'][1]['measurements']['model']['wall_seconds'],20)
            self.assertFalse(result['long_packet_admission'])

    def test_source_outcome_physical_and_measurement_drift_refused(self):
        for defect in ('values','source','physical','probe','cycles','failed_unit','nonfinite'):
            with self.subTest(defect=defect),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);a=self.fixture(root,1);b=self.fixture(root,8,defect)
                with self.assertRaises((ValueError,KeyError)):comparison.compare_p16(a,b)


if __name__=='__main__':unittest.main()
