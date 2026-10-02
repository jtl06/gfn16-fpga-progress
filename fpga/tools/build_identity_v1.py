"""Read-only, host-bound native build identity and qualified ELF reuse admission.

No compiler, subprocess, extraction or execution. A matching cache key is not
correctness evidence: reuse also needs an externally pinned successful native
report and independent review. Native tool/cgroup checks remain the caller's job.
"""
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

MAX_BYTES = 512 * 1024 * 1024


def require(ok, why):
    if not ok:
        raise ValueError(why)


def digest_ok(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def stream_sha(stream):
    result = hashlib.sha256()
    size = 0
    while chunk := stream.read(1024 * 1024):
        size += len(chunk)
        require(size <= MAX_BYTES, 'bounded evidence stream')
        result.update(chunk)
    return result.hexdigest()


def sha(path):
    with Path(path).open('rb') as stream:
        return stream_sha(stream)


def regular(root, name):
    root = Path(root)
    rel = PurePosixPath(name)
    require(str(rel) == name and not rel.is_absolute() and '..' not in rel.parts
            and name not in ('', '.'), 'safe evidence relative path')
    require(root.is_dir() and not root.is_symlink(), 'regular evidence root')
    target = root / name
    current = root
    for part in rel.parts:
        current = current / part
        require(not current.is_symlink(), 'no evidence symlinks')
    require(target.is_file() and target.stat().st_nlink == 1
            and target.resolve().is_relative_to(root.resolve()), 'regular evidence file')
    return target


def build_identity(manifest, profile):
    require(manifest.get('schema') == 'native-source-gate-v1', 'source-gate schema')
    sources = manifest.get('sources', {})
    require(sources and all(digest_ok(v) for v in sources.values()), 'source hashes')
    build = manifest['build']
    require(all(name in sources for name in build['sv_sources'] + [build['cpp_source']]),
            'complete compiled source closure')
    require(all(type(v) is int for v in build['parameters'].values()), 'typed parameters')
    require(manifest['probe']['expected_json'] ==
            dict(context_threads=1, model_threads=1, expected_threads=1), 'single-thread ABI')
    require(profile.get('hashes') and all(digest_ok(v) for v in profile['hashes'].values()),
            'tool hashes')
    # Conservatively include the entire snapshot, including ROMs, harness and
    # oracle inputs. Runtime command selection itself does not force a rebuild.
    identity = dict(schema='gfn16-native-build-identity-v1', host=manifest['host'],
                    source_root=manifest['source_root'], sources=sources, build=build,
                    tool_hashes=profile['hashes'], verilator_dir=profile['verilator_dir'],
                    abi='approved-host-linux-x86_64-single-thread', model_threads=1,
                    compile_workers=2)
    identity = json.loads(json.dumps(identity))  # detach mutable caller objects
    encoded = json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()
    return dict(identity=identity, build_key=hashlib.sha256(encoded).hexdigest())


def archive_inventory(path, expected):
    actual = {}
    total = 0
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive:
            name = PurePosixPath(member.name)
            require(member.isfile() and str(name) == member.name and not name.is_absolute()
                    and '..' not in name.parts and member.name not in actual,
                    'unique regular source archive member')
            total += member.size
            require(total <= MAX_BYTES, 'bounded source archive')
            actual[member.name] = stream_sha(archive.extractfile(member))
    require(actual == expected, 'complete archive identity')


def admit_cached_elf(manifest, profile, donor_dir, donor_report_sha, review_path, review_sha):
    donor_dir = Path(donor_dir)
    review_path = Path(review_path)
    require(digest_ok(donor_report_sha) and digest_ok(review_sha), 'external admission pins')
    report_path = regular(donor_dir, 'report.json')
    require(sha(report_path) == donor_report_sha, 'pinned donor report')
    require(sha(regular(review_path.parent, review_path.name)) == review_sha, 'pinned independent review')
    report = json.loads(report_path.read_text())
    review = json.loads(review_path.read_text())
    require(report['status'] == 'completed_native_commands_unreviewed', 'successful donor native run')
    require(review['status'].startswith('PASS_') and review['report_sha256'] == donor_report_sha
            and review['manifest_sha256'] == report['manifest_sha256']
            and review['executable_sha256'] == report['executable_sha256'],
            'independent review binds exact donor executable/report/manifest')
    approved = regular(donor_dir, 'approved-manifest.json')
    require(sha(approved) == report['manifest_sha256'], 'donor manifest pin')
    donor_manifest = json.loads(approved.read_text())
    expected = build_identity(manifest, profile)
    require(build_identity(donor_manifest, profile) == expected, 'exact build identity reuse')
    require(report['sources'] == manifest['sources'] and report['host'] == manifest['host']
            and report['source_root'] == manifest['source_root'], 'host/source closure')
    tools = dict(verilator=Path(profile['verilator_dir'])/'verilator',
                 verilator_bin=Path(profile['verilator_dir'])/'verilator_bin',
                 compiler=Path('/usr/bin/x86_64-linux-gnu-g++-15'),
                 python=Path('/usr/bin/python3.14'), make=Path('/usr/bin/make'),
                 taskset=Path('/usr/bin/taskset'))
    require(report['tool_sha256'] == {str(path): profile['hashes'][key] for key, path in tools.items()},
            'exact donor toolchain')
    require(report['probe'] == manifest['probe']['expected_json'], 'donor runtime thread probe')
    steps = report['steps']
    require([s['name'] for s in steps] == ['verilator-version', 'compiler-version', 'build', 'probe']
            + [s['name'] for s in donor_manifest['steps']], 'complete donor step sequence')
    require(all(s['returncode'] == 0 and s.get('error') is None for s in steps),
            'all donor commands succeeded')
    for name, value in report['artifacts'].items():
        require(sha(regular(donor_dir, name)) == value, 'donor artifact hash: ' + name)
    archive_inventory(regular(donor_dir, 'sources.tar.gz'), report['sources'])
    archive_inventory(regular(donor_dir, 'generated-sources.tar.gz'), report['generated_source_sha256'])
    model = regular(donor_dir, 'model.gz')
    with gzip.open(model, 'rb') as stream:
        header = stream.read(5)
        require(header == b'\x7fELF\x02', '64-bit ELF evidence')
    with gzip.open(model, 'rb') as stream:
        require(stream_sha(stream) == report['executable_sha256'], 'decompressed executable identity')
    return dict(archive_path=str(model), executable_sha256=report['executable_sha256'],
                build_key=expected['build_key'], donor_report_sha256=donor_report_sha,
                independent_review_sha256=review_sha, promotion_allowed=False,
                scope='Reuse only; new invocations still need native receipts and qualification.')
