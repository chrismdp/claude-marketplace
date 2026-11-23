# Bounded model experiments

Experiments are on demand, for a chosen comparison, never per delegation. They never hold up production merges, documentation or issue updates; if one competes with production tests for machine capacity, pause it. The coordinator owns the question, task boundaries, review and decision. A worker earns work by handling a task class usefully under supervision, not by matching the coordinator.

## Forms

Record which form a run is:

- **Supervised task**: a bounded piece of real work, reviewed and verified by the coordinator, which can ship normally. Measures worker and coordinator together, not independent capability.
- **Focused review or investigation**: a specific question with a concrete deliverable. Record whether the finding was adopted.
- **Independent comparison**: candidates get the same frozen task and starting source in isolation. A shadow is an experimental implementation that never ships.

## Before dispatch

Write a short experiment brief beside the ledger artefacts: question and task list; coordinator, candidate model, harness and starting revision; deliverable and acceptance criteria; time and cost budget including review passes and coordinator effort; help permitted and how interventions are recorded; and the end decision (use the model for a named task class, revise, or stop). Five to ten tasks can screen a candidate; that is not a reliability claim. Set a concrete deadline; launchers do not enforce a campaign budget. At the limit, stop and record unfinished work as incomplete; a resumed run is a new attempt with its own budget.

## Isolate independent comparisons

Freeze task text, attachments and starting source; give every candidate the same acceptance criteria; record coaching and help separately. Use a separate repository containing only the starting source and frozen inputs: a worktree of the production repo shares its object database and can expose the completed answer. Block access to the production checkout, control branches, later issue comments and finished answers; a separate directory alone does not. The launchers do not enforce this. If you cannot isolate, run a supervised task or record the comparison as non-independent. Record any answer exposure; matching blobs or commit messages are a reason to inspect logs, not proof of copying.

## Launchers and measurement

From the isolated repository, with `scripts/` resolved from the delegate skill directory:

```bash
scripts/shadow_arm.sh <label> <brief-file> <base-ref> [model]
```

Pass the base and the model explicitly. `shadow_arm.sh` calls `pi_bench.py`, which writes raw logs to `~/vault/data/model-bench/logs/` and rows to `~/vault/data/model-bench/runs.jsonl`. Logs may be gzipped (`gzip -dc <path>.gz`). Costs come from `PRICES` in the runner and are token-cost estimates, not invoices; pi's own price fallback is wrong for models missing from its catalogue. Codex models run through Codex (`codex_arm.sh` records its own control measurements). For an Agent-tool control:

```bash
python3 scripts/pi_bench.py --record-control \
  --label <comparison-label> --model <model> \
  --from-agent-transcript <transcript-path>
```

Use one comparison label per pair and distinct attempt labels for retries. Keep unknown cost or duration as null; never estimate one model's usage from another's.

`--compare` is unreliable: it turns missing costs into zero, can divide by zero, and replaces measured rows with later grade-only rows. Analyse from the raw ledger and logs.

Record coordinator review time, corrections, adopted findings and actual production delay alongside model measurements. Costs of two implementations add unless one replaces the other.

## Coaching and review passes

`pi_bench.py` owns the coaching text, `COACHING_VERSION`, the review prompt and `MAX_REVIEW_PASSES`; do not copy them into a brief. A fresh-context review can start after the first stop, so a commit does not mean the run is finished: wait for process exit before grading. Read `passes`, `review_passes`, `review_verdict` and `review_stop_reason` with the diff; usage and duration cover all passes, `stop_reason` only the first. Record model and harness version together.

## Monitor and clean up

Follow `arm-safety.md`. Also: verify the sentinel belongs to this run, not an interrupted earlier attempt; stop only this experiment's processes and record each intervention, exit status and stop reason; keep the diff, logs and grade before removing the worktree; gzip finished logs with `compress_logs.sh`.

## Grade and decide

Read the diff against the task and run the affected checks. Locate the candidate's implementation rather than searching for the control's identifiers. Check changed tests for weakened assertions. Record measurements when the run ends and the grade after review, under the same run identity, using the ledger vocabulary:

- `shipped-clean`: landable without fixes.
- `shipped-with-fixes`: needed corrections before acceptance.
- `rejected`: failed acceptance, including weakened tests.
- `inconclusive`: interruption, missing evidence or answer exposure.

For shadows, `shipped` means landable, not deployed. Read-only tasks get "completed and useful", not an implementation grade. For independent pairs, record `shadow_vs_control` as `SHADOW-BETTER`, `near-equal` or `control-better` with the reason. Keep first-attempt results apart from post-correction ones. Note what the worker found, missed and needed, and whether the cause of a miss was the brief, the environment, the harness or the model. Check surprising ratios against raw usage.

At the end, make the declared decision, report it, and name the task class that gained or lost confidence. A useful worker earns more bounded tasks, not coordinator status or automatic approval to ship.
