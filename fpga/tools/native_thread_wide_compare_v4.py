"""Final wide replay with the exact prepared provider-snapshot path admitted."""
import hashlib
from pathlib import Path

PRESERVED_COMPARISON_SHA = 'abdd838ced9d91173fd08af6894516b6c167169ec6710d09fea9f93b874f08e4'
_raw = Path(__file__).with_name('native_thread_wide_compare_v1.py').read_bytes()
if hashlib.sha256(_raw).hexdigest() != PRESERVED_COMPARISON_SHA:
    raise ValueError('frozen wide-comparison source')
_text = _raw.decode()
for _old, _new, _count in (
    ('native_threaded_wide_v1.py', 'native_threaded_wide_v3.py', 2),
    ('75bd5bae7ffa549db530c02a46c527d5d996391980385e2a28c3d5c39adac9a1',
     '5090b199e2a32463d05c38a51ff313f48b4ad210de15e047d19ced9322738419', 1),
    ("core27-t5b-thread-wide-source-v1/execution-inputs-v[1-9][0-9]*/provider\\.json",
     "(?:core27-t5b-thread-wide-source-v1/execution-inputs-v[1-9][0-9]*/provider\\.json|threaded-wide-package-v3/provider\\.json)", 1)
):
    if _text.count(_old) != _count:
        raise ValueError('exact live-wide provider/replay anchor')
    _text = _text.replace(_old, _new)
exec(compile(_text, str(Path(__file__).resolve()) + '[prepared-provider-path]', 'exec'), globals())


def compare_p8(first_job, threaded_job):
    """Read automatic captured gates; no HDL/reference/numerical rerun."""
    import math
    from fpga.tools import global_queue_v1 as queue
    samples=[];numeric=[];compiled=[];contracts=[]
    for job in (first_job,threaded_job):
        gate_ref=job.get('dependency_gate',{})
        need(gate_ref.get('status')=='PASS_expected_contracts','actual complete typed pilot gate')
        gate_path=Path(gate_ref['path']);need(sha(gate_path)==gate_ref['sha256'],'captured automatic gate pin')
        gate=json.loads(gate_path.read_text());folder=Path(job['result']['evidence'])
        manifest=json.loads((folder/'manifest.json').read_text());report_path=folder/'output/native/report.json'
        report=json.loads(report_path.read_text());package=job['package'];count=job['resources']['threads']
        need(count in (1,4,8) and gate['id']==job['id'] and gate['manifest_sha256']==sha(folder/'manifest.json')==package['manifest_sha256']
             and gate['report_sha256']==sha(report_path) and report['manifest_sha256']==package['manifest_sha256'],
             'exact captured gate/report/manifest binding')
        expected=dict(context_threads=count,model_threads=count,expected_threads=count)
        need(report['status']=='completed_native_commands_unreviewed' and report['probe']==manifest['probe']['expected_json']==expected
             and report['model_threads']==report['context_threads']==count and report['compile_workers']==2,
             'actual compiled/context thread probe and truthful j2')
        placement=manifest['fixed_execution'];allocation=placement['runtime_allocation'];limits=report['limits']
        need(job['dispatch']['lane']==placement['placement']['id'] and job['dispatch']['lane_ids']==placement['placement']['lane_ids']
             and len(allocation['cpus'])==len(set(map(tuple,allocation['physical_cores'])))==8
             and limits['affinity']==allocation['cpus'] and limits['physical_cores']==allocation['physical_cores']
             and limits['memory_max_bytes']==allocation['memory_bytes']==8<<30 and limits['swap_max_bytes']==0
             and list(map(int,limits['cpu_max']))==[800000,100000]
             and report['exact_build_identity']['identity']['runtime_allocation']==allocation,
             'actual eight physical cores/800percent/8GiB/Swap0 and immutable build allocation')
        props=job['result']['properties']
        need(props['InvocationID']==job['dispatch']['invocation'] and props['MainPID']=='0'
             and props['MemoryMax']==str(8<<30) and props['MemorySwapMax']=='0'
             and props['AllowedCPUs']==str(allocation['cpus'][0])+'-'+str(allocation['cpus'][-1]),
             'actual terminal unit identity/resource binding')
        step=manifest['steps'][0]['name'];rows={r['name']:r for r in report['steps']}
        measured={}
        for phase in ('build',step):
            row=rows[phase];usage=row['native_child_usage']
            need(row['returncode']==0 and row.get('error') is None
                 and usage['schema']=='native-wait4-child-usage-v1' and usage['returncode']==0
                 and type(usage['pid']) is int and usage['pid']>0,'actual successful measured native child')
            cpu=usage['user_seconds']+usage['system_seconds']
            values=(row['seconds'],cpu,usage['peak_rss_kib'])
            need(all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in values),'finite real wall/CPU/RSS')
            measured['compile' if phase=='build' else 'model']=dict(wall_seconds=row['seconds'],cpu_seconds=cpu,
                child_peak_rss_kib=usage['peak_rss_kib'])
        validation=report['validations'][step]
        need(validation==next(r['validation'] for r in gate['steps'] if r['name']==step)
             and validation['status']=='PASS_expected_contracts' and validation['operations']==100
             and validation['independent_reference_equal'] is True
             and validation['final_actual_sha256']==validation['final_expected_sha256'],
             'same actual independent full signed96-word reference contract')
        numeric.append({k:v for k,v in validation.items() if k!='phase_wall_ms'})
        contract=manifest['wide_thread_pilot']['serial_contract'];contracts.append(contract)
        compiled.append({name:manifest['sources'][name] for name in contract['sources']})
        samples.append(dict(job_id=job['id'],host=report['host'],threads=count,placement=placement,
            gate=dict(path=str(gate_path),sha256=gate_ref['sha256']),invocation=props['InvocationID'],
            measurements=measured,overall_seconds=report['seconds'],unit_cpu_seconds=int(props['CPUUsageNSec'])/1e9,
            unit_peak_bytes=int(props['MemoryPeak']),phase_wall_ms=validation['phase_wall_ms'],
            tool_sha256=report['tool_sha256']))
    a,b=samples
    need(a['threads']==1 and b['threads'] in (4,8),'matched serial baseline and declared candidate')
    need(a['host']==b['host'] and a['placement']==b['placement'] and a['tool_sha256']==b['tool_sha256']
         and contracts[0]==contracts[1] and compiled[0]==compiled[1] and numeric[0]==numeric[1],
         'source/case/full-word/cycle/ownership equality on the SAME allocation')
    return dict(schema='gfn16-p8-matched-native-thread-pilot-v1',status='PASS_source_identical_values_cycles_ownership',
        samples=samples,model_wall_speedup=a['measurements']['model']['wall_seconds']/b['measurements']['model']['wall_seconds'],
        model_cpu_ratio=b['measurements']['model']['cpu_seconds']/a['measurements']['model']['cpu_seconds'],
        overall_wall_speedup=a['overall_seconds']/b['overall_seconds'],
        scope='ONE source-identical100-operation sample per thread count on SAME8 physical cores; no generic speedup/long qualification',
        promotion_allowed=False,long_packet_admission=False)


def compare_p16(serial_job,threaded_job):
    """Exact baseline P16 values/source/ownership across unlike allocations.

    Wall ratios are observations, never causal thread speedups across hosts.
    Only captured automatic data is read; no numeric/native replay is run.
    """
    import math
    samples=[];manifests=[];validations=[]
    for job,count,cores in ((serial_job,1,2),(threaded_job,8,8)):
        binding=job['dependency_gate'];gate_path=Path(binding['path'])
        need(binding['status']=='PASS_expected_contracts' and sha(gate_path)==binding['sha256'],'actual pinned automatic P16 gate')
        gate=json.loads(gate_path.read_text());folder=Path(job['result']['evidence'])
        manifest_path=folder/'manifest.json';report_path=folder/'output/native/report.json'
        m=json.loads(manifest_path.read_text());r=json.loads(report_path.read_text());manifests.append(m)
        need(gate['id']==job['id'] and gate['manifest_sha256']==sha(manifest_path)==job['package']['manifest_sha256']
             and gate['report_sha256']==sha(report_path) and r['manifest_sha256']==sha(manifest_path)
             and r['status']=='completed_native_commands_unreviewed','closed actual P16 report/manifest outcome')
        probe=dict(context_threads=count,model_threads=count,expected_threads=count)
        limits=r['limits'];props=job['result']['properties']
        need(r['probe']==m['probe']['expected_json']==probe and r['model_threads']==r.get('context_threads',r['probe']['context_threads'])==count
             and r['compile_workers']==2 and len(limits['affinity'])==cores
             and len(set(map(tuple,limits['physical_cores'])))==cores
             and limits['memory_max_bytes']==8<<30 and limits['swap_max_bytes']==0
             and list(map(int,limits['cpu_max']))==[cores*100000,100000],
             'actual exact threads/physical cores/quota/8GiB/Swap0/j2')
        need(r['host']==job['dispatch']['host'] and props['InvocationID']==job['dispatch']['invocation']
             and props['MainPID']=='0' and props['Result']=='success' and props['ExecMainStatus']=='0'
             and not props.get('ControlGroup') and props['MemoryMax']==str(8<<30) and props['MemorySwapMax']=='0'
             and props['AllowedCPUs']==str(limits['affinity'][0])+'-'+str(limits['affinity'][-1]),
             'actual terminal unit/host/resource identity')
        if count==8:
            execution=m['fixed_execution'];allocation=execution['runtime_allocation'];placement=execution['placement']
            need(allocation['cpus']==limits['affinity'] and allocation['physical_cores']==limits['physical_cores']
                 and allocation['cpu_quota_percent']==800 and allocation['memory_bytes']==8<<30
                 and allocation['compile_workers']==2 and job['dispatch']['lane']==placement['id']
                 and job['dispatch']['lane_ids']==placement['lane_ids']
                 and r['exact_build_identity']['identity']['runtime_allocation']==allocation,
                 'four constituent pairs and actual eight-physical build allocation')
        step=m['steps'][0]['name'];rows={value['name']:value for value in r['steps']}
        metrics={}
        for name in ('build',step):
            row=rows[name];usage=row.get('native_child_usage')
            need(row['returncode']==0 and row.get('error') is None,'actual successful measured native command')
            if usage:
                need(usage['schema']=='native-wait4-child-usage-v1' and usage['returncode']==0
                     and type(usage['pid']) is int and usage['pid']>0,'actual wait4 measured child')
                cpu=usage['user_seconds']+usage['system_seconds'];rss=usage['peak_rss_kib'];cumulative=None
                method='native wait4 child CPU and peak RSS'
            else:
                need(count==1,'qualified wide executor records actual wait4 child usage')
                cpu=row['user_seconds']+row['system_seconds'];rss=None;cumulative=row['cumulative_children_peak_rss_kib']
                method='legacy RUSAGE_CHILDREN CPU delta; cumulative peak is not per-command/model RSS'
            need(all(type(value) in (int,float) and math.isfinite(value) and value>=0
                         for value in (row['seconds'],cpu,rss if rss is not None else cumulative)) and row['seconds']>0,
                 'finite actual wall/CPU/RSS observations')
            metrics['compile' if name=='build' else 'model']=dict(wall_seconds=row['seconds'],cpu_seconds=cpu,
                child_peak_rss_kib=rss,cumulative_children_peak_rss_kib=cumulative,measurement_method=method)
        v=r['validations'][step]
        need(v==next(row['validation'] for row in gate['steps'] if row['name']==step)
             and v['status']=='PASS_expected_contracts' and v['p16_diet']==1
             and v.get('p16_timing',0)==0 and v['operations']==100 and v['counts']['candidate_cycles']==1505466
             and v['independent_reference_equal'] is True and v['final_actual_sha256']==v['final_expected_sha256'],
             'exact baseline P16 all-word/cycle/ownership contract')
        validations.append({key:value for key,value in v.items() if key!='phase_wall_ms'})
        samples.append(dict(job_id=job['id'],host=r['host'],threads=count,physical_cores=limits['physical_cores'],affinity=limits['affinity'],
            gate=dict(path=str(gate_path),sha256=binding['sha256']),invocation=props['InvocationID'],measurements=metrics,
            overall_seconds=r['seconds'],unit_cpu_seconds=int(props['CPUUsageNSec'])/1e9,unit_peak_bytes=int(props['MemoryPeak']),
            phase_wall_ms=v['phase_wall_ms'],tool_sha256=r['tool_sha256']))
    serial,wide=manifests;contract=wide['wide_thread_pilot']['serial_contract']
    need(all(serial[key]==contract[key] for key in ('build','probe','steps'))
         and wide['steps']==contract['steps'] and wide['continuous']==serial['continuous']
         and all(serial['sources'].get(name)==wide['sources'].get(name)==pin for name,pin in contract['sources'].items())
         and validations[0]==validations[1],'unchanged complete baseline source/case/full words/cycles/owners')
    normalized=dict(wide['build']);normalized.pop('runtime_threads',None)
    normalized['cflags']=[flag for flag in normalized['cflags'] if flag!='-DGFN16_RUNTIME_THREADS=8']
    need(normalized==contract['build'],'only declared runtime macro/thread count changed')
    a,b=samples
    return dict(schema='gfn16-p16-source-identical-native-thread-pilot-v1',status='PASS_source_identical_values_cycles_ownership',
        samples=samples,observed_model_wall_ratio_not_thread_causal=a['measurements']['model']['wall_seconds']/b['measurements']['model']['wall_seconds'],
        causal_thread_speedup=None,scope='ONE baseline P16 source/case; hosts, compiler versions and physical allocations may differ. Absolute timing/correctness only, not pure thread-causal speedup.',
        promotion_allowed=False,long_packet_admission=False)
