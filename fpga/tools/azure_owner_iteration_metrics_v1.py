#!/usr/bin/env python3
"""Bounded, local metadata reader. No network, worker commands, imports or jobs.

Print a frozen normalized snapshot, then calculate from that snapshot. This is
reporting only: it is not an admission gate, a dispatcher or a budget meter.
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
import pathlib
import statistics

UTC = dt.timezone.utc
MAX_BYTES = 4 * 1024 * 1024
MAX_TICKETS = 1000


def stamp(value):
    if value is None or value == "":
        return None
    if isinstance(value, (float, int)):
        return float(value)
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        try:
            return dt.datetime.strptime(value, "%a %Y-%m-%d %H:%M:%S UTC").replace(tzinfo=UTC).timestamp()
        except ValueError:
            return None


def iso(value):
    return dt.datetime.fromtimestamp(value, UTC).isoformat().replace("+00:00", "Z") if value is not None else None


def union_seconds(intervals):
    end = None
    total = 0.0
    for left, right in sorted(intervals):
        if right <= left:
            continue
        total += max(0.0, right - max(left, end if end is not None else left))
        end = max(right, end if end is not None else right)
    return total


def clip(left, right, start, end):
    return max(left, start), min(right, end)


def cpu_ids(value):
    result = []
    for token in (value or "").replace(",", " ").split():
        if "-" in token:
            low, high = map(int, token.split("-"))
            result.extend(range(low, high + 1))
        else:
            result.append(int(token))
    return result


class Reader:
    def __init__(self, root):
        self.root = pathlib.Path(root).resolve()
        self.pins = {}

    def read(self, path, optional=False, raw=False):
        path = pathlib.Path(path)
        if not path.is_absolute():
            path = self.root / path
        path = path.resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Metadata path outside fpga root: " + str(path))
        if optional and not path.is_file():
            return None
        if path.is_symlink() or path.stat().st_size > MAX_BYTES:
            raise ValueError("Unbounded metadata file: " + str(path))
        data = path.read_bytes()
        self.pins[str(path.relative_to(self.root))] = hashlib.sha256(data).hexdigest()
        return data.decode() if raw else json.loads(data)


def classify(ticket, report, manifest):
    result = ticket.get("result", {})
    status = result.get("status")
    gate = ticket.get("dependency_gate", {}).get("status")
    if ticket.get("kind") == "reference":
        return "reference_generation" if status == "needs_reference_import_validation" else "reference_unresolved"
    if status == "imported_existing_independent_PASS":
        return "historical_import_no_new_execution"
    if status == "cancelled_unstarted_dependency_failure":
        return "cancelled_unstarted_dependency_failure"
    if status == "terminal_infrastructure_failure":
        return "infrastructure_failure"
    if status == "terminal_failure":
        return "native_contract_or_runner_failure"
    if gate == "observation_only_not_dependency":
        return "lint_observation_only"
    if gate == "PASS_expected_contracts" and report and report.get("status") == "completed_native_commands_unreviewed":
        codes = [s.get("expected_returncode", 0) for s in (manifest or {}).get("steps", [])]
        if not codes:
            return "expected_native_gate_contract_mix_unknown"
        if all(c == 0 for c in codes):
            return "expected_native_gate_positive_only"
        if all(c != 0 for c in codes):
            return "expected_native_gate_intentional_negative_only"
        return "expected_native_gate_mixed_positive_negative"
    return "unresolved_or_unclassified"


def normalize_ticket(reader, ticket, state):
    dispatch = ticket.get("dispatch", {})
    result = ticket.get("result", {})
    props = result.get("properties") or dispatch.get("properties") or {}
    evidence = result.get("evidence")
    report = None
    manifest = None
    if result.get("native_report_path"):
        report = reader.read(result["native_report_path"], optional=True)
        manifest = reader.read(pathlib.Path(result["native_report_path"]).parent / "approved-manifest.json", optional=True)
    if evidence:
        report = report or reader.read(pathlib.Path(evidence) / "output/native/report.json", optional=True)
        manifest = manifest or reader.read(pathlib.Path(evidence) / "manifest.json", optional=True)
    if ticket.get("kind") == "reference":
        report = result.get("command_report") or result.get("queue_report") or report
    gate = ticket.get("dependency_gate", {})
    if gate.get("path"):
        actual = reader.read(gate["path"], optional=True)
        if actual is None:
            raise ValueError("Missing gate receipt: " + ticket["id"])
        gate_path = str(pathlib.Path(gate["path"]).resolve().relative_to(reader.root))
        if reader.pins[gate_path] != gate.get("sha256"):
            raise ValueError("Gate receipt hash mismatch: " + ticket["id"])
    limits = (report or {}).get("limits", {})
    start = stamp(props.get("ExecMainStartTimestamp"))
    exit_at = stamp(result.get("recovered_allocation_exit_utc")) or stamp(props.get("ExecMainExitTimestamp"))
    observed = stamp(dispatch.get("observed_at"))
    active = props.get("SubState") == "running" and int(props.get("MainPID", 0) or 0) > 0
    topology = limits.get("full_topology") or {}
    physical = limits.get("physical_cores") or []
    package = ticket.get("package", {})
    if not physical and props.get("AllowedCPUs"):
        physical = [["logical-unresolved", n] for n in cpu_ids(props["AllowedCPUs"])]
    counter = props.get("CPUUsageNSec")
    recovered = bool(result.get("recovered_allocation_exit_utc"))
    return {
        "id": ticket["id"], "record_state": state, "kind": ticket.get("kind"),
        "owner": ticket.get("owner"), "host": dispatch.get("host"), "unit": dispatch.get("unit"),
        "invocation": dispatch.get("invocation"), "profile": package.get("profile"),
        "category": classify(ticket, report, manifest), "result_status": result.get("status"),
        "gate_status": ticket.get("dependency_gate", {}).get("status"),
        "start_epoch": start, "exit_epoch": exit_at, "last_observed_epoch": observed,
        "observed_running": active, "collected_epoch": stamp(result.get("completed")),
        "allocation_end_basis": "recovered_original_journal" if recovered else "terminal_unit_timestamp" if exit_at else "last_running_observation" if active else "unknown",
        "physical_cores": physical, "allowed_cpus": cpu_ids(props.get("AllowedCPUs")),
        "topology": topology, "after": ticket.get("after") or [],
        "candidate_source_sha256": ticket.get("dependency_gate", {}).get("candidate_source_sha256"),
        "CPUUsageNSec": int(counter) if counter not in (None, "") else None,
        "cpu_counter_basis": "partial_pre_stop" if recovered and counter is not None else "terminal" if exit_at and counter is not None else "partial" if counter is not None else "not_captured",
        "expected_step_returncodes": [s.get("expected_returncode", 0) for s in (manifest or {}).get("steps", [])],
        "native_report_status": (report or {}).get("status"),
        "classification": result.get("classification"),
    }


def capture(root, facts_path):
    reader = Reader(root)
    facts = reader.read(facts_path)
    records = {}
    # Done last, so a ticket moving while read is counted once. Pins retain both reads.
    for state in ("pending", "running", "done"):
        files = sorted((reader.root / "queue" / state).glob("*.json"))
        if len(files) > MAX_TICKETS:
            raise ValueError("Ticket directory exceeds bounded reader limit")
        for path in files:
            ticket = reader.read(path, optional=True)
            if ticket:
                records[ticket["id"]] = normalize_ticket(reader, ticket, state)
    for host, info in facts["hosts"].items():
        observed = reader.read(info["topology_path"])
        info["topology"] = observed.get("topology") or {
            str(c["cpu"]): [c["package_id"], c["core_id"]] for c in observed.get("cpus", [])}
        if len(set(map(tuple, info["topology"].values()))) != info["physical_cores"]:
            raise ValueError("Pinned physical topology and stated capacity disagree: " + host)
    for record in records.values():
        info = facts["hosts"].get(record["host"], {})
        if record["physical_cores"] and record["physical_cores"][0][0] == "logical-unresolved":
            topology = info.get("topology", {})
            if all(str(n) in topology for n in record["allowed_cpus"]):
                record["physical_cores"] = sorted({tuple(topology[str(n)]) for n in record["allowed_cpus"]})
                record["affinity_basis"] = "actual_unit_affinity_mapped_by_pinned_host_topology"
            else:
                record["physical_cores"] = []
                record["affinity_basis"] = "unknown_physical_mapping"
        else:
            record["affinity_basis"] = "native_report_observed_physical_cores"
    extras = []
    for source in facts.get("fit_terminal_paths", []):
        receipt = reader.read(source)
        proof = receipt.get("native_journal_proof", {})
        resources = receipt.get("native_context_resources", {})
        if not proof.get("terminal_proven"):
            continue
        counters = [int(x["CPU_USAGE_NSEC"]) for x in proof.get("resource_journal", [])
                    if x.get("INVOCATION_ID") == receipt["invocation_id"] and x.get("UNIT") == receipt["unit"]]
        extras.append({"id": receipt["unit"], "host": receipt["host"], "unit": receipt["unit"],
                       "invocation": receipt["invocation_id"], "kind": "fit", "category": "fit_completed" if receipt.get("native_job_succeeded") else "fit_failed",
                       "start_epoch": int(proof["manager_start_realtime_us"]) / 1e6,
                       "exit_epoch": int(proof["manager_end_realtime_us"]) / 1e6,
                       "physical_cores": resources["physical_cores"],
                       "CPUUsageNSec": counters[-1] if counters else None, "cpu_counter_basis": "terminal",
                       "allocation_end_basis": "attributed_system_manager_journal", "source": source})
    # Owner-supplied normalization of existing live observations. Never extrapolate.
    for record in facts.get("additional_records", []):
        for ref in record.get("evidence", []):
            reader.read(ref, raw=True)
        extras.append(record)
    for ref in facts.get("evidence_paths", []):
        reader.read(ref, raw=True)
    return {"schema": "owner-metadata-snapshot-v1", "captured_at_utc": iso(dt.datetime.now(UTC).timestamp()),
            "atomic_across_files": False, "capture_race_policy": "Bounded sequential reads; id deduplicated, done wins. Each exact file read hashed. No remote freshness claimed.",
            "facts": facts, "records": sorted(list(records.values()) + extras, key=lambda r: r["id"]),
            "evidence_sha256": reader.pins}


def summarize(snapshot, start, end):
    records = snapshot["records"]
    hosts = snapshot["facts"]["hosts"]
    valid_from = stamp(snapshot["facts"].get("valid_from_utc"))
    if valid_from is None or start < valid_from:
        raise ValueError("Requested window predates frozen topology/lifecycle facts; supply new facts, not current capacity")
    if end <= start or end > stamp(snapshot["captured_at_utc"]):
        raise ValueError("Window must end by the metadata capture, never a future interval")
    by_id = {r["id"]: r for r in records}
    windows = []
    left = start
    while left < end:
        right = min(end, (int(left) // 3600 + 1) * 3600)
        counts = collections.Counter()
        starts = collections.Counter()
        host_results = {}
        edges = []
        readiness = []
        for r in records:
            a, b = r.get("start_epoch"), r.get("exit_epoch")
            if a is not None and left <= a < right:
                starts[r["kind"] or "unknown"] += 1
            if b is not None and left <= b < right:
                counts[r["category"]] += 1
            elif a is None and left <= (r.get("collected_epoch") or -1) < right:
                counts[r["category"]] += 1
            if a is not None and left <= a < right:
                required = []
                missing = []
                for dependency in r.get("after", []):
                    p = by_id.get(dependency.get("id") if isinstance(dependency, dict) else dependency)
                    if p and p.get("exit_epoch") is not None:
                        required.append(p)
                        edges.append({"predecessor": p["id"], "successor": r["id"],
                                      "predecessor_exit_utc": iso(p["exit_epoch"]), "successor_start_utc": iso(a),
                                      "gap_seconds": round(a - p["exit_epoch"], 6),
                                      "same_owner": p.get("owner") == r.get("owner"),
                                      "same_candidate_source": bool(p.get("candidate_source_sha256") and p["candidate_source_sha256"] == r.get("candidate_source_sha256"))})
                    else:
                        missing.append(dependency)
                if required and not missing:
                    last = max(required, key=lambda p: p["exit_epoch"])
                    readiness.append({"successor": r["id"], "last_required_predecessor": last["id"],
                                      "predecessor_exit_utc": iso(last["exit_epoch"]), "successor_start_utc": iso(a),
                                      "gap_seconds": round(a-last["exit_epoch"], 6)})
        for host, info in hosts.items():
            cores = collections.defaultdict(list)
            categories = collections.Counter()
            unresolved = []
            cpu = []
            overlaps = []
            host_records = [r for r in records if r.get("host") == host]
            terminals = collections.Counter(r["category"] for r in host_records if r.get("exit_epoch") is not None and left <= r["exit_epoch"] < right)
            host_starts = collections.Counter(r["kind"] for r in host_records if r.get("start_epoch") is not None and left <= r["start_epoch"] < right)
            for r in host_records:
                a = r.get("start_epoch")
                b = r.get("exit_epoch")
                if a is None:
                    continue
                if b is None and r.get("observed_running"):
                    b = r.get("last_observed_epoch")
                if b is not None and b > a:
                    x, y = clip(a, b, left, right)
                    if y > x:
                        for core in set(map(tuple, r.get("physical_cores", []))):
                            cores[core].append((x, y, r["id"]))
                        categories[r["category"]] += (y - x) * len(set(map(tuple, r.get("physical_cores", []))))
                if r.get("exit_epoch") is None and a < right:
                    last = r.get("last_observed_epoch")
                    if last is None or last < right:
                        unresolved.append({"id": r["id"], "last_observed_utc": iso(last),
                                           "unknown_after_utc": iso(max(left, last or a)), "not_extrapolated": True})
                if r.get("CPUUsageNSec") is not None:
                    # Only whole attributed counters entirely within window; no hourly prorating.
                    cpu_end = r.get("exit_epoch") if r.get("cpu_counter_basis") == "terminal" else r.get("last_observed_epoch")
                    if cpu_end is not None and left <= a <= cpu_end < right:
                        cpu.append({"id": r["id"], "cpu_seconds": r["CPUUsageNSec"] / 1e9,
                                    "basis": r["cpu_counter_basis"], "counter_at_utc": iso(cpu_end)})
            assigned = 0.0
            for core, intervals in cores.items():
                assigned += union_seconds([(a, b) for a, b, _ in intervals])
                for i, (a, b, job) in enumerate(sorted(intervals)):
                    for x, y, other in sorted(intervals)[:i]:
                        if min(b, y) > max(a, x):
                            overlaps.append({"physical_core": core, "ids": [other, job],
                                             "seconds": round(min(b, y) - max(a, x), 6)})
            down = []
            unknown = []
            known = [(max(left, r["start_epoch"]), min(right, r.get("exit_epoch") or r.get("last_observed_epoch") or r["start_epoch"]))
                     for r in host_records if r.get("start_epoch") is not None and
                     (r.get("exit_epoch") is not None or r.get("observed_running"))]
            for period in info.get("known_available_intervals", []):
                a, b = clip(stamp(period["start"]), stamp(period["end"]), left, right)
                if b > a:
                    known.append((a, b))
            for period in info.get("unavailable_intervals", []):
                a, b = clip(stamp(period["start"]), stamp(period["end"]), left, right)
                if b > a:
                    down.append((a, b))
            for period in info.get("unknown_availability_intervals", []):
                a, b = clip(stamp(period["start"]), stamp(period["end"]), left, right)
                if b > a:
                    unknown.append((a, b))
            down_seconds = union_seconds(down)
            unknown_seconds = union_seconds(unknown)
            # Positive job lifetimes / enumerated guest-boot evidence bound availability.
            # Do not call every gap "idle" or extrapolate a stale live observation.
            covered_unknown = union_seconds([(max(a, x), min(b, y)) for a, b in unknown for x, y in known])
            unknown_seconds = max(0.0, unknown_seconds - covered_unknown)
            # Availability bounds are explicit lifecycle model, never current topology * full hour.
            capacity_max = info["physical_cores"] * (right - left - down_seconds)
            capacity_min = max(0, capacity_max - info["physical_cores"] * unknown_seconds)
            host_results[host] = {"physical_cores": info["physical_cores"],
                "actual_job_starts": dict(host_starts), "terminal_counts_by_actual_exit": dict(terminals),
                "capacity_basis": info["capacity_basis"], "known_unavailable_seconds": round(down_seconds, 6),
                "unknown_availability_seconds": round(unknown_seconds, 6),
                "available_capacity_core_seconds_bounds": [round(capacity_min, 6), round(capacity_max, 6)],
                "observed_assigned_affinity_core_seconds_union": round(assigned, 6),
                "observed_occupancy_pct_using_capacity_upper": round(100 * assigned / capacity_max, 3) if capacity_max else None,
                "per_category_core_seconds_before_union": {k: round(v, 6) for k, v in categories.items()},
                "unresolved_intervals": unresolved, "unit_affinity_overlap_union_not_double_counted": overlaps,
                "whole_counter_cpu_seconds_known_in_window": round(sum(x["cpu_seconds"] for x in cpu if x["basis"] == "terminal"), 6),
                "partial_counter_cpu_seconds_known_in_window": round(sum(x["cpu_seconds"] for x in cpu if x["basis"] != "terminal"), 6),
                "cpu_counter_coverage": cpu}
        gaps = [x["gap_seconds"] for x in edges if x["gap_seconds"] >= 0]
        ready_gaps = [x["gap_seconds"] for x in readiness if x["gap_seconds"] >= 0]
        same = [x["gap_seconds"] for x in edges if x["gap_seconds"] >= 0 and x["same_candidate_source"]]
        windows.append({"start_utc": iso(left), "end_utc": iso(right), "seconds": right-left,
                        "terminal_counts_by_actual_exit": dict(counts), "actual_job_starts": dict(starts),
                        "hosts": host_results, "explicit_dependency_gaps": edges,
                        "last_required_predecessor_gaps": readiness,
                        "median_last_required_predecessor_gap_seconds": statistics.median(ready_gaps) if ready_gaps else None,
                        "median_explicit_dependency_gap_seconds": statistics.median(gaps) if gaps else None,
                        "median_exact_same_candidate_source_gap_seconds": statistics.median(same) if same else None})
        left = right
    return {"schema": "owner-iteration-resource-metrics-v1", "scope": "Local queue metadata plus enumerated existing fit/qualification receipts; no remote work or queue changes",
            "snapshot_captured_at_utc": snapshot["captured_at_utc"], "start_utc": iso(start), "end_utc": iso(end),
            "definitions": {
                "native_gate": "Collected native report completed + PASS_expected_contracts. Positive-only, expected-negative-only and mixed are separate. Not independent promotion.",
                "allocated_core_occupancy": "Union of observed job unit assigned physical affinity over actual start-to-exit, or start-to-last-positive-running-observation only. Includes wrappers/compile-lock waits; not CPU utilization or proof every core was busy.",
                "capacity": "Pinned topology with explicit unavailable/unknown lifecycle intervals; power observations between samples use stated continuity model, not per-second provider measurements.",
                "CPUUsageNSec": "Attributed per-unit whole/partial counters only; never interpolated or prorated across hour boundaries. Missing counters/other host workloads omitted.",
                "gap": "Explicit ticket after edges only; candidate equality only exact candidate_source_sha256. Collected-at is not native exit; no heuristic ticket-name family or owner-as-candidate.",
                "coverage": "Not all manual/pre-queue jobs, native fits, imports or outcomes are in global queue. Enumerated extra receipts included; unenumerated work is unknown, not idle.",
                "time_precision": "systemctl real-time timestamps usually seconds; manager-journal fit timestamps microseconds. Native positive gate count attributed by allocation exit, not delayed receipt collection."},
            "warnings": snapshot["facts"].get("limitations", []), "windows": windows,
            "record_count": len(records), "evidence_sha256": snapshot["evidence_sha256"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("capture")
    p.add_argument("--root", default="fpga")
    p.add_argument("--facts", required=True)
    p = sub.add_parser("summarize")
    p.add_argument("--snapshot", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    args = parser.parse_args()
    if args.command == "capture":
        result = capture(args.root, args.facts)
    else:
        path = pathlib.Path(args.snapshot)
        if path.stat().st_size > 16 * MAX_BYTES:
            raise ValueError("Snapshot exceeds metadata bound")
        snapshot = json.loads(path.read_text())
        result = summarize(snapshot, stamp(args.start), stamp(args.end))
        result["snapshot_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
