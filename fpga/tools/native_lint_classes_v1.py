"""Pure conservative r38 lint classifier for new -Wall -Wno-fatal runs.

No executions, warning suppression, per-line baseline waiver, or source edits.
The caller separately proves command/tool/source closure and retains raw logs.
Old warning-fatal nonzero/%Error observations remain failures unchanged.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


STYLE = frozenset({'UNUSEDSIGNAL', 'UNUSEDPARAM', 'PINCONNECTEMPTY', 'GENUNNAMED',
                   'DECLFILENAME', 'VARHIDDEN', 'SYNCASYNCNET'})
FATAL = frozenset({'UNOPTFLAT', 'LATCH', 'MULTIDRIVEN', 'CASEINCOMPLETE', 'SELRANGE',
                   'IMPLICIT', 'COMBDLY', 'BLKANDNBLK', 'ALWCOMBORDER', 'UNDRIVEN', 'PINMISSING'})
HEADER = re.compile(rb'^%Warning-([A-Z][A-Z0-9_]*):[ \t]+\S.*$')
MAX_LOG_BYTES = 16 * 1024 * 1024


class LintClassError(ValueError):
    """Rejected lint, with the exact log/class receipt when inputs are typed."""
    def __init__(self, message, receipt=None):
        super().__init__(message)
        self.receipt = receipt


def need(ok, why):
    if not ok:
        raise LintClassError(why)


def classify(returncode, stdout, stderr, manifest, root):
    """Return a JSON receipt for rc0 style-only/clean logs, otherwise raise.

    All UNDRIVEN and PINMISSING are conservatively fatal. A manifest assertion
    that a pin is open/output is not proof and cannot waive either warning.
    WIDTH* and every listed defect apply to changed and inherited source.
    """
    need(type(returncode) is int, 'typed native lint returncode')
    need(type(stdout) is bytes and type(stderr) is bytes, 'raw byte stdout/stderr required')
    need(type(manifest) is dict, 'JSON manifest object required')
    need(isinstance(root, Path) and root.is_absolute() and root.is_dir() and root.resolve() == root,
         'canonical existing source root required')
    try:
        manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    except (TypeError, ValueError) as error:
        raise LintClassError('finite JSON manifest required') from error
    receipt = dict(schema='native-lint-classes-v1', status='classification_pending',
        policy='B20261001-r38 conservative class policy v1', returncode=returncode,
        stdout_sha256=hashlib.sha256(stdout).hexdigest(), stderr_sha256=hashlib.sha256(stderr).hexdigest(),
        stdout_bytes=len(stdout), stderr_bytes=len(stderr), source_root=str(root),
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        warning_count=0, class_counts={}, style_class_counts={}, fatal_class_counts={},
        unknown_class_counts={}, malformed_diagnostics=[], error_streams=[],
        exploration_only=True, promotion_admission=False,
        required_caller_checks='actual -Wall -Wno-fatal command, pinned tools, complete source closure, raw-log retention and remaining native/resource/output guards',
        conservative_unproven_classes=['PINMISSING', 'UNDRIVEN'])
    reasons, counts = [], Counter()
    for stream, raw in (('stdout', stdout), ('stderr', stderr)):
        if len(raw) > MAX_LOG_BYTES:
            reasons.append(stream + ' exceeds bounded16MiB diagnostic log')
            continue
        if b'\0' in raw or b'\x1b' in raw:
            reasons.append(stream + ' contains NUL/ANSI diagnostic ambiguity')
            continue
        try:
            raw.decode('utf-8', errors='strict')
        except UnicodeDecodeError:
            reasons.append(stream + ' is not UTF-8 diagnostic text')
            continue
        if b'%Error' in raw:
            receipt['error_streams'].append(stream)
        for number, line in enumerate(raw.splitlines(), 1):
            if b'%Warning' not in line:
                continue
            stripped = line.lstrip(b' \t')
            match = HEADER.fullmatch(stripped)
            # Native source/continuation excerpts may quote a warning token.
            # They are not new headers; unexpected wrapper/prefix text is not
            # allowed to hide a diagnostic. Multiple tokens in a header fail.
            if re.match(rb'^\s*[0-9]+\s*\|', line) and not stripped.startswith(b'%Warning'):
                continue
            if match is None or stripped.count(b'%Warning') != 1:
                receipt['malformed_diagnostics'].append(dict(stream=stream, line=number,
                    line_sha256=hashlib.sha256(line).hexdigest()))
                continue
            counts[match[1].decode('ascii')] += 1
    receipt['class_counts'] = dict(sorted(counts.items()))
    receipt['warning_count'] = sum(counts.values())
    receipt['style_class_counts'] = {name: count for name, count in sorted(counts.items()) if name in STYLE}
    receipt['fatal_class_counts'] = {name: count for name, count in sorted(counts.items())
        if name.startswith('WIDTH') or name in FATAL}
    receipt['unknown_class_counts'] = {name: count for name, count in sorted(counts.items())
        if name not in STYLE and name not in FATAL and not name.startswith('WIDTH')}
    if returncode != 0:
        reasons.append('genuine nonzero native lint exit')
    if receipt['error_streams']:
        reasons.append('native %Error is never waived, including old warning-only trailers')
    if receipt['malformed_diagnostics']:
        reasons.append('unknown/malformed diagnostic header')
    if receipt['fatal_class_counts']:
        reasons.append('nonwaivable defect/unproven warning class: ' + ','.join(receipt['fatal_class_counts']))
    if receipt['unknown_class_counts']:
        reasons.append('unknown warning class: ' + ','.join(receipt['unknown_class_counts']))
    if reasons:
        receipt['status'] = 'blocked_lint_classes'
        receipt['reasons'] = reasons
        raise LintClassError('; '.join(reasons), receipt)
    receipt['status'] = 'admitted_lint_classes_exploration_ONLY'
    receipt['classification'] = 'style_only' if counts else 'no_warnings'
    return receipt
