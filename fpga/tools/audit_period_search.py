"""Finite fixed-layout period selection from collected native audit receipts.

No execution, source edits, Fmax inference or promotion. The caller supplies
source-verified automatic collections and enforces financial/runtime bounds.
"""
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

KINDS = ('setup', 'hold', 'recovery', 'removal', 'mpw')


def ps(value):
    result = Decimal(str(value))*1000
    if result != result.to_integral_value() or int(result) % 2 or not 2000 <= result <= 100000:
        raise ValueError('qualified 2ps period in 2..100ns required')
    return int(result)


def even(value, rounding):
    return int((Decimal(value)/2).to_integral_value(rounding=rounding))*2


def measured(phase):
    margins = {}
    closes = True
    for kind in KINDS:
        rows = [corner[kind] for corner in phase['corners'].values()
                if corner[kind]['status'] == 'measured']
        if kind in ('setup', 'hold', 'mpw') and not rows:
            raise ValueError('missing required measured timing kind')
        for row in rows:
            slack = Decimal(str(row['slack_ns']))
            tns = Decimal(str(row['tns_ns']))
            if not slack.is_finite() or not tns.is_finite():
                raise ValueError('nonfinite native timing')
            actual = slack >= 0 and tns == 0 and row['failing_endpoints'] == 0
            if actual != row['closes']:
                raise ValueError('inconsistent typed timing result')
            closes = closes and actual
        if rows:
            margins[kind] = min(Decimal(str(row['slack_ns'])) for row in rows)
    if closes != phase['timing_closes']:
        raise ValueError('inconsistent all-corner timing result')
    return closes, margins


def choose(receipts, project, original_invocation, baseline_ns='10.000', max_selected=8):
    """Return the next explicit selected period, or a scoped terminal decision.

    First action audits only the requested baseline. Each subsequent action
    repeats that baseline plus one distinct selected period. At most eight
    selected runs follow the baseline-only run; no outside-domain claim.
    """
    baseline = ps(baseline_ns)
    if not receipts:
        return dict(action='audit', selected_period_ns=None, reason='source-bound original-clock all-corner baseline')
    trials = {}
    identity = None
    selected_count = 0
    for receipt in receipts:
        if (receipt['project'] != project or receipt['original_invocation'] != original_invocation
                or receipt['fit_commands'] != 0 or receipt['original_unchanged'] is not True
                or receipt['compiled_input_unchanged'] is not True or receipt['terminal_proven'] is not True):
            raise ValueError('exact source-bound collected fixed-layout audit required')
        bound = (receipt['original_tree_sha256'], receipt['qdb_inventory_sha256'])
        if identity is not None and bound != identity:
            raise ValueError('fixed layout changed between periods')
        identity = bound
        if ps(receipt['timing']['baseline']['period_ns']) != baseline:
            raise ValueError('requested baseline drift')
        selected_count += 'selected' in receipt['timing']
        for phase in receipt['timing'].values():
            period = ps(phase['period_ns'])
            observed = measured(phase)
            if period in trials and trials[period] != observed:
                raise ValueError('repeated native period changed')
            trials[period] = observed
    passing = sorted(period for period, (closes, _) in trials.items() if closes)
    best = passing[0] if passing else None
    lower = max((period for period, (closes, _) in trials.items()
                 if not closes and best is not None and period < best), default=None)
    summary = dict(best_passing_period_ns=None if best is None else best/1000,
                   failing_lower_period_ns=None if lower is None else lower/1000,
                   resolution_ps=2, selected_audits=selected_count,
                   scope='fastest passing tested period on this fixed layout; not global or board maximum')
    if best is not None and lower is not None and best-lower == 2:
        return dict(summary, action='complete', reason='adjacent 2ps failing/passing bracket')
    if selected_count >= max_selected:
        return dict(summary, action='bounded_stop', reason='selected-audit limit; unresolved boundary retained')
    if any(margins['hold'] < 0 for _, margins in trials.values()):
        return dict(summary, action='bounded_stop', reason='observed hold violation; no passing-clock inference')
    if best is None:
        period = max(trials)
        margins = trials[period][1]
        adjustment = max(-margins['setup']*1000,
                         -margins.get('recovery', Decimal(0))*1000,
                         -margins['mpw']*2000, Decimal(0))
        candidate = even(Decimal(period)+adjustment+10, ROUND_CEILING)
    else:
        margins = trials[best][1]
        reserve = min(margins['setup']*1000,
                      margins.get('recovery', Decimal(100))*1000,
                      margins['mpw']*2000)
        candidate = even(Decimal(best)-reserve-2, ROUND_FLOOR)
        if lower is not None and not (lower < candidate < best and candidate not in trials):
            candidate = even(Decimal(best+lower)/2, ROUND_FLOOR)
    if candidate < 2000 or candidate > 100000 or candidate in trials:
        return dict(summary, action='bounded_stop', reason='period domain or repeated point reached; boundary unresolved')
    return dict(summary, action='audit', selected_period_ns=f'{candidate/1000:.3f}',
                reason='explicit period selected from measured all-corner margins and finite tested bracket')
