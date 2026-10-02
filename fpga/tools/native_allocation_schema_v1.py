"""D1 pure physical-core request and immutable launch-allocation contract.

No allocation policy, locks, host mutations, dispatch, or threaded admission.
The dispatcher chooses free cores; the runner replays this binding and checks
live affinity/cgroups/topology plus its existing source/tool/quota guards.
"""
import copy
from decimal import Decimal
import hashlib
import json
import re
from pathlib import Path

GIB=1<<30


def need(ok,why):
    if not ok:raise ValueError(why)


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


def pin(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{64}',value),'exact source/profile/build SHA256')
    return value


def number(value,why,positive=False):
    need(type(value) in (int,float),why)
    result=Decimal(str(value));need(result.is_finite() and (result>0 if positive else result>=0),why)
    return result


def gib_bytes(value):
    result=number(value,'finite nonnegative GiB')*GIB
    need(result==result.to_integral_value(),'GiB value must resolve to exact bytes')
    return int(result)


def validate_request(request):
    need(type(request) is dict and set(request) in (
        {'cores','threads','ram_gib','scratch_gib'},
        {'cores','threads','ram_gib','scratch_gib','est_minutes'}),'closed D1 resource request')
    cores=request['cores'];ram=request['ram_gib']
    need(type(cores) is dict and set(cores)=={'min','max'}
         and all(type(v) is int for v in cores.values()) and 1<=cores['min']<=cores['max']<=64,'physical core range')
    need((type(request['threads']) is int and request['threads']==1) or request['threads']=='alloc','model threads1 or future alloc request')
    need(type(ram) is dict and set(ram)=={'base','per_core'},'RAM base/per-core schema')
    base,per=gib_bytes(ram['base']),gib_bytes(ram['per_core'])
    need(base+per*cores['min']>0,'positive minimum RAM grant')
    need(gib_bytes(request['scratch_gib'])>0,'positive scratch reservation')
    if 'est_minutes' in request and request['est_minutes'] is not None:
        number(request['est_minutes'],'finite positive estimate',True)
    return copy.deepcopy(request)


def topology_map(topology):
    need(type(topology) is dict and topology,'complete admitted SMT topology')
    result={}
    for cpu,core in topology.items():
        need(type(cpu) is str and re.fullmatch('0|[1-9][0-9]*',cpu),'canonical logical CPU id')
        need(type(core) is list and len(core)==2 and all(type(v) is int and v>=0 for v in core),'package/core identity')
        result[int(cpu)]=tuple(core)
    return result


def limits_check(limits):
    keys={'max_physical_cores','max_memory_bytes','available_memory_bytes','memory_floor_bytes',
          'available_scratch_bytes','scratch_floor_bytes'}
    need(type(limits) is dict and set(limits)==keys and all(type(v) is int and v>=0 for v in limits.values()),'typed bounded host admission inputs')
    need(1<=limits['max_physical_cores']<=64 and limits['max_memory_bytes']>0,'finite host job ceilings')


def bind_allocation(request,*,worker_id,host,reservation_epoch,source_manifest_sha256,base_build_key,profile_sha256,tool_sha256,
                    topology,physical_cores,limits):
    """Create the exact launch document; free-pool selection remains external.

    physical_cores is an ordered list of [package_id,core_id]. Every logical
    sibling in the pinned complete topology is included in AllowedCPUs. CPU
    quota and compile workers count physical cores, never SMT siblings.
    """
    request=validate_request(request)
    need(request['threads']==1,'D1 refuses alloc threading until separately admitted D3 pilot')
    need(type(host) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}',host),'exact host identity')
    need(type(worker_id) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}',worker_id),'exact worker identity')
    need(type(reservation_epoch) is int and reservation_epoch>0,'typed reservation UTC epoch')
    need(type(tool_sha256) is dict and tool_sha256 and all(type(k) is str and k for k in tool_sha256),'exact tool identity mapping')
    for value in tool_sha256.values():pin(value)
    for value in (source_manifest_sha256,base_build_key,profile_sha256):pin(value)
    topo=topology_map(topology);limits_check(limits)
    need(type(physical_cores) is list and physical_cores
         and all(type(v) is list and len(v)==2 and all(type(x) is int and x>=0 for x in v) for v in physical_cores),'physical allocation list')
    selected=list(map(tuple,physical_cores))
    need(selected==sorted(set(selected)) and set(selected)<=set(topo.values()),'sorted unique known physical cores')
    count=len(selected)
    need(request['cores']['min']<=count<=request['cores']['max'] and count<=limits['max_physical_cores'],'allocation within request and host range')
    cpus=sorted(cpu for cpu,core in topo.items() if core in selected)
    memory=gib_bytes(request['ram_gib']['base'])+count*gib_bytes(request['ram_gib']['per_core'])
    scratch=gib_bytes(request['scratch_gib'])
    need(memory<=limits['max_memory_bytes'] and memory+limits['memory_floor_bytes']<=limits['available_memory_bytes'],'RAM grant plus reserve fits admission')
    need(scratch+limits['scratch_floor_bytes']<=limits['available_scratch_bytes'],'scratch grant plus reserve fits admission')
    value=dict(schema='native-launch-allocation-v1',phase='D1_serial_model',host=host,worker_id=worker_id,
        reservation_epoch=reservation_epoch,tool_sha256=copy.deepcopy(tool_sha256),
        request=request,request_sha256=digest(request),source_manifest_sha256=source_manifest_sha256,
        base_build_key=base_build_key,profile_sha256=profile_sha256,
        topology=copy.deepcopy(topology),topology_sha256=digest(topology),physical_cores=copy.deepcopy(physical_cores),
        physical_core_count=count,allowed_cpus=cpus,compile_workers=count,model_threads=1,
        cpu_quota_percent=100*count,memory_bytes=memory,scratch_bytes=scratch,
        admission_inputs=copy.deepcopy(limits),resource_scope='one immutable launch; no lock or live-resource admission conferred')
    value['allocation_sha256']=digest(value)
    value['allocated_build_key']=digest(dict(base_build_key=base_build_key,allocation_sha256=value['allocation_sha256'],compile_workers=count,model_threads=1))
    return value


def validate_launch(launch,*,allocation_sha256,request,worker_id,host,reservation_epoch,source_manifest_sha256,base_build_key,profile_sha256,tool_sha256,topology):
    need(type(launch) is dict,'launch allocation object')
    need(launch.get('allocation_sha256')==pin(allocation_sha256),'independently bound allocation SHA256')
    expected=bind_allocation(request,worker_id=worker_id,host=host,reservation_epoch=reservation_epoch,source_manifest_sha256=source_manifest_sha256,
        base_build_key=base_build_key,profile_sha256=profile_sha256,tool_sha256=tool_sha256,topology=topology,
        physical_cores=launch.get('physical_cores'),limits=launch.get('admission_inputs'))
    need(launch==expected,'immutable request/source/profile/topology/resource allocation mismatch')
    return copy.deepcopy(expected)


def check_runtime(launch,*,affinity,topology,memory_max_bytes,cpu_quota,cpu_period,swap_max_bytes):
    """Exact observed cgroup/SMT checks; caller first invokes validate_launch."""
    need(type(affinity) is list and all(type(x) is int for x in affinity)
         and affinity==launch['allowed_cpus'],'affinity equals allocation including all SMT siblings')
    topology_map(topology)
    need(topology==launch['topology'],'live complete topology equals allocation')
    need(all(type(v) is int for v in (memory_max_bytes,cpu_quota,cpu_period,swap_max_bytes))
         and memory_max_bytes==launch['memory_bytes'] and swap_max_bytes==0
         and cpu_period>0 and cpu_quota==launch['physical_core_count']*cpu_period,'exact memory/no-swap/physical-core CPU quota')
    return True


def write_launch(native_root,launch):
    """Write-once launch artifact; returns raw bytes SHA for outer ticket/argv.

    No directory creation or existing-file replacement. The dispatcher keeps
    this pin outside the launch file and passes it to the runner. A failed
    partial write remains evidence and is never silently retried here.
    """
    root=Path(native_root)
    need(root.is_absolute() and root.resolve()==root and root.is_dir(),'pre-existing canonical native job root')
    expected={key:launch[key] for key in ('worker_id','host','reservation_epoch','source_manifest_sha256','base_build_key','profile_sha256','tool_sha256','topology')}
    validate_launch(launch,allocation_sha256=launch['allocation_sha256'],request=launch['request'],**expected)
    raw=canonical(launch)+b'\n';path=root/'allocation.json'
    with path.open('xb') as stream:stream.write(raw)
    need(path.read_bytes()==raw,'launch write identity')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),allocation_sha256=launch['allocation_sha256'])
