"""Export CSA traces for a given run_id to JSONL files."""

import json
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from langsmith import Client

client = Client()

run_id = sys.argv[1] if len(sys.argv) > 1 else "d2e63d53-57e9-404f-9c73-18fc5080f9d6"
out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("trace_exports/rev3_csa_full")

runs = list(
    client.list_runs(
        project_name="general_project",
        filter=f'and(eq(metadata_key, "run_id"), eq(metadata_value, "{run_id}"))',
        is_root=True,
    )
)

csa_runs = [r for r in runs if r.tags and "csa" in r.tags]
print(f"Total root runs: {len(runs)}")
print(f"CSA runs: {len(csa_runs)}")

out_dir.mkdir(parents=True, exist_ok=True)

for i, run in enumerate(csa_runs):
    trace_runs = list(client.list_runs(trace_id=run.id, project_name="general_project"))

    # Fetch feedback for the root run and index by run_id
    feedback_list = list(client.list_feedback(run_ids=[str(run.id)]))
    feedback_by_run = {}
    for fb in feedback_list:
        feedback_by_run[str(fb.run_id)] = {"key": fb.key, "score": fb.score}

    with open(out_dir / f"{run.id}.jsonl", "w") as f:
        for r in trace_runs:
            r_dict = json.loads(r.json())
            if str(r.id) in feedback_by_run:
                r_dict["_feedback"] = feedback_by_run[str(r.id)]
            f.write(json.dumps(r_dict) + "\n")
    print(f"  [{i+1}/{len(csa_runs)}] Exported trace {run.id} ({len(trace_runs)} runs)")

print(f"\nDone. {len(csa_runs)} CSA traces exported to {out_dir}")
