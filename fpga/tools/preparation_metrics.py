#!/usr/bin/env python3
"""Small, read-only r64 latency summary from explicit readiness/native events.

Input JSON: ready[] has candidate_id, candidate_source_sha256, rtl_ready_at_utc.
runs[] has job_id, the same candidate identity, started_at_utc, optional
finished_at_utc, passed_contract (boolean), and after[] job IDs. Timestamps must
be timezone-aware. Use actual worker-job start/finish, not submit/collection
time. Job start includes its build phase; it is not a claim that the simulation
model has already started. Model-step latency needs separate step timestamps.
The producer defines a frozen candidate snapshot shared by its ladder; this
tool never infers identity from owner names, ticket prefixes, or similar RTL.
"""
import argparse
import datetime as dt
import json
import statistics
from pathlib import Path


def stamp(value):
    if not value:
        return None
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return parsed.timestamp()


def identity(row):
    candidate = row.get("candidate_id")
    source = row.get("candidate_source_sha256")
    return (candidate, source) if candidate and source else None


def median(values):
    return round(statistics.median(values), 3) if values else None


def worker_stamp(value):
    """Accept the worker's UTC systemd timestamp, never collection time."""
    if not value or value == "n/a":
        return None
    try:
        parsed = dt.datetime.strptime(value, "%a %Y-%m-%d %H:%M:%S UTC").replace(tzinfo=dt.timezone.utc)
        return parsed.isoformat()
    except ValueError:
        stamp(value)  # Also permits explicitly timezone-aware ISO timestamps.
        return value


def queue_events(tickets):
    """Adapt automatic queue receipts; use only owner-declared ladder identity.

    Gate hashes describe individual harnesses and are not shared RTL identity.
    Missing historical declarations remain unknown. No tickets are modified.
    """
    ready, runs = [], []
    for ticket in tickets:
        declared = ticket.get("rtl_readiness") or {}
        if declared:
            if identity(declared) is None or not declared.get("rtl_ready_at_utc"):
                raise ValueError("incomplete rtl_readiness declaration")
            ready.append(declared)
        dispatch = ticket.get("dispatch") or {}
        observed = dispatch.get("properties") or {}
        terminal = (ticket.get("result") or {}).get("properties") or {}
        for properties in (observed, terminal):
            if properties and dispatch.get("invocation") and properties.get("InvocationID") != dispatch["invocation"]:
                raise ValueError("worker properties do not match dispatch invocation")
        began = observed.get("ExecMainStartTimestamp") or terminal.get("ExecMainStartTimestamp")
        ended = terminal.get("ExecMainExitTimestamp") or observed.get("ExecMainExitTimestamp")
        runs.append(dict(
            job_id=ticket["id"], candidate_id=declared.get("candidate_id"),
            candidate_source_sha256=declared.get("candidate_source_sha256"),
            started_at_utc=worker_stamp(began), finished_at_utc=worker_stamp(ended),
            test_role=ticket.get("test_role"),
            normal_test_submitted_at_utc=ticket.get("normal_test_submitted_at_utc"),
            passed_contract=(ticket.get("dependency_gate") or {}).get("status") == "PASS_expected_contracts",
            after=[edge["id"] if isinstance(edge, dict) else edge for edge in ticket.get("after") or []],
        ))
    return {"ready": ready, "runs": runs}


def read_queue(directory):
    # Deliberately shallow: package/evidence trees can contain millions of files.
    tickets = []
    for state in ("pending", "running", "done"):
        for path in sorted((directory / state).glob("*.json")):
            tickets.append(json.loads(path.read_text()))
    identifiers = [ticket["id"] for ticket in tickets]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("queue moved during snapshot or has duplicate IDs; retry read-only snapshot")
    return queue_events(tickets)


def summarize(data, start, end):
    """Window includes native starts in [start, end); missing data is not zero."""
    lo, hi = stamp(start), stamp(end)
    if lo is None or hi is None or lo >= hi:
        raise ValueError("invalid time window")
    ready, retired, readiness_conflicts = {}, {}, set()
    for row in data.get("ready", []):
        key, at = identity(row), stamp(row.get("rtl_ready_at_utc"))
        if key is None or at is None:
            raise ValueError("readiness requires explicit candidate/source/time")
        if key in ready and ready[key] != at:
            readiness_conflicts.add(key)
        ready[key] = at
        if row.get("retired_at_utc"):
            retired[key] = stamp(row["retired_at_utc"])
    # Instrumentation uncertainty is not a reason to suppress every other
    # measured job. Exclude ambiguous preparation timestamps, never pick one.
    for key in readiness_conflicts:
        ready.pop(key, None)
    jobs, first, normal, normal_job_delays = {}, {}, {}, []
    for row in data.get("runs", []):
        job = row["job_id"]
        if job in jobs:
            raise ValueError("duplicate job_id; normalize attempts first")
        began, ended = stamp(row.get("started_at_utc")), stamp(row.get("finished_at_utc"))
        if began is not None and ended is not None and ended < began:
            raise ValueError("native finish precedes start")
        jobs[job] = (row, began, ended)
        key = identity(row)
        if began is not None and key is not None:
            first[key] = min(first.get(key, began), began)
        submitted = stamp(row.get("normal_test_submitted_at_utc"))
        if submitted is not None:
            if row.get("test_role") != "normal":
                raise ValueError("normal submission event requires explicit normal role")
            if began is not None and began < submitted:
                raise ValueError("native start precedes accepted normal submission")
            if began is not None and lo <= began < hi:
                normal_job_delays.append(began - submitted)
            if key is not None:
                if key in ready and submitted < ready[key]:
                    raise ValueError("normal submission precedes declared RTL readiness")
                if key not in normal or submitted < normal[key][0]:
                    normal[key] = (submitted, began)
    prep, gaps, dispatch = [], [], []
    missing_ready = missing_edges = missing_identity = 0
    for key, began in first.items():
        if key in ready and began < ready[key]:
            raise ValueError("native start precedes declared RTL readiness")
        if lo <= began < hi:
            if key in ready:
                prep.append(began - ready[key])
            else:
                missing_ready += 1
    for row, began, _ in jobs.values():
        if began is None or not lo <= began < hi:
            continue
        key = identity(row)
        if key is None:
            missing_identity += 1
            continue
        after = row.get("after", [])
        if not after:
            continue
        parents = [jobs.get(parent) for parent in after]
        if any(p is None or p[2] is None or p[0].get("passed_contract") is not True for p in parents):
            missing_edges += 1
            continue
        if any(p[2] > began for p in parents):
            raise ValueError("dependent native start precedes prerequisite finish")
        same = [p for p in parents if identity(p[0]) == key]
        if same:
            gaps.append(began - max(p[2] for p in same))
            dispatch.append(began - max(p[2] for p in parents))
    pending_ages = [hi - at for key, at in ready.items()
                    if at < hi and first.get(key, hi) >= hi
                    and not (key in retired and retired[key] < hi)]
    preparation_to_normal = [submitted - ready[key] for key, (submitted, _) in normal.items()
                             if key in ready and lo <= submitted < hi]
    normal_queue_delays = [began - submitted for submitted, began in normal.values()
                          if began is not None and lo <= began < hi]
    waiting_normal = [hi - submitted for submitted, began in normal.values()
                      if submitted < hi and (began is None or began >= hi)]
    return {
        "window": {"start": start, "end": end},
        "rtl_ready_to_first_run_median_seconds": median(prep),
        "same_candidate_gap_median_seconds": median(gaps),
        "all_prerequisites_ready_to_start_median_seconds": median(dispatch),
        "samples": {"preparation": len(prep), "same_candidate_edges": len(gaps)},
        "operational_readiness": {
            "definition": "Actual accepted first normal-test submission; fault-test preparation never gates this event.",
            "rtl_to_normal_submit_median_seconds": median(preparation_to_normal),
            "normal_submit_to_native_start_median_seconds": median(normal_queue_delays),
            "samples": {"preparation": len(preparation_to_normal), "queue_delay": len(normal_queue_delays)},
            "awaiting_first_normal_start": len(waiting_normal),
            "per_normal_job_submit_to_start_median_seconds": median(normal_job_delays),
            "normal_job_samples": len(normal_job_delays),
            "scope": "Candidate preparation uses declared source identity. Per-normal-job queue delay needs only an explicit accepted normal submission and its own native start; it is not a same-design metric.",
        },
        "coverage_missing": {"readiness": missing_ready, "identity": missing_identity, "prerequisite_evidence": missing_edges, "readiness_conflicts": len(readiness_conflicts)},
        "awaiting_first_run": {"count": len(pending_ages),
                               "at_or_over_target": sum(age >= 600 for age in pending_ages),
                               "oldest_seconds": round(max(pending_ages), 3) if pending_ages else None},
        "targets_seconds": {"preparation_under": 600, "same_candidate_gap_under": 120},
        "scope": "Explicit frozen-candidate identities and worker-job timestamps only; job start includes build, not inferred model execution. No inferred historical readiness. Same-candidate gap includes other dependency waits; ready-to-start separates them.",
    }


def compact_table(result):
    def cell(value):
        return "unknown" if value is None else f"{value:.1f} s"
    missing = result["coverage_missing"]
    normal = result["operational_readiness"]
    return ("| Preparation metric | Median | Target | Samples |\n"
            "|---|---:|---:|---:|\n"
            f"| RTL-ready → first worker-job start | {cell(result['rtl_ready_to_first_run_median_seconds'])} | <600 s | {result['samples']['preparation']} |\n"
            f"| RTL → normal submitted | {cell(normal['rtl_to_normal_submit_median_seconds'])} | diagnostic | {normal['samples']['preparation']} |\n"
            f"| Normal job submitted → worker start | {cell(normal['per_normal_job_submit_to_start_median_seconds'])} | diagnostic | {normal['normal_job_samples']} |\n"
            f"| Same-candidate predecessor → next start | {cell(result['same_candidate_gap_median_seconds'])} | <120 s | {result['samples']['same_candidate_edges']} |\n"
            f"| All prerequisites ready → next start | {cell(result['all_prerequisites_ready_to_start_median_seconds'])} | diagnostic | — |\n"
            f"Missing: readiness {missing['readiness']}; identity {missing['identity']}; prerequisite evidence {missing['prerequisite_evidence']}; readiness conflicts {missing['readiness_conflicts']}.\n"
            f"Awaiting first start: {result['awaiting_first_run']['count']}; at/over 10 min: {result['awaiting_first_run']['at_or_over_target']}; oldest: {cell(result['awaiting_first_run']['oldest_seconds'])}.\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events", type=Path, help="events JSON, or queue directory with --queue")
    parser.add_argument("--queue", action="store_true", help="read current shallow queue receipts without modifying them")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    data = read_queue(args.events) if args.queue else json.loads(args.events.read_text())
    result = summarize(data, args.start, args.end)
    print(json.dumps(result, indent=2) if args.json else compact_table(result), end="\n")


if __name__ == "__main__":
    main()
