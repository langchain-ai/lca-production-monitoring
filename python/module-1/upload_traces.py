"""Load traces.json, shift timestamps to now, regenerate IDs, and upload."""

import json
from collections import defaultdict
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from langsmith import Client, uuid7


def parse_dt(s: str | None) -> datetime | None:
    if s is None:
        return None
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="ACME-cost", help="Target project name")
    parser.add_argument("--input", default="traces.json", help="Input file path")
    args = parser.parse_args()

    with open(args.input) as f:
        runs = json.load(f)

    print(f"Loaded {len(runs)} runs from {args.input}")

    # Calculate time shift so traces appear recent
    latest = max(parse_dt(r["start_time"]) for r in runs if r["start_time"])
    time_delta = datetime.now(timezone.utc).replace(tzinfo=None) - latest
    print(f"Shifting timestamps by: {time_delta}")

    # Build ID map (uuid7 for time-ordering)
    # For root runs, trace_id must equal id, so map both to the same uuid7.
    id_map = {}
    for run in runs:
        if run.get("parent_run_id") is None:
            root_new_id = str(uuid7())
            id_map[run["id"]] = root_new_id
            id_map[run["trace_id"]] = root_new_id
    for run in runs:
        for field in ("id", "parent_run_id"):
            old_id = run.get(field)
            if old_id and old_id not in id_map:
                id_map[old_id] = str(uuid7())

    # Group runs by trace and transform
    traces = defaultdict(list)
    for run in runs:
        trace_id = id_map[run["trace_id"]]
        traces[trace_id].append({
            "id": id_map[run["id"]],
            "trace_id": trace_id,
            "dotted_order": None,  # populated below
            "parent_run_id": id_map.get(run["parent_run_id"]),
            "name": run["name"],
            "run_type": run["run_type"],
            "inputs": run["inputs"],
            "outputs": run.get("outputs"),
            "error": run.get("error"),
            "extra": run.get("extra") or {},
            "tags": run.get("tags"),
            "start_time": parse_dt(run["start_time"]) + time_delta,
            "end_time": parse_dt(run["end_time"]) + time_delta if run.get("end_time") else None,
        })

    client = Client()
    print(f"Uploading {len(traces)} traces to project '{args.project}'...")

    for i, (trace_id, trace_runs) in enumerate(traces.items()):
        # Sort: root first, then children by start_time
        trace_runs.sort(key=lambda r: (r["parent_run_id"] is not None, r["start_time"]))

        # Build dotted_order for proper nesting
        dotted_orders = {}
        child_counters = defaultdict(int)
        for run in trace_runs:
            ts = run["start_time"].strftime("%Y%m%dT%H%M%S%f") + "Z"
            if run["parent_run_id"] is None:
                run["dotted_order"] = f"{ts}{run['id']}"
            else:
                parent_order = dotted_orders.get(run["parent_run_id"], "")
                run["dotted_order"] = f"{parent_order}.{ts}{run['id']}"
            dotted_orders[run["id"]] = run["dotted_order"]

        # Upload each run individually
        for run in trace_runs:
            client.create_run(
                id=run["id"],
                trace_id=run["trace_id"],
                dotted_order=run["dotted_order"],
                parent_run_id=run["parent_run_id"],
                name=run["name"],
                run_type=run["run_type"],
                inputs=run["inputs"],
                outputs=run.get("outputs"),
                error=run.get("error"),
                extra=run.get("extra"),
                tags=run.get("tags"),
                start_time=run["start_time"],
                end_time=run["end_time"],
                project_name=args.project,
            )

        if (i + 1) % 10 == 0:
            print(f"  Uploaded {i + 1}/{len(traces)} traces")

    # Wait for all background operations to complete
    print("Flushing...")
    client.flush()
    print("Done!")


if __name__ == "__main__":
    main()
