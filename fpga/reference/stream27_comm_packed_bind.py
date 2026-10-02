"""Incremental lockstep delay packing; never counts existing P1/P2 savings.

The qualified shared-stage controller is unchanged. This binds two wide delay
words instead of 2*PAIRS data memories plus two tag memories. MLAB/M20K/LAB
mapping is a measurement, not a source-level saving.
"""
from copy import deepcopy
import hashlib
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SELF = 'reference/stream27_comm_packed_bind.py'
PARENT = ('results/throughput-20260929/trackS-p16-diet-analysis-v1/'
          'commutator-shared-mlab-v1/rtl/'
          'genefer_stream27_mdc_commutator_shared_mlab_v1.sv')
LEAF = 'rtl/kernel/genefer_stream27_mdc_commutator_shared_packed_v1.sv'
OLD = 'genefer_stream27_mdc_commutator_shared_mlab_v1'
NEW = 'genefer_stream27_mdc_commutator_shared_packed_v1'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def need(ok, label):
    if not ok:
        raise ValueError(label)


def control_projection(text):
    """Compare every controller/fault/reset line, not a boolean approximation."""
    start = text.index(' genefer_stream27_delay_mlab_v1 #') if OLD in text else text.index(' localparam int unsigned PACKED_W=')
    end = text.index(' always_ff @(posedge clk or negedge rst_n)begin', start)
    text = text[:start] + text[end:]
    return text[text.index(' localparam int unsigned COUNT_W='):]


def bind(bundle, *, enabled=1):
    need(type(enabled) is int and enabled in (0, 1), 'S4_PACKED_LITERAL_FLAG')
    out = deepcopy(bundle)
    if not enabled:
        return out
    need('comm_delay_packed' not in out, 'S4_PACKED_ALREADY_BOUND')
    need(out['parameters'].get('COMM_STAGE_SHARED_MLAB') == 1, 'S4_PACKED_SHARED_PARENT')
    files = out['files']
    parent = (ROOT / PARENT).read_text()
    leaf = (ROOT / LEAF).read_text()
    need(files.get(OLD + '.sv') == parent, 'S4_PACKED_PARENT_BYTES')
    need(control_projection(parent) == control_projection(leaf), 'S4_PACKED_CONTROL_IDENTICAL')
    changes = {}
    occurrences = 0
    for name, text in list(files.items()):
        if name == OLD + '.sv' or not name.endswith('.sv'):
            continue
        changed, count = re.subn(r'\b' + OLD + r'\b', NEW, text)
        if count:
            need(re.sub(r'\b' + NEW + r'\b', OLD, changed) == text,
                 'S4_PACKED_INSTANCE_ONLY ' + name)
            files[name] = changed
            changes[name] = {'parent_sha256': sha(text.encode()),
                             'bound_sha256': sha(changed.encode())}
            occurrences += count
    need(occurrences > 0, 'S4_PACKED_CONSUMERS')
    del files[OLD + '.sv']
    files[NEW + '.sv'] = leaf
    out['rtl_sources'] = [name for name in files if name.endswith('.sv')]
    out['source_dependencies'] = list(dict.fromkeys(out['source_dependencies'] + [SELF, LEAF, PARENT]))
    out['source_sha256'] = {path: sha((ROOT / path).read_bytes()) for path in out['source_dependencies']}
    out['generated_sha256'] = {name: sha(text.encode()) for name, text in files.items()}
    out['comm_delay_packed'] = {
        'flag': 1, 'parent_leaf_sha256': sha(parent.encode()),
        'new_leaf_sha256': sha(leaf.encode()), 'identifier_changes': changes,
        'identifier_occurrences': occurrences, 'calendar_changed': False,
        'fault_control_changed': False, 'physical_savings_measured': False,
        'whole_P16_GO': False,
    }
    return out
