"""Standing-queue adapter for the requested Azure P8 saved-layout audit chain.

Native work uses the existing qualified audit runner and collector. This
adapter supplies immutable data and transport, never changes the fitted tree.
"""
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shlex
import subprocess
import tarfile

FPGA = Path(__file__).resolve().parents[1]
END = datetime(2026, 10, 2, 16, tzinfo=timezone.utc)
WRAP_END = datetime(2026, 10, 3, 1, tzinfo=timezone.utc)
PINS = {
    'tools/plain_fit_queue_v6.py': 'abd323d015b4ccf8f195432efd003481053b1a38812e6ec9c877862233451184',
    'cloud/plain_fit_audit_signed_v1.py': 'da7134c6c732cf13df0109f8c4f20ed075d878b23524051b3f73212e8285865a',
    'tools/collect_plain_fit_audit_signed_v1.py': 'da17344e10f9dc70945181561834247e99f7f1e343959bba989d27cb9379014e',
    'tools/fit_audit_stage.py': 'e60669aef65f32cca4776dc10e345e5112a533c7cef5f44140e720a5d2da2636',
    'tools/audit_period_search.py': '9bb6c698d13febbda7c9a167425b4cf5e6927bf69a6e6b4aa3ba4a41a487f1ce',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module(name, relative):
    path = FPGA/relative
    # r66: maintained tools change in place. Capture actual bytes once for
    # fresh packages; never change a running job's captured implementation.
    PINS[relative] = sha(path)
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class AuditBackend:
    horizon_seconds = 2280

    def __init__(self, directory, end=END):
        if end > END:
            raise ValueError('audit cannot extend campaign cutoff')
        self.directory = Path(directory)
        self.end = end
        self.q = module('audit_transport', 'tools/plain_fit_queue_v6.py')
        self.ad = module('audit_native', 'cloud/plain_fit_audit_signed_v1.py')
        self.search = module('audit_search', 'tools/audit_period_search.py')
        PINS['tools/collect_plain_fit_audit_signed_v1.py']=sha(FPGA/'tools/collect_plain_fit_audit_signed_v1.py')
        PINS['tools/fit_audit_stage.py']=sha(FPGA/'tools/fit_audit_stage.py')
        policy=module('audit_budget_policy','cloud/fit_budget_policy.py')
        policy_path=FPGA/'cloud/fit-policy-signed-credits.json'
        self.money=policy.PolicyBudget(dict(path=str(policy_path.relative_to(FPGA)),sha256=sha(policy_path)),FPGA)
        self.reader = self.q.SSHBackend(self.directory, end)

    def next(self, parent_handle, parent_bundle, prior_audit_terminal_bundles):
        parent = self.q.read(dict(path=parent_bundle['receipt'], sha256=parent_bundle['receipt_sha256']))
        if not parent['native_job_succeeded']:
            return None
        self.q.need(parent_handle['host'] in self.ad.HOSTS and parent_handle['slot'] in self.ad.HOSTS[parent_handle['host']]['slots']
                    and parent['host'] == parent_handle['host'] and parent['unit'] == parent_handle['unit']
                    and parent['terminal_proven'] is True
                    and parent['source_request_sha256'] == parent_handle['request_sha256']
                    and parent['invocation_id'] == parent_handle['invocation_id'], 'exact same-host parent')
        receipts = [self.q.read(dict(path=b['receipt'], sha256=b['receipt_sha256']))
                    for b in prior_audit_terminal_bundles]
        if any(r.get('status')=='failed_native_or_evidence' for r in receipts):
            return dict(kind='audit_search_result',parent_id=parent_handle['id'],action='complete',
                        status='failed_native_or_evidence',reason='Collected native evidence failure; no clock PASS or automatic retry')
        # Baseline-only native audit is source-bound to the fitted manifest's
        # original clock. New tickets need not use the first P8 run's 10 ns.
        baseline_ns=receipts[0]['timing']['baseline']['period_ns'] if receipts else '10.000'
        decision = self.search.choose(receipts, parent['project'], parent['invocation_id'],baseline_ns=baseline_ns)
        if decision['action'] != 'audit':
            return dict(kind='audit_search_result', parent_id=parent_handle['id'], **decision)
        number = len(receipts)
        self.q.need(number <= 8, 'one baseline plus eight selected audit bound')
        return dict(kind='audit', id=parent_handle['id']+'-audit'+str(number),
                    parent_id=parent_handle['id'], host=parent_handle['host'], slot=parent_handle['slot'],
                    parent_handle=parent_handle, parent_bundle=parent_bundle,
                    selected_period_ns=decision['selected_period_ns'],
                    selection_reason=None if decision['selected_period_ns'] is None else decision['reason'],
                    cutoff_utc=self.end.isoformat())

    def prepare(self, action, directory, topology, now):
        host=action['host']; slot=action['slot']
        self.q.need(action['kind'] == 'audit' and host in self.ad.HOSTS and slot in self.ad.HOSTS[host]['slots']
                    and host == action['parent_handle']['host'], 'requested bounded same-host audit')
        self.q.need(now < self.end, 'remaining audit intake cutoff')
        self.q.need(now.timestamp()+self.horizon_seconds+600 <= WRAP_END.timestamp(), 'audit completion and collection before wrap end')
        self.q.need(not (FPGA/'docs/briefs/PAUSE').exists(), 'PAUSE')
        parent_handle = action['parent_handle']
        terminal = self.q.read(dict(path=action['parent_bundle']['receipt'],
                                   sha256=action['parent_bundle']['receipt_sha256']))
        original = self.q.read(parent_handle['request'])
        self.q.need(terminal['terminal_proven'] and terminal['native_job_succeeded']
                    and terminal['invocation_id'] == parent_handle['invocation_id'], 'successful original terminal')
        directory = Path(directory)
        directory.mkdir()
        tools_name = 'audit-tools-'+action['id']
        tools = directory/tools_name
        tools.mkdir()
        remote_root = Path(self.ad.HOSTS[host]['root'])
        remote_tools = remote_root/tools_name
        unit = 'gfn16-'+action['id']+'.service'
        self.q.name(action['id'])
        hourly=self.money.hourly('azure' if host == self.ad.FIT else 'aws')
        descriptor=dict(host=host,max_seconds=self.horizon_seconds,
                        source_sha256=original['project']['manifest_sha256'],hourly_provider_status=hourly)
        self.ad.hourly_status(descriptor,host)
        provider,transition=None,None
        runtime = self.ad.runtime_pins(host, descriptor, FPGA)
        sources = {'plain_fit_audit_signed_v1.py': FPGA/'cloud/plain_fit_audit_signed_v1.py',
                   self.ad.AUDIT: FPGA/'tools'/self.ad.AUDIT,
                   self.ad.TCL: FPGA/'synthesis'/self.ad.TCL,
                   'fit_audit_stage.py': FPGA/'tools/fit_audit_stage.py'}
        for relative, pin in runtime.items():
            if relative.startswith('fpga/'):
                sources[relative] = FPGA/relative[5:]
        for relative, source in sources.items():
            expected = runtime.get(relative, sha(source))
            self.q.need(expected is not None and sha(source) == expected, 'closed staged audit source')
            destination = tools/relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as stream:
                stream.write(source.read_bytes())
        if action.get('report_path_classes'):
            self.q.need(action['report_path_classes'] is True and action['selected_period_ns'] is None,
                        'bounded baseline-only architectural report')
            tcl=tools/self.ad.TCL
            original_tcl=tcl.read_text()
            anchor='                plain_mark END $phase $index $name $hold_only'
            self.q.need(original_tcl.count(anchor)==1,'one post-report diagnostic anchor')
            diagnostic=(FPGA/'synthesis/postfit_path_classes.tcl').read_text()
            if action.get('report_class_names'):
                names=action['report_class_names']
                self.q.need(type(names) is list and names and len(names)==len(set(names))
                    and set(names)<={'feed_boundary','boundary_local','forward_ntt','inverse_ntt','term','carry','crt','canonical','canonical_raw_ready','canonical_raw_ready_data','fault_control','fault_sinks'},
                    'bounded architectural selector names')
                diagnostic='set path_class_selection {'+' '.join(names)+'}\n'+diagnostic
            tcl.write_text(diagnostic+'\n'+original_tcl.replace(anchor,
                '                report_path_classes $output $phase $index $name\n'+anchor))
            adapter=tools/'plain_fit_audit_signed_v1.py'
            raw=adapter.read_text()
            self.q.need(raw.count(self.ad.TCL_SHA)==1,'one captured Tcl identity')
            adapter.write_text(raw.replace(self.ad.TCL_SHA,sha(tcl)))
        config = dict(adapter=dict(path=str(remote_tools/'plain_fit_audit_signed_v1.py'),
                                   sha256=sha(tools/'plain_fit_audit_signed_v1.py')),
            host=host, slot=slot, unit=unit, project=terminal['project'],
            output=str(remote_root/('audit-output-'+action['id'])),
            original_request=dict(path=parent_handle['remote_request'], sha256=parent_handle['request_sha256']),
            terminal_receipt=dict(path=str(remote_root/('fit-queue-collection-'+parent_handle['id'])/'terminal-collection-v1.json'),
                                  sha256=action['parent_bundle']['receipt_sha256']),
            original_invocation=parent_handle['invocation_id'], manifest_sha256=original['project']['manifest_sha256'],
            selected_period_ns=action['selected_period_ns'], selection_reason=action['selection_reason'],
            provider_inputs=provider, transition=transition, cutoff_utc=action['cutoff_utc'],hourly_provider_status=hourly)
        self.q.save(tools/'config.json', config)
        helpers = {str(p.relative_to(tools)):sha(p) for p in tools.rglob('*') if p.is_file()}
        archive = directory/'package.tar.gz'
        with tarfile.open(archive, 'w:gz') as stream:
            stream.add(tools, arcname=tools_name)
        handle = dict(id=action['id'], kind='audit', host=host, slot=slot, unit=unit,
            parent_id=action['parent_id'], original_invocation=parent_handle['invocation_id'],
            project_name=Path(terminal['project']).name, scope=terminal['scope'],
            config=dict(path=str(tools/'config.json'), sha256=sha(tools/'config.json')),
            remote_config=str(remote_tools/'config.json'), tools=str(remote_tools),
            package_sha256=sha(archive), selected_period_ns=action['selected_period_ns'])
        self.q.save(directory/'prepared.json', dict(handle=handle, helper_sha256=helpers))
        return handle, helpers, archive

    def remote(self, handle, script, timeout=120):
        result = subprocess.run(self.q.SSH[handle['host']]+['/usr/bin/python3 -I -B -'],
            input=script.encode(), capture_output=True, timeout=self.reader.timeout(timeout))
        self.q.need(result.returncode == 0, 'audit remote operation unresolved: '+result.stderr.decode()[-2000:])
        return json.loads(result.stdout)

    def affinity(self, handle):
        return ','.join(map(str,self.ad.HOSTS[handle['host']]['slots'][handle['slot']]))

    def stage(self, handle, archive):
        raw = self.q.regular(archive, handle['package_sha256'])
        import base64
        script = "import base64,io,pathlib,tarfile,json,hashlib\n"
        script += 'root=pathlib.Path('+repr(self.ad.HOSTS[handle['host']]['root'])+')\n'
        script += 'target=pathlib.Path('+repr(handle['tools'])+')\n'
        script += 't=tarfile.open(fileobj=io.BytesIO(base64.b64decode('+repr(base64.b64encode(raw).decode())+')),mode="r:gz")\n'
        script += 'members=t.getmembers()\nassert sum(m.size for m in members)<536870912 and len(members)<10000\n'
        script += 'for m in members:\n p=pathlib.Path(m.name)\n assert not p.is_absolute() and ".." not in p.parts and p.parts[0]==target.name and (m.isfile() or m.isdir())\n'
        script += 'if not target.exists():t.extractall(root,filter="data")\n'
        script += 'for m in members:\n if m.isfile():\n  p=root/m.name\n  assert p.resolve()==p and p.is_file() and p.stat().st_nlink==1 and hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256(t.extractfile(m).read()).digest()\n'
        script += 'assert not (target/"start-intent.json").exists(),"prior start intent requires observation, never restaging"\n'
        script += 'print(json.dumps({"staged":True,"prepared":(target/"preparation.json").exists()}))\n'
        staged = self.remote(handle, script)
        command = ['/usr/bin/taskset', '-c', self.affinity(handle), '/usr/bin/python3', '-I', '-B',
                   str(Path(handle['tools'])/'fit_audit_stage.py'), 'prepare', handle['remote_config'], handle['config']['sha256']]
        if staged['prepared']:
            recovery = 'import pathlib,json,hashlib\np=pathlib.Path('+repr(handle['tools'])+')\n'
            recovery += 'd=json.loads((p/"preparation.json").read_text())\nassert pathlib.Path(d["request_path"])==p/"request.json"\n'
            recovery += 'assert hashlib.sha256((p/"request.json").read_bytes()).hexdigest()==d["request_sha256"]\n'
            recovery += 'assert hashlib.sha256((p/"spec.json").read_bytes()).hexdigest()==d["spec_sha256"]\nprint(json.dumps(d))\n'
            prepared = self.remote(handle, recovery)
        else:
            result = subprocess.run(self.q.SSH[handle['host']]+[shlex.join(command)], capture_output=True,
                                    text=True, timeout=self.reader.timeout(180))
            self.q.need(result.returncode == 0, 'audit preparation incomplete; no native launch: '+result.stderr[-2000:])
            prepared = json.loads(result.stdout)
        self.q.need(prepared['config_sha256'] == handle['config']['sha256'], 'native preparation config identity')
        handle.update(remote_request=prepared['request_path'], request_sha256=prepared['request_sha256'],
                      spec_sha256=prepared['spec_sha256'])
        return handle

    def launch(self, handle, helpers=None):
        command = ['/usr/bin/taskset', '-c', self.affinity(handle), '/usr/bin/python3', '-I', '-B',
                   str(Path(handle['tools'])/'fit_audit_stage.py'), 'start', handle['remote_config'], handle['config']['sha256']]
        result = subprocess.run(self.q.SSH[handle['host']]+[shlex.join(command)], capture_output=True,
                                text=True, timeout=self.reader.timeout(180))
        self.q.need(result.returncode == 0, 'uncertain audit launch; never retry: '+result.stderr[-2000:])
        observed = json.loads(result.stdout)
        self.q.need(observed['request']['sha256'] == handle['request_sha256'], 'actual request identity')
        return dict(state=observed['state'], invocation_id=observed['state']['InvocationID'],
                    request_sha256=handle['request_sha256'])

    def observe(self, handle):
        script = 'import pathlib,json,subprocess,hashlib\n'
        script += 'p=pathlib.Path('+repr(handle['remote_request'])+')\nassert hashlib.sha256(p.read_bytes()).hexdigest()=='+repr(handle['request_sha256'])+'\n'
        script += 'unit='+repr(handle['unit'])+'\n'
        script += 'state=dict(x.split("=",1) for x in subprocess.check_output(["systemctl","show",unit,"-p","MainPID","-p","ActiveState","-p","SubState","-p","InvocationID"],text=True).splitlines())\n'
        script += 'rows=[json.loads(x) for x in subprocess.check_output(["journalctl","-u",unit,"-o","json","--no-pager"],text=True).splitlines()]\n'
        script += 'ids={r.get("INVOCATION_ID") for r in rows if str(r.get("_PID"))=="1" and r.get("UNIT")==unit and r.get("JOB_TYPE")=="start" and r.get("JOB_RESULT")=="done"}\nassert len(ids)<=1\n'
        script += 'print(json.dumps(dict(state=state,invocation_id=next(iter(ids)) if ids else None,request_sha256='+repr(handle['request_sha256'])+')))\n'
        return self.remote(handle, script)

    def collect(self, handle):
        collector = FPGA/'tools/collect_plain_fit_audit_signed_v1.py'
        self.q.need(sha(collector) == PINS['tools/collect_plain_fit_audit_signed_v1.py'], 'collector drift')
        remote_root = Path(self.ad.HOSTS[handle['host']]['root'])
        target = Path(handle['tools'])/('collect_plain_fit_audit_'+sha(collector)[:16]+'.py')
        output = remote_root/('collection-'+handle['id'])
        script = 'import pathlib,hashlib,json,subprocess\n'
        script += 'target=pathlib.Path('+repr(str(target))+')\nraw='+repr(collector.read_bytes())+'\n'
        script += 'if not target.exists():\n with target.open("xb") as f:f.write(raw)\nassert hashlib.sha256(target.read_bytes()).hexdigest()=='+repr(sha(collector))+'\n'
        script += 'output=pathlib.Path('+repr(str(output))+')\nreceipt=output/"terminal-collection.json"\n'
        argv = ['/usr/bin/taskset', '-c', self.affinity(handle), '/usr/bin/python3', '-I', '-B', str(target),
                '--request', handle['remote_request'], '--request-sha256', handle['request_sha256'],
                '--invocation', handle['invocation_id'], '--output', str(output)]
        script += 'if not receipt.exists():\n subprocess.run('+repr(argv)+',check=True,capture_output=True,timeout=180)\n'
        script += 'print(json.dumps(dict(receipt=json.loads(receipt.read_text()),receipt_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest())))\n'
        result = self.remote(handle, script, 210)
        directory = self.directory/'audit-terminal'/handle['id']
        directory.mkdir(parents=True, exist_ok=True)
        receipt = directory/'receipt.json'
        if not receipt.exists():
            self.q.save(receipt, result['receipt'])
        self.q.need(json.loads(receipt.read_text()) == result['receipt'], 'preserve original audit receipt')
        metadata = result['receipt']['archive']
        archive = directory/'native-audit.tar.gz'
        if not archive.exists():
            raw = self.reader.call(handle['host'], dict(op='read', host=handle['host'], path=metadata['path'], sha256=metadata['sha256']), binary=True)
            self.q.need(len(raw) == metadata['size'] and hashlib.sha256(raw).hexdigest() == metadata['sha256'], 'audit archive identity')
            with archive.open('xb') as stream:
                stream.write(raw)
        return dict(receipt=str(receipt), receipt_sha256=sha(receipt), archive=str(archive),
                    remote_receipt_sha256=result['receipt_sha256'])

    def verify_terminal(self, handle, bundle):
        receipt = self.q.read(dict(path=bundle['receipt'], sha256=bundle['receipt_sha256']))
        self.q.need(receipt['collector_sha256'] == PINS['tools/collect_plain_fit_audit_signed_v1.py']
                    and receipt['schema'] == 'plain-fit-audit-terminal-collection-v1'
                    and receipt['unit'] == handle['unit'] and receipt['scope'] == handle['scope']
                    and receipt['invocation_id'] == handle['invocation_id']
                    and receipt['request_sha256'] == handle['request_sha256']
                    and receipt['spec_sha256'] == handle['spec_sha256']
                    and receipt['original_invocation'] == handle['original_invocation']
                    and receipt['terminal_proven'] and receipt['original_unchanged']
                    and receipt['compiled_input_unchanged'] and receipt['fit_commands'] == 0,
                    'typed source-bound actual audit terminal')
        if receipt['status']=='failed_native_or_evidence':
            self.q.need(receipt.get('failure_reason')=="ValueError('unknown setup relationship/nonfinite timing')"
                        and receipt.get('timing')=={} and receipt['timing_closes'] is False,'exact collected parser failure, never timing PASS')
            return 'audit_native_failure'
        self.q.need(receipt['status'] in ('native_scoped_timing_closes_pending_independent_review', 'native_timing_violation'),
                    'native/evidence failure is not a timing-search result')
        return 'audit_timing_pass' if receipt['timing_closes'] else 'audit_timing_violation'
