"""R86 read-only C2 state attribution and finite scalar lifetime analysis.

No RTL generation, HDL execution, oracle arithmetic, or fit admission. Counts
come from disjoint OWN columns of existing synthesis reports. The proposed
physical-bank lifetime is a closed-host calendar hypothesis, not a new ABI.
"""
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/throughput-20260929/trackS-p16-two-context-synthesis-v1'
TERMINAL = ROOT / 'queue/standing-fit-state/terminal'
PARENT = 's4-p16-packed-parent-matched-syn-v2'
CANDIDATE = 's4-p16-c2-explicit-synthesis-screen-v2'
EXPECTED_TOP = 'cb734faeef4ebe4e95d8a6924e8467253d66e686a0aaa5ec13b2c2cca8bd9e3b'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def own_rows(text):
    """Never add inclusive hierarchy totals to their descendants."""
    rows = {}
    in_table = False
    for line in text.splitlines():
        cells = [v.strip() for v in line.split(';')[1:-1]]
        if cells and cells[0] == 'Compilation Hierarchy Node':
            in_table = True
            continue
        if in_table and len(cells) == 12 and re.match(r'\d+ \(', cells[1]):
            name = cells[9]
            if name in rows:
                raise ValueError('duplicate own hierarchy row')
            rows[name] = [int(re.search(r'\((\d+)\)', cells[i])[1]) for i in (1, 2)]
        elif in_table and not line.strip():
            in_table = False
    if not rows:
        raise ValueError('missing own hierarchy')
    return rows


def field_category(path):
    if not path:
        return 'table/controller root'
    if path == 'term_producer':
        return 'term storage/controller root'
    if path in ('forward_transform', 'inverse_transform'):
        return 'CT/GS stage tag pipes'
    if 'shared_shuffle' in path:
        return 'shuffle tag/control'
    if '.digits' in path:
        return 'digit reducer metadata'
    if '.boundary' in path:
        return 'boundary reducer metadata'
    if path == 'epoch_protocol':
        return 'logical lease controller'
    return 'other field arithmetic/control'


def field_delta(parent, candidate, field):
    result = defaultdict(lambda: [0, 0])
    for name in sorted(set(parent) | set(candidate)):
        match = re.search(r'field' + str(field) + r'(?:\||$)', name)
        if not match:
            continue
        relative = name[match.end():]
        key = field_category(relative)
        for i in (0, 1):
            result[key][i] += candidate.get(name, [0, 0])[i] - parent.get(name, [0, 0])[i]
    return dict(result)


def windows(counts=(4, 4), *, anchor=0, interval=8459, pointwise=4207,
            rows=4096, next_correction=12557, second_correction=8233):
    """Inclusive conservative storage windows, not arithmetic simulation.

    Storage is reserved as early as correction acceptance, even though A/B
    capture and recurrence seeding are later. Keep one extra edge after final
    PW for the registered term consumer. This over-approximates every product
    tail: updates stop four rows early and the captured product bypass is E4.
    """
    if anchor not in (0, 1) or len(counts) != 2 or any(type(v) is not int or not 0 <= v <= 16 for v in counts):
        raise ValueError('bounded counts/anchor')
    if not counts[anchor]:
        raise ValueError('inactive anchor')
    output = []
    for context in (anchor, 1 - anchor):
        for ordinal in range(counts[context]):
            start = ordinal * interval + (0 if context == anchor else interval // 2)
            correction = ((0 if context == anchor else second_correction) if ordinal == 0
                          else start - interval + next_correction)
            output.append(dict(context=context, ordinal=ordinal, frame=start,
                               begin=correction, end=start + pointwise + rows,
                               last_coefficient_read=start + pointwise + rows - 1,
                               last_update_issue=start + pointwise + rows - 5,
                               last_E4_product_write=start + pointwise + rows - 1,
                               physical=context))
    return sorted(output, key=lambda v: v['begin'])


def check_windows(items, banks=2):
    if type(banks) is not int or banks < 1:
        raise ValueError('positive bank count')
    latest = {}
    gaps = []
    for item in sorted(items, key=lambda v: v['begin']):
        bank = item['physical'] % banks
        if bank in latest:
            gap = item['begin'] - latest[bank]['end']
            if gap <= 0:
                raise ValueError('live arithmetic storage overwritten')
            gaps.append(gap)
        latest[bank] = item
    return min(gaps) if gaps else None


def logical_peak(items, *, release_offset=12511, capacity=4):
    """PRE-edge logical allocation is kept separate from arithmetic storage."""
    live = {}
    peak = 0
    witness = None
    for item in sorted(items, key=lambda v: v['frame']):
        tick = item['frame']
        live = {bank: old for bank, old in live.items() if old['frame'] + release_offset >= tick}
        free = next((bank for bank in range(capacity) if bank not in live), None)
        if free is None:
            raise ValueError('logical lease capacity')
        live[free] = item
        if len(live) > peak:
            peak = len(live)
            witness = dict(tick=tick, logical_banks={str(bank): [old['context'], old['ordinal']]
                                                   for bank, old in live.items()})
    return dict(peak=peak, witness=witness)


class PhysicalOwners:
    """Pure control witness: physical storage != logical frame allocation.

    Tuple order is bank2/context1/epoch16/generation8. Raw work is still allowed
    after cancellation; only its publication eligibility changes. reset clears
    validity, and upstream reset-valid pipelines must suppress old tokens.
    """
    def __init__(self):
        self.reset()

    def reset(self):
        self.owners = [None, None]
        self.ready_bits = [False, False]

    @staticmethod
    def context(owner):
        if len(owner) != 4 or any(type(v) is not int for v in owner) or any(
                not 0 <= value < limit for value, limit in zip(owner, (4, 2, 65536, 256))):
            raise ValueError('full owner tuple')
        return owner[1]

    def reserve(self, owner):
        context = self.context(owner)
        if self.owners[context] is not None:
            raise ValueError('occupied physical bank')
        self.owners[context] = tuple(owner)
        self.ready_bits[context] = False

    def cache(self, owner, *, physical_valid=True):
        context = self.context(owner)
        if not physical_valid or self.owners[context] != tuple(owner):
            return False
        self.ready_bits[context] = True
        return True

    def consume(self, owner, *, enabled=True, live_generation=None):
        context = self.context(owner)
        if self.owners[context] != tuple(owner) or not self.ready_bits[context]:
            raise ValueError('full owner not ready')
        return enabled and (live_generation is None or owner[3] == live_generation)

    def retire_raw(self, owner):
        context = self.context(owner)
        if self.owners[context] != tuple(owner):
            raise ValueError('stale raw retirement')
        self.owners[context] = None
        self.ready_bits[context] = False


def resource_group(name):
    match = re.search(r'field[012](?:\||$)', name)
    if match:
        return match[0].rstrip('|')
    if '.carry' in name:
        return 'carry'
    if '.crt' in name:
        return 'CRT'
    if 'final_image' in name or name.startswith('scratch'):
        return 'canonical'
    if name.startswith(('host_image', 'shadows')):
        return 'shadows'
    if 'setup' in name:
        return 'setup'
    return 'other controller'


def group_rows(rows):
    grouped = defaultdict(lambda: [0, 0])
    for name, values in rows.items():
        target = grouped[resource_group(name)]
        for i in (0, 1):
            target[i] += values[i]
    return dict(grouped)


def ram_groups(text, *, kind='all'):
    grouped = defaultdict(int)
    for line in text.splitlines():
        cells = [v.strip() for v in line.split(';')[1:-1]]
        if len(cells) != 14 or cells[1] not in ('AUTO', 'M20K block', 'MLAB'):
            continue
        if kind == 'non_MLAB' and cells[1] == 'MLAB':
            continue
        if kind == 'MLAB' and cells[1] != 'MLAB':
            continue
        name = cells[0]
        group = resource_group(name)
        if group.startswith('field'):
            group = 'field root RAM' if 'root' in name else 'field delay/tag RAM' if 'shuffle' in name else 'field table RAM'
        grouped[group] += int(cells[12])
    return dict(grouped)


def analyze():
    project = BASE / 'source-explicit-v2/project'
    manifest_path = project / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for name, digest in manifest['source_sha256'].items():
        if sha(project / 'rtl' / name) != digest:
            raise ValueError('C2 source drift: ' + name)
    for name, digest in manifest['control_sha256'].items():
        if sha(project / name) != digest:
            raise ValueError('C2 control drift: ' + name)
    if manifest['source_sha256'][manifest['top'] + '.sv'] != EXPECTED_TOP:
        raise ValueError('wrong C2 root')
    paths = [TERMINAL / job / 'evidence/project/output_files/probe.syn.rpt' for job in (PARENT, CANDIDATE)]
    report_texts = [p.read_text() for p in paths]
    parent, candidate = [own_rows(t) for t in report_texts]
    groups = [group_rows(rows) for rows in (parent, candidate)]
    ram = [ram_groups(t) for t in report_texts]
    non_mlab = [ram_groups(t, kind='non_MLAB') for t in report_texts]
    mlab = [ram_groups(t, kind='MLAB') for t in report_texts]
    deltas = {str(f): field_delta(parent, candidate, f) for f in range(3)}
    field_ff = [sum(v[1] for v in d.values()) for d in deltas.values()]
    if field_ff != [12803] * 3:
        raise ValueError('unexpected field attribution')
    g = manifest['geometry']
    for key, value in {'warm_interval': 8459, 'pointwise_accept': 4207,
                       'rows': 4096, 'next_correction_accept': 12557}.items():
        if g[key] != value:
            raise ValueError('calendar drift: ' + key)
    host = (project / 'rtl' / (manifest['top'] + '.sv')).read_text()
    if 'CONTEXT_OFFSET=4229,SECOND_CORRECTION=8233;' not in host:
        raise ValueError('host offset drift')
    minima = []
    cases = 0
    for anchor in (0, 1):
        for first in range(1, 17):
            for second in range(17):
                counts = (first, second) if anchor == 0 else (second, first)
                gap = check_windows(windows(counts, anchor=anchor))
                if gap is not None:
                    minima.append(gap)
                cases += 1
    return dict(
        schema='stream27-c2-state-analysis-v1', scope='source/report/scalar analysis ONLY; author, not promotion review',
        inputs={str(p.relative_to(ROOT)): sha(p) for p in [manifest_path, *paths,
            BASE / 'resource-breakdown.json', ROOT / 'reference/stream27_shared_field_contexts.py',
            ROOT / 'reference/stream27_host_contexts.py', ROOT / 'reference/stream27_threefield_contexts.py',
            ROOT / 'reference/stream27_warm_contexts.py']},
        validated_source_files=len(manifest['source_sha256']), validated_controls=len(manifest['control_sha256']),
        source_root=EXPECTED_TOP, disjoint_field_delta_ALUT_FF=deltas,
        disjoint_whole_delta_ALUT_FF={k: [groups[1].get(k, [0, 0])[i] - groups[0].get(k, [0, 0])[i]
                                         for i in (0, 1)] for k in sorted(set(groups[0]) | set(groups[1]))},
        separate_RAM_bit_delta={k: ram[1].get(k, 0) - ram[0].get(k, 0) for k in sorted(set(ram[0]) | set(ram[1]))},
        separate_AUTO_or_M20K_bit_delta={k: non_mlab[1].get(k, 0) - non_mlab[0].get(k, 0)
                                       for k in sorted(set(non_mlab[0]) | set(non_mlab[1]))},
        separate_MLAB_bit_delta={k: mlab[1].get(k, 0) - mlab[0].get(k, 0)
                                for k in sorted(set(mlab[0]) | set(mlab[1]))},
        synthesized_unit_counts={
            'correction transforms': sum(n.endswith('|correction_transform|engine') for n in candidate),
            'term product pools': sum(n.endswith('|term_producer|products') for n in candidate),
            'CRT lanes': sum(bool(re.search(r'\.crt$', n)) for n in candidate),
            'carry lanes': sum(bool(re.search(r'\.carry$', n)) for n in candidate),
            'shared setup': sum(n.endswith('|shared_setup') for n in candidate),
            'canonical scratch': int('scratch' in candidate),
            'descriptor queues': sum(bool(re.fullmatch(r'descriptors\[[01]\]\.fifo', n)) for n in candidate)},
        total_own_FF_delta=sum(v[1] for v in candidate.values()) - sum(v[1] for v in parent.values()),
        shared=['one correction transform and term multiplier pool per field',
                'one setup unit, two retained profile snapshots', 'one CRT/P carry datapath',
                'one canonical scratch and ordered publication/copy controller'],
        duplicated_state=['four logical lease records; four A/B coefficient and term-recurrence banks',
                          'two shadow image planes and two descriptor queues',
                          'per-context job/profile/cold/final-correction/publication state'],
        hypothesis=dict(name='two physical arithmetic banks, four unchanged logical frame leases',
            selector='context bit owner[24] for A/B and term_data/row/valid; retain complete bank+context+epoch+generation owner',
            bounded_cases=cases, minimum_conservative_reuse_gap=min(minima),
            payload_bits_per_field=2 * 16 * 27 * 2 + 2 * 4 * 16 * 27,
            payload_bits_three_fields=3 * (2 * 16 * 27 * 2 + 2 * 4 * 16 * 27),
            window_examples=windows((3, 3)),
            logical_leases=logical_peak(windows((3, 3))),
            requirements=['closed host per-context I8459 and fixed cold fence; do not apply to arbitrary low-level frame API',
                'do not free logical leases at PW end: raw inverse/sink tails continue to last_sink12511',
                'no old producer write or consumer read after storage recycle; preserve E4 product bypass and II1',
                'owner cache join and same-edge pending-fault/raw-tail semantics remain full-width',
                'logical-to-physical table selection and cache readiness must translate consistently; no bank-ID truncation in carried tuple',
                'reset/quarantine revoke validity without payload reset; malformed early reuse must reject',
                'preserve cross-context correction seed/PW shared port exclusion and both-base profiles'],
            measured_saving=None, ALM_or_LAB_credit=None, adoption=False),
        term_MLAB_alternative=dict(
            logical_four_bank_data_bits=4 * 4 * 16 * 27,
            two_bank_FF_data_bits=2 * 4 * 16 * 27,
            flattened_depth=16, flattened_width=432,
            wide_MLAB_shape=[32, 20], wide_MLAB_count_estimate=22,
            lane_separated_MLAB_count_estimate=32,
            MLAB_ALM_capacity_units_estimate=[220, 320],
            capacity_source='https://www.intel.com/programmable/technical-pdfs/683461.pdf',
            scope='geometric storage-capacity comparison only, NOT actual ALM/LAB saving or whole credit',
            ports='one product write and one current-term read per edge; same-row E4 bypass mandatory',
            latency='existing unregistered selection must survive a proven MLAB implementation, or prefetch needs a separately source-qualified calendar; adding a read edge is not free',
            controls='full owner/row/valid outside data RAM; no payload reset, only existing validity reset',
            verdict='may beat two-bank FF pure storage capacity, but FF co-packing/read mux/output FF/ports/timing are unmeasured; do not prefer/adopt from this estimate'),
        caveats=['C1/C2 different root/ABI/profile/full-owner widths, not an isolated context toggle',
                 'field root/term own FF include metadata and inferred RAM; nominal payload bits are not mapped FF credit',
                 'tag FIFO RAM width growth is separate from CT/GS FF; compacttag owner must measure dictionary/full-output paths',
                 'no new RTL, native arithmetic, fit, placed resource, timing or spending claim'])


if __name__ == '__main__':
    print(json.dumps(analyze(), indent=2, sort_keys=True))
