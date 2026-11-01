# Setup progress stream (NDJSON)

`aria_setup.py --progress` emits a machine-readable progress stream while the
setup pipeline runs: one JSON object per line (NDJSON) on **stderr**, flushed
after every frame so a consumer can tail it live.

    python aria_setup.py --progress 2> progress.ndjson
    python aria_setup.py --progress --json > report.json 2> progress.ndjson

## The `aria_progress` discriminator

Every line carries `"aria_progress": true`. Progress frames share the stream
with ordinary setup output, so a consumer filters on the marker instead of
parsing terminal text:

    import json

    for line in stderr_text.splitlines():
        try:
            frame = json.loads(line)
        except ValueError:
            continue  # ordinary setup output, not a progress frame
        if frame.get("aria_progress"):
            handle(frame)

## Fields

| Field | Type | Meaning |
| --- | --- | --- |
| `aria_progress` | bool | Always `true`; the discriminator. |
| `event` | string | `run_start`, `step_start`, `step_end` or `run_end`. |
| `ts` | string | RFC3339 UTC timestamp with a `Z` suffix. |
| `run_id` | string | 12-hex id shared by every frame of one run. |
| `name` | string | Step name. Absent on run-level frames. |
| `tier` | string | `core`, `runtime` or `optional`. |
| `index` | int | 0-based position of a step. **Only** on `step_start` / `step_end`. |
| `total` | int | Steps planned for the run. |
| `steps_done` | int | Steps that executed. **Only** on `run_end`. |
| `status` | string | See the vocabulary below. |
| `message` | string | Human-readable outcome, on `step_end`. |
| `elapsed_s` | float | Seconds. |

Optional fields that do not apply to a frame are omitted, never sent as
`null`.

### `index` and `steps_done` are not interchangeable

`index` is the **0-based position of a step** within the run and appears
**only** on `step_start` and `step_end`. `steps_done` is a **count** and
appears **only** on `run_end`. The two keys have different types of meaning, so
a consumer must never conflate them: on a `step_end` frame `steps_done` is
absent, and on a `run_end` frame `index` is absent. To advance a progress bar
from a `step_end`, compute `steps_done = index + 1`; take the authoritative
final count from `run_end.steps_done`.

### Status vocabulary

Step-level statuses (`step_start`, `step_end`) are `ok`, `warn`, `fail`, `skip`,
`running`, `pending`, `rolled_back`. `run_end.status` is run-level and is only
`"ok"` or `"failed"`; a step-level `"fail"` maps to a run-level `"failed"`.

## Frames

### run_start

    {"aria_progress":true,"event":"run_start","ts":"2026-09-30T21:04:11.482913Z","total":10,"run_id":"3f9c1a0b7e21"}

### step_start

    {"aria_progress":true,"event":"step_start","ts":"2026-09-30T21:04:11.483101Z","index":0,"total":10,"name":"detect_environment","tier":"core","status":"running","run_id":"3f9c1a0b7e21"}

### step_end

    {"aria_progress":true,"event":"step_end","ts":"2026-09-30T21:04:14.902337Z","index":0,"total":10,"name":"detect_environment","tier":"core","status":"warn","message":"2 tool(s) not installed","elapsed_s":3.419236,"run_id":"3f9c1a0b7e21"}

### run_end

    {"aria_progress":true,"event":"run_end","ts":"2026-09-30T21:05:02.117744Z","steps_done":12,"total":10,"status":"ok","elapsed_s":50.634831,"run_id":"3f9c1a0b7e21"}

## Why stderr, not stdout

`--json` already prints the final report on stdout and that report is
machine-read today. Progress frames on stdout would interleave with it and any
consumer would have to strip frames out of the middle of a JSON document.
stderr is the diagnostics side channel, so `--json` on stdout stays a clean
parseable report and the painted report is unaffected.

## Guarantees

- One JSON object per line. `json.dumps` escapes embedded newlines, so even a
  hostile step name cannot break NDJSON framing.
- Every frame is flushed immediately: the consumer sees a step the moment it
  starts, not when the buffer happens to fill.
- The emitter is observability, not a dependency. A closed pipe, or a stream
  that raises on write, is swallowed silently; a broken progress consumer can
  never abort a setup run.
- Without `--progress` nothing is emitted and behaviour is unchanged.

## Files

| Path | Change |
| --- | --- |
| `aria_autoconfig/progress.py` | New. `ProgressEmitter`, `ProgressEvent`, `status_str`, `tier_str`, `default_progress_stream`. |
| `aria_autoconfig/orchestrator.py` | New optional `progress=` argument; emits the four event types around `run_full_setup`. |
| `aria_autoconfig/__init__.py` | Re-exports the progress API. |
| `aria_setup.py` | New `--progress` flag. |
| `tests/test_autoconfig_progress.py` | New. Framing, status mapping, resilience and wiring tests. |
| `docs/SETUP_PROGRESS.md` | New. This document. |
