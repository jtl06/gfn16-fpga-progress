"""One isolated A-a storage port on frozen A10 point087bb158.

Data/config/source preparation only; reuse shared packaging and dispatcher.
External32-bit ABI, arithmetic, R=2^32, valid/cycle/reset and full-word checks
are unchanged. No area saving is inferred from declared widths.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/radix22_aa_pointdata27_v1.py'
TEST = 'tests/test_radix22_aa_pointdata27_v1.py'
PARENT = 'rtl/kernel/genefer_a10_banked27_engine_pointlaunch_v3.sv'
PARENT_SHA = '087bb158c0f493e22ed8e49372e233928979ed2161eff11f21f4510d2888c646'
TARGET = 'rtl/kernel/genefer_a10_pointdata27_v1.sv'
RAM = 'rtl/kernel/genefer_sdp_ram27_residue.sv'
RAM_SHA = '1e86ac052d83377fac45637a1f4b2708ce0012700209333f25012b566df0f816'
CPP_PARENT = 'rtl/tb/a10_point_launch_geometry_v3.cpp'
CPP_SHA = '527ea82a6fd8eb9b313e3687aca5fe0ebf35b628d4b437fe3eccd5a61f4b181d'
CPP = 'rtl/tb/radix22_aa_pointdata27_v1.cpp'
VALIDATOR = 'reference/radix22_aa_fault_contract_v1.py'
OLD = 'genefer_sdp_ram32 #(.AW(RW),.DEPTH(DEPTH)) data_ram'
NEW = 'genefer_sdp_ram27_residue #(.AW(RW),.DEPTH(DEPTH)) data_ram'
DOSSIER = ROOT/'queue/fit-r54-controller-v5/terminal/a10-point-sizing'
RECEIPT_SHA = '7b46383863e86716939f260ff3fed7c4d79189b0724f8cbebeb62a65a679e45d'
SYN_SHA = '4c1dc451b685b21715d1d89a579b4c824096b3770160efabfc68243ad7f4bbad'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def need(ok, why):
    if not ok:
        raise ValueError(why)


def source(original=None):
    original = (ROOT/PARENT).read_bytes() if original is None else original
    need(type(original) is bytes and sha(original) == PARENT_SHA, 'exact frozen point parent')
    text = original.decode()
    need(text.count(OLD) == 1 and NEW not in text, 'one data-RAM-only substitution')
    result = text.replace(OLD, NEW)
    need(result.replace(NEW, OLD) == text and 'data_w[bank]>=P' in result,
         'no arithmetic/control/pretruncation-domain change')
    need(sha((ROOT/RAM).read_bytes()) == RAM_SHA, 'verified canonical-storage leaf')
    return result


def audit():
    need(sha((DOSSIER/'receipt.json').read_bytes()) == RECEIPT_SHA, 'actual field fit receipt')
    path = DOSSIER/'evidence/project/output_files/probe.syn.rpt'
    need(sha(path.read_bytes()) == SYN_SHA, 'actual unpruned synthesis report')
    text = path.read_text()
    rows = [line for line in text.splitlines() if line.startswith('; child|child|memories[')
            and '.data_ram|' in line and 'Simple Dual Port' in line]
    banks = set()
    for row in rows:
        f = [x.strip() for x in row.split(';')[1:-1]]
        banks.add(int(re.search(r'memories\[(\d+)\]', f[0])[1]))
        need(f[3:10] == ['512', '32', '512', '32', '16384', '512', '32']
             and f[10:13] == ['512', '32', '16384'], 'logical and implemented data-RAM widths32')
    need(len(rows) == 128 and banks == set(range(128)), 'complete actual128-bank width inventory')
    protected = sorted(set(re.findall(r'child\|child\|arithmetic\[(\d+)\]\.point_lhs_q\[(2[7-9]|3[01])\]', text)))
    need(len(protected) == 15, 'actual protected-register high-bit sample')
    legacy = ROOT/'results/throughput-20260929/ntt27-prefetch-data27/full-v2'
    check = json.loads((legacy/'correctness-normalized.json').read_text())
    need(sha((legacy/'verification.json').read_bytes()) == 'b369a1f4cb94208fb34da145fe2b9dfee5c809b38b6ae87b556beb1e3f073a35'
         and sha((legacy/'correctness-normalized.json').read_bytes()) == 'd37ca006362ded8863bae73473e53350942b9d749006ff7d5f65e2f7281e9c53'
         and check['scope']['type'] == 'isolated data-RAM-only prefetch engine', 'verified old data27 scope, not whole arithmetic')
    return dict(status='PASS_measured_unpruned_RAM32_and_protected_high_bit_sample', receipt_sha256=RECEIPT_SHA,
                synthesis_sha256=SYN_SHA, banks32=128, implemented_data_RAM_bits=128*512*32,
                protected_high_bit_register_sample=protected, sample_is_partial=True,
                existing_verified_delta='RAM storage27/zeroextend32 only; not a new arithmetic profile',
                new_area_saving_measured=False, expected_cycle_delta=0, hardware_noncanonical_rejection_NOT_proved=True)


def cpp_source():
    original = (ROOT/CPP_PARENT).read_text()
    need(sha(original.encode()) == CPP_SHA, 'frozen point geometry oracle')
    old = 'fault=="--negative-counter","A10_FAULT_ARGUMENT");'
    new = ('fault=="--negative-counter" || fault=="--high-bit" || fault=="--bit27" || '
           'fault=="--vector-high-bit" || fault=="--masked-off-high-bit","A10_FAULT_ARGUMENT");')
    anchor = '        reset();d.size_log2=AW;d.profile_size_log2=AW;d.profile_modulus=P;d.profile_format=3;\n'
    extra = '''        if(fault=="--high-bit" || fault=="--bit27" || fault=="--vector-high-bit"){
            const uint32_t bad=fault=="--bit27"?0x08000001u:0x80000001u;
            idle(d);d.host_addr=0;d.write_data=bad;
            if(fault=="--vector-high-bit"){
                d.vector_load_we=1;d.vector_addr=0;d.vector_lane_mask=1;
                for(unsigned lane=0;lane<16;lane++)d.vector_write_data[lane]=lane==0?bad:1;
            }else d.load_we=1;
            std::cout<<"AA_DATA27_HIGHBIT kind="<<fault<<" word="<<bad<<" aw="<<AW<<" field="<<P<<std::endl;
            tick();throw std::runtime_error("AA_DATA27_HIGHBIT_NOT_REJECTED");
        }
        if(fault=="--masked-off-high-bit"){
            idle(d);d.host_addr=0;d.load_we=1;d.write_data=19;tick();
            idle(d);d.vector_load_we=1;d.vector_addr=0;d.vector_lane_mask=0;
            for(unsigned lane=0;lane<16;lane++)d.vector_write_data[lane]=0x80000001u;
            tick();require(!d.host_error,"AA_DATA27_MASKED_DESCRIPTOR");
            idle(d);d.read_en=1;tick();require(d.read_valid && d.read_data==19,"AA_DATA27_MASKED_WRITE_CORRUPTION");
            idle(d);d.rst_n=0;d.load_we=1;d.write_data=0x80000001u;tick();
            idle(d);d.rst_n=1;tick();d.read_en=1;tick();
            require(d.read_valid && d.read_data==19,"AA_DATA27_RESET_WRITE_CORRUPTION");
            idle(d);tick();require(!d.read_valid,"AA_DATA27_STALE_READ");
            std::cout<<"AA_DATA27_MASKED_RESET_PASS aw="<<AW<<" field="<<P<<" cases=2\\n";return 0;
        }
'''
    need(original.count(old) == original.count(anchor) == 1, 'two exact additive fault-harness sites')
    admission = 'static_assert(AW==5 || AW==8,"separately admitted small geometry only");'
    full_admission = 'static_assert(AW==5 || AW==8 || AW==16,"separately admitted geometry only");'
    need(original.count(admission) == 1, 'same existing AW16 geometry admission')
    result = original.replace(old, new).replace(anchor, anchor+extra).replace(admission, full_admission)
    need(result.replace(new, old).replace(anchor+extra, anchor).replace(full_admission, admission) == original, 'ordinary math/cycle/reset oracle unchanged')
    return result


def role(aw, field):
    from fpga.reference import a10_point_launch_prepare_v3 as parent
    need(sha((ROOT/'reference/a10_point_launch_prepare_v3.py').read_bytes()) == 'aa914876a9ebfc466696337f08a36096978eca30aa94e002bb9efbaf7e25e44a', 'reused role API pin')
    need((ROOT/TARGET).read_text() == source() and (ROOT/CPP).read_text() == cpp_source(), 'exact additive source bytes')
    if aw == 16:
        from fpga.reference import a10_point_launch_prepare_v4 as full
        manifest, files = full.role(16, field, allow_full_constants=True)
    else:
        manifest, files = parent.role(aw, field)
    files[TARGET], files[RAM], files[CPP] = (ROOT/TARGET).read_bytes(), (ROOT/RAM).read_bytes(), (ROOT/CPP).read_bytes()
    for name in (SELF, TEST, VALIDATOR):
        files[name] = (ROOT/name).read_bytes()
    manifest['build']['sv_sources'] = [TARGET if x == PARENT else x for x in manifest['build']['sv_sources']] + [RAM]
    manifest['build']['cpp_source'] = CPP
    prime = parent.batch.old.math.FIELDS[field].p
    manifest['steps'] += [dict(name='masked-reset-payload', argv=['{exe}', '--masked-off-high-bit'], expected_returncode=0,
        expected_stdout=f'AA_DATA27_MASKED_RESET_PASS aw={aw} field={prime} cases=2\n', expected_stderr='')]
    if aw == 5 and field == 0:
        for kind in ('--high-bit', '--bit27', '--vector-high-bit'):
            manifest['steps'].append(dict(name=kind[2:], argv=['{exe}', kind], expected_returncode=-6,
                validator=dict(source=VALIDATOR, function='validate', config=dict(kind=kind, aw=aw, field=prime,
                    engine_sha256=sha(files[TARGET]), ram_sha256=RAM_SHA), assets=dict(engine=TARGET, ram=RAM))))
    manifest['sources'] = {name: sha(raw) for name, raw in files.items()}
    manifest['scope'] = 'A-a RAM-only27 port on exact frozen point parent; external32/MontR2^32/ordinary oracle/counters unchanged. Field-only, no upper/A-next integration or physical claim.'
    manifest['aa_data27'] = dict(parent_sha256=PARENT_SHA, ram_sha256=RAM_SHA, delta='ONE RAM leaf substitution; full32 pretruncation check remains',
        cycle_delta_source_prediction=0, simulation_fatal_expected_SIGABRT_not_rc1=True,
        hardware_runtime_caller_admission_not_changed=True, whole_core_promotion=False)
    return manifest, files


def project(output):
    """Mechanical source-only successor of the exact measured point project."""
    parent = ROOT/'results/throughput-20260929/a10-point-field-probe-v3/project-workers6'
    old = json.loads((parent/'manifest.json').read_text())
    need(sha((parent/'manifest.json').read_bytes()) == '99816830cde736bbade38a841fc962dcb735e81af7e84f846f1bf8349a862ec0', 'matched measured point field project')
    output = Path(output).resolve()
    need(not output.exists() and output.parent.is_dir(), 'fresh candidate source project')
    need((ROOT/TARGET).read_text() == source(), 'exact candidate source before project')
    files = {name: (parent/'rtl'/name).read_bytes() for name in old['source_sha256']}
    need(all(sha(raw) == old['source_sha256'][name] for name, raw in files.items()), 'frozen nine-RTL closure')
    files.pop(Path(PARENT).name)
    files[Path(TARGET).name], files[Path(RAM).name] = (ROOT/TARGET).read_bytes(), (ROOT/RAM).read_bytes()
    output.mkdir(); (output/'rtl').mkdir()
    for name, raw in files.items():
        with (output/'rtl'/name).open('xb') as stream: stream.write(raw)
    for name, pin in old['control_sha256'].items():
        raw = (parent/name).read_bytes(); need(sha(raw) == pin, 'unchanged parent control')
        if name == 'probe.qsf':
            anchor = ('set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+Path(PARENT).name+'\n').encode()
            need(raw.count(anchor) == 1, 'one source-file QSF replacement')
            raw = raw.replace(anchor, ('set_global_assignment -name SYSTEMVERILOG_FILE rtl/'+Path(TARGET).name+'\nset_global_assignment -name SYSTEMVERILOG_FILE rtl/'+Path(RAM).name+'\n').encode())
        with (output/name).open('xb') as stream: stream.write(raw)
    m = dict(old, schema='aa-pointdata27-field-sizing-v1', target='A_a_point_data27_registered_AW16_F0',
        source_sha256={name: sha(raw) for name,raw in files.items()}, control_sha256={name: sha((output/name).read_bytes()) for name in old['control_sha256']},
        status='source_only_candidate_native_pending', matched_parent_manifest_sha256=sha((parent/'manifest.json').read_bytes()),
        delta='RAM leaf32→verified27 storage/zeroextend; all externalABI/arithmetic/control/clock/seed/boundary unchanged',
        new_child_full_N_native_gate_pending=True, physical_timing_proven=False, promotion_allowed=False)
    save(output/'manifest.json', m)
    return dict(project=str(output), manifest_sha256=sha((output/'manifest.json').read_bytes()), sources=len(files), native_pending=True)


def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2); stream.write('\n')


def prepare(output):
    from fpga.tools import native_class_package_v2 as package
    from fpga.cloud import host_hours_admit_v1 as meter
    need(sha(Path(package.__file__).read_bytes()) == '03b6a81aa7d465487da97f854a79e9e43a19c9c637db6178587cfac02476f604'
         and sha(Path(meter.__file__).read_bytes()) == '6fd1904025f4d76557497dba2eac2a5514b419a799c8616b177bc696f051379a', 'shared package/accounting pins')
    need(not any((ROOT/name).exists() for name in ('docs/briefs/PAUSE', 'queue/PAUSE')), 'PAUSE')
    output = Path(output).resolve(); need(not output.exists() and output.parent.is_dir(), 'fresh one-candidate packet root')
    audit(); output.mkdir(); hours = meter.admit('gcp-c4d', 3715); save(output/'host-hours.json', hours)
    budget = dict(provider='gcp', observed_at=hours['observed_at_utc'], total_allowance_usd=100,
                  planning_usd_per_hour=hours['hourly_rate_usd'], remaining_after_reserves_usd=hours['remaining_total_after_storage_usd'],
                  actual_billing=False, source_receipt_sha256=sha((output/'host-hours.json').read_bytes()))
    save(output/'budget.json', budget); jobs=[]
    for aw, field in ((5,0), (5,1), (5,2), (8,0), (16,0)):
        m, files = role(aw, field); case = output/f'aw{aw}-f{field}'; src=case/'source/fpga'; src.mkdir(parents=True)
        for name, raw in files.items():
            path=src/name; path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as stream: stream.write(raw)
        manifest=case/'manifest.json'; save(manifest,m); variants=[]
        for pair in ('01','23'):
            profile=f'gcp-c4d-static{pair}-v1'; worker=f'aa-pointdata27-aw{aw}-f{field}-{pair}-v1'; packet=case/('packet-'+pair)
            result=package.prepare(manifest,src,profile,worker,'run',packet,output/'budget.json')
            variants.append(dict(archive=str(packet/'package.tar.gz'),sha256=result['archive_sha256'],ticket_sha256=result['ticket_sha256'],manifest_sha256=sha((packet/'manifest.json').read_bytes()),
                profile=profile,worker_id=worker,native_root=result['native_root'],runner='tools/native_class_package_v2.py',runner_sha256=sha(Path(package.__file__).read_bytes()),
                stager=str(ROOT/'tools/native_package_v4.py'),stager_sha256=sha((ROOT/'tools/native_package_v4.py').read_bytes()),
                stager_dependencies=[dict(path=str(ROOT/'tools'/n),sha256=sha((ROOT/'tools'/n).read_bytes())) for n in ('native_package_v3.py','native_package_v2.py')],max_seconds=3700))
        qid=f'aa-pointdata27-aw{aw}-f{field}-q1-v1'
        q=dict(schema='gfn16-global-ticket-v1',id=qid,candidate_id='aa-pointdata27-v1',owner='radix22-sol',priority='P2',kind='sim',needs='verilator',
            created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),tool_identity='gcp-c4d-verilator5032-gcc15-python314-v1',
            resources=dict(cores=2,threads=1,ram_gib=8,scratch_gib=4),est_minutes=5,promotion_bound=False,packages=variants,
            source_gate=dict(parent_sha256=PARENT_SHA,candidate_sha256=sha(files[TARGET]),existing_RAM27_sha256=RAM_SHA,expected_cycle_delta=0,no_arithmetic_profile_change=True))
        if aw==8: q.update(after=[f'aa-pointdata27-aw5-f{x}-q1-v1' for x in range(3)],on='PASS_expected_contracts')
        if aw==16: q.update(after=['aa-pointdata27-aw8-f0-q1-v1'],on='PASS_expected_contracts')
        save(case/'global-ticket.json',q); jobs.append(dict(id=qid,path=str(case/'global-ticket.json'),sha256=sha((case/'global-ticket.json').read_bytes()),packages=variants))
    result=dict(status='prepared_ONE_A_a_RAM27_candidate_five_bounded_roles_NOT_dispatched',audit=audit(),jobs=jobs,
                field_project=project(output/'candidate-field-workers6'),native_executed=False,vendor_executed=False,promotion_allowed=False)
    save(output/'preparation.json',result); return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path);parser.add_argument('--print-source',action='store_true');parser.add_argument('--print-cpp',action='store_true')
    args=parser.parse_args()
    if args.print_source: print(source(),end='')
    elif args.print_cpp: print(cpp_source(),end='')
    else: print(json.dumps(prepare(args.output) if args.output else audit(),indent=2))
