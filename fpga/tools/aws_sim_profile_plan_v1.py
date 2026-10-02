"""Executable, offline AWS simulation profile proposal; no install or launch.

The observed Ubuntu package hash pins a candidate, not an admitted toolchain.
Emit a separate adapter contract. Frozen v1 profiles and cache helpers stay
unchanged; no foreign ELF is admitted, even if a printed version matches.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


HOST = 'gfn16-aws-m8i'
ROOT = '/home/ubuntu/gfn16-worker'
TOOL_ROOT = ROOT + '/tools/verilator-5.020-ubuntu2404-v1'
DEB_SHA = 'bb74ca8c32c73eb903ee91da64c8b58cfbe095c229967a95782108afb67bb3ca'
DEB_BYTES = 6940528
DEB_NAME = 'verilator_5.020-1_amd64.deb'
KNOWN_TOOLS = {
    'compiler': ('/usr/bin/x86_64-linux-gnu-g++-13', '1353e9bdd29a7295c7226bf6c63abccce056d8cac31f112e5cdbecc3f28c2769'),
    'python': ('/usr/bin/python3.12', 'e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f'),
    'make': ('/usr/bin/make', 'd78b8f1d099fbcfb6f2f49ab87223b9b68fb3956642f92d6ec6de812e8afa965'),
    'taskset': ('/usr/bin/taskset', 'a431738fadddc2e2326c8ab81843e72f4011658379381aef1502a6ddb1c1115b'),
    'perl': ('/usr/bin/perl', '47bdc8a342556c1d140084417ef6cacd79a3362e4b6cc1e4754df55bdf1e3683'),
    'linker': ('/usr/bin/ld', 'e9ceb054c12207970f2726dfc07e9a66b411602748628baf27399f02a9bbb31b'),
    'archiver': ('/usr/bin/ar', '6452af2eea333b8c65e1adb92964fc8f97863ab003fa13f9d12bff5345cd7dbe'),
    'assembler': ('/usr/bin/as', '21aff249b692b5c31a44007491f922dcb49f41323e362c57d2ada3f52eddb7f0'),
}
FROZEN_PINS = {
    'tools/native_source_gate_v1.py': '5205f587313a1403fddabff58bbcf4565d27c8219aa2e0c3f4aaa3af2901c2cd',
    'tools/build_identity_v1.py': 'b0e1ab77c0fc06a6b0cc958061394dad1f990aa52eb1e76d96922c25225788a2',
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def package_fields(text):
    fields = {}
    for row in text.split('\n\n', 1)[0].splitlines():
        if row and not row[0].isspace() and ': ' in row:
            key, value = row.split(': ', 1)
            fields[key] = value
    return fields


def proposal(observation):
    require(observation['schema'] == 'aws-simulation-readonly-inventory-v1'
            and observation['status'] == 'observed_not_admitted_no_install_no_native_execution'
            and observation['host'] == HOST and observation['uid'] == 1000, 'AWS inventory identity')
    require('VERSION_ID="24.04"' in observation['os_release']
            and 'x86_64' in observation['uname']['stdout'], 'Ubuntu24.04 amd64 ABI')
    apt = observation['apt']['verilator']
    require(apt['show']['returncode'] == apt['policy']['returncode'] == 0
            and 'Installed: (none)' in apt['policy']['stdout']
            and 'Candidate: 5.020-1' in apt['policy']['stdout'], 'uninstalled exact apt candidate')
    fields = package_fields(apt['show']['stdout'])
    require(fields.get('Package') == 'verilator' and fields.get('Version') == '5.020-1'
            and fields.get('Architecture') == 'amd64' and fields.get('Origin') == 'Ubuntu'
            and fields.get('SHA256') == DEB_SHA and fields.get('Size') == str(DEB_BYTES)
            and fields.get('Filename') == 'pool/universe/v/verilator/' + DEB_NAME,
            'exact Ubuntu package identity')
    require(not observation['path_tools']['verilator'] and not observation['path_tools']['verilator_bin']
            and all(row['exists'] is False for row in observation['candidate_files']),
            'known-path absence, not existing-tool admission')
    files = {row['path']:row for row in observation['files']}
    for path, digest in KNOWN_TOOLS.values():
        require(files[path]['regular'] and files[path]['sha256'] == digest, 'installed tool pin: ' + path)
    require(files['/usr/bin/g++']['resolved'] == KNOWN_TOOLS['compiler'][0]
            and files['/usr/bin/python3']['resolved'] == KNOWN_TOOLS['python'][0], 'default tool aliases')
    physical = {row['cpu']:(row['package'],row['core']) for row in observation['cpus']}
    selected = [4, 5]
    require(len(set(physical[cpu] for cpu in selected)) == 2
            and not set(physical[cpu] for cpu in selected) & set(physical[cpu] for cpu in range(4)),
            'spare physical-core pair, not fit SMT siblings')
    result = dict(
        schema='aws-simulation-profile-proposal-v1', status='proposed_not_installed_not_admitted_not_dispatched',
        host=HOST, observed_at=observation['observed_at'],
        package=dict(name='verilator', version='5.020-1', architecture='amd64',
                     filename=DEB_NAME, bytes=DEB_BYTES, sha256=DEB_SHA, origin='Ubuntu noble/universe',
                     mode='rootless extraction; no maintainer scripts, apt update/install or sudo'),
        installation_plan=dict(
            approval_required=True, fresh_empty_tool_root=TOOL_ROOT, network_bytes=DEB_BYTES,
            proposed_command_argv=[['/usr/bin/apt-get', 'download', 'verilator=5.020-1'],
                                   ['/usr/bin/dpkg-deb', '--extract', DEB_NAME, TOOL_ROOT]],
            command_cwd='fresh main-created download directory beneath worker root',
            before_extraction='Verify exact .deb byte count/SHA and safe package member paths; reject existing destination.',
            bounds=dict(cpu_percent=100, memory_bytes=1<<30, seconds=300,
                        extraction_allocated_bytes_max=128<<20, retained_download_bytes=DEB_BYTES),
            preservation='Retain package/source and failed extraction; no deletion/retry-in-place.'),
        minimal_dependencies=dict(
            existing=['Python3.12', 'Perl5.38', 'glibc2.39 (package requires>=2.38)', 'GCC13.3 C++17', 'make4.3', 'binutils2.42'],
            new=['exact Ubuntu Verilator binary package'],
            not_required_for_planned_cc_flow=['SystemC recommendation (--sc unused)', 'documentation JS/theme dependencies',
                                              'flex/bison/help2man (not building Verilator source)', 'ccache', 'gtkwave']),
        profile=dict(name='aws-ubuntu2404-verilator5020-gcc13-python312-candidate-v1', base=ROOT,
                     cpus=selected, spare_slot=[4,5,6,7], preserved_fit_slot=[0,1,2,3],
                     lock=ROOT+'/native-compile.lock', verilator_dir=TOOL_ROOT+'/usr/bin',
                     tools={name:dict(path=path, sha256=digest) for name,(path,digest) in KNOWN_TOOLS.items()},
                     pending_tools={name:dict(path=TOOL_ROOT+'/usr/bin/'+name, sha256=None)
                                    for name in ('verilator', 'verilator_bin')},
                     clean_environment=dict(CXX=KNOWN_TOOLS['compiler'][0], CC='/usr/bin/x86_64-linux-gnu-gcc-13',
                                            VERILATOR_ROOT=TOOL_ROOT+'/usr/share/verilator',
                                            PATH=TOOL_ROOT+'/usr/bin:/usr/bin:/bin', CCACHE_DISABLE='1',
                                            PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1', LC_ALL='C', LANG='C'),
                     resource_caps=dict(cpu_percent=200, memory_bytes=4<<30, swap_bytes=0,
                                        compile_workers=2, model_threads=1, job_seconds=3600)),
        launcher_delta=dict(
            future_separate_adapter='tools/native_source_gate_aws_v1.py (not implemented or admitted)',
            frozen_sources_unchanged=FROZEN_PINS,
            changes=['Explicit per-tool paths/hash map instead of hardcoded GCC15/Python3.14.',
                     'Pin VERILATOR_ROOT and complete extracted runtime/include tree; recheck before/after every command.',
                     'Add profile/package/runtime/compiler-backend/ABI/clean-environment identity to a separate cache key.',
                     'Retain source closure, exact stream/output contracts, warning policy, timeout/cgroup/affinity/lock guards.',
                     'Use a fresh source stage and fresh generated C++/ELF; never import aethia/GCP binaries or cache entries.'],
            no_changes=['Quartus installations/evaluation/fit sources', 'native_source_gate_v1 profiles',
                        'build_identity_v1 frozen API', 'finite queue v1 allowed hosts']),
        admission_gates=[
            'Main approves bounded download/extraction; snapshot package SHA and complete extracted file closure.',
            'Record wrapper/native hashes and all used Verilator runtime headers; verify --version exactly5.020.',
            'Record dynamic library/linker/cc1plus/runtime ABI hashes; reject unresolved linkage or tool drift.',
            'Independently review separately pinned adapter/tool profile/source manifest; recheck T5/slot/disjoint cores.',
            'Fresh tiny --cc C++17 build with -Werror=return-type, --threads1/-j2; retain warnings and failure evidence.',
            'Run matching single-thread context/model probe and deterministic oracle with a typed negative control.',
            'Independently replay sources/generated closure/native outputs; only then admit an AWS queue revision.'],
        installed=False, native_execution=False, queue_admission=False, promotion_allowed=False,
        limitations=['Apt metadata from existing indexes, not a package downloaded or signature independently reverified here.',
                     'VERILATOR_ROOT layout/linkage/5.020 warning/API compatibility are candidate assumptions requiring native admission.',
                     'Spare resources are observations, not reservations. Main rechecks live limits before any action.'])
    encoded = json.dumps(result, sort_keys=True, separators=(',', ':')).encode()
    result['proposal_identity_sha256'] = hashlib.sha256(encoded).hexdigest()
    return result


def load_proposal(path, digest):
    require(re.fullmatch('[0-9a-f]{64}', digest or '') and path.is_file()
            and not path.is_symlink() and sha(path) == digest, 'externally pinned observation')
    fpga = Path(__file__).resolve().parents[1]
    for name, expected in FROZEN_PINS.items():
        require(sha(fpga/name) == expected, 'frozen comparison source drift: ' + name)
    result = proposal(json.loads(path.read_text()))
    result['observation_sha256'] = digest
    result['plan_source_sha256'] = sha(Path(__file__))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--inventory-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(load_proposal(args.inventory, args.inventory_sha256), indent=2))
