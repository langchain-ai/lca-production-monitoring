---
name: LangSmith Upload Traces
description: "INVOKE THIS SKILL when uploading historical traces to LangSmith. Covers the bulk upload script, required fields, gotchas for cost/token monitoring, and trace file preparation."
---

<oneliner>
Bulk upload historical trace JSON files to LangSmith with correct nested runs, cost data, and monitoring support.
</oneliner>

## Upload Script

The upload script is `upload_traces_nested_bulk.py`. It is self-contained (only needs `langsmith` and `python-dotenv`).

```bash
uv run python upload_traces_nested_bulk.py --input traces.json -p my-project
uv run python upload_traces_nested_bulk.py --input traces.json -p my-project --tag my-custom-tag
```

**What it does:**
- Shifts all timestamps so the latest run ends ~5 minutes ago (LangSmith requires ±24hr)
- Regenerates all run/trace IDs with fresh uuid7s
- Computes `dotted_order` for proper parent-child nesting
- Updates `LANGSMITH_PROJECT` metadata to match target project
- Auto-generates a timestamped tag if none provided
- Uses `batch_ingest_runs` with separate create/update passes (~90s for 3630 runs)

## Critical Upload Requirements

1. **Two-step create+update** — Send all creates first, flush, then all updates. Single `create_run()` with all fields won't populate monitoring cost/token charts.
2. **Use `batch_ingest_runs()`** — Chunk into batches of ~250. Much faster than individual calls.
3. **Update dicts MUST include `parent_run_id`** — Child run updates are silently rejected without it.
4. **Update dicts MUST include `extra`** — Model metadata (`ls_model_name`, `ls_provider`) is needed for server-side cost computation.
5. **`dotted_order` format** — `YYYYMMDDTHHMMSSffffffZ{run_id}` for root, `{parent_dotted_order}.{timestamp}{child_id}` for children.
6. **Can't delete individual traces** — Only delete entire project.
7. **Monitoring dashboard** may need a page refresh after bulk upload to show cost data.

**Create step fields:** id, trace_id, dotted_order, parent_run_id, name, run_type, inputs, extra, tags, start_time, session_name
**Update step fields:** id, trace_id, dotted_order, parent_run_id, extra, outputs, error, end_time

## Modifying Traces

To change the model for a time window (for cost demos):
- Identify traces by root `start_time` relative to the earliest trace
- Update these fields in LLM runs: `extra.metadata.ls_model_name`, `extra.invocation_params.model`, `extra.invocation_params.model_name`, `outputs.llm_output.model_name`, and `outputs.generations[0][0].message.kwargs.response_metadata.model_name`

To add custom metadata (e.g., customer):
- Assign per trace (all runs in a trace get the same value)
- Add to `extra.metadata` on every run in the trace
