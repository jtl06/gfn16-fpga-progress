"""Size-flexible worker checks; no cloud calls or compiler executions."""
from datetime import datetime,timezone
import copy
import inspect
import tempfile
from pathlib import Path
import unittest
from fpga.cloud import aws_fit_v6 as v6
from fpga.cloud import aws_fit_v5 as frozen
from fpga.synthesis.prepare_crt27_worker_pair import prepare

class WorkerV6Tests(unittest.TestCase):
    def test_existing_project_limits_and_lock_guards_unchanged(self):
        for name in ('verify_project','validate_limits','live_limits','locked','slot_locks','read_regular','live_topology','topology_map','parse_cpus'):
            self.assertEqual(inspect.getsource(getattr(v6,name)),inspect.getsource(getattr(frozen,name)))
        self.assertEqual((v6.HOST,v6.ROOT,v6.MEMORY,v6.TIMEOUT),(frozen.HOST,frozen.ROOT,frozen.MEMORY,frozen.TIMEOUT))
        self.assertEqual(inspect.getsource(v6.launch),inspect.getsource(frozen.launch).replace('launcher_version=5','launcher_version=6').replace('run-aws-fit-v5.sh','run-aws-fit-v6.sh'))
    def fixture(self,cores):
        now=datetime.now(timezone.utc)
        rows=[dict(cpu=i,package_id=0,core_id=i%cores) for i in range(cores*2)]
        names='ab' if cores==8 else 'abcd'
        doc=dict(hostname=v6.HOST,observed_at=now.isoformat(),cpus=rows,
            slots={s:list(range(i*4,i*4+4)) for i,s in enumerate(names)})
        return doc,rows,now

    def test_both_sizes_disjoint_no_siblings(self):
        for cores in (8,16):
            doc,rows,now=self.fixture(cores)
            for slot,cpus in doc['slots'].items():
                result=v6.validate_topology(doc,slot,cpus,rows,v6.HOST,now)
                self.assertEqual(len(result['physical_cores']),4)
            bad=copy.deepcopy(doc);bad['slots']['b']=[cores,1,2,3]
            with self.assertRaises(ValueError):v6.validate_topology(bad,'a',[0,1,2,3],rows,v6.HOST,now)

    def test_stale_observation_and_unavailable_slot_rejected(self):
        doc,rows,now=self.fixture(8)
        with self.assertRaises(ValueError):v6.validate_topology(doc,'c',[0,1,2,3],rows,v6.HOST,now)
        doc['observed_at']='2026-01-01T00:00:00+00:00'
        with self.assertRaises(ValueError):v6.validate_topology(doc,'a',[0,1,2,3],rows,v6.HOST,now)

    def test_worker_pair_validates_and_controls_match(self):
        root=Path(__file__).resolve().parents[1]
        gate=root/'results/throughput-20260929/crt27-mont-mutations-v1/report.json'
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp).resolve()/'pair';prepare(out,gate)
            for name in ('frozen','montgomery'):
                context=v6.verify_project(out/name)
                self.assertEqual(context['qsf_parameters'],{'USE_MONT':int(name=='montgomery')})
            for name in ('run.tcl','probe.sdc','probe.qpf'):
                self.assertEqual((out/'frozen'/name).read_bytes(),(out/'montgomery'/name).read_bytes())
            self.assertEqual((out/'frozen/probe.qsf').read_text().replace('USE_MONT 0','USE_MONT 1'),(out/'montgomery/probe.qsf').read_text())
            with self.assertRaises(FileExistsError):prepare(out,gate)

if __name__=='__main__':unittest.main()
