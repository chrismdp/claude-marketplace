# Delegate run mechanics

## Task shape

Name the shape in the brief:

- **Plan/build**: new behaviour from a stable spec. Red test first for business logic, then the code.
- **Fix**: existing behaviour is wrong. Add a failing regression test, then fix. Existing tests stay unchanged unless the defect lacked coverage; watch for a weakened test.
- **Spike**: read-only. No production code, no cleanup. Output is findings, options and a proposed next ticket. If it finds the build path, it stops and writes the follow-on ticket rather than drifting into production code.

## Briefing

Point the worker at the canonical spec (ticket file, design doc) in its worktree; never write a parallel plan.md or restate the spec. Add only what the spec lacks: task shape, red-first testing, the relevant repo `CLAUDE.md` gotchas verbatim, whether parallel builds are running (then demand a surgical diff), the base ref for the affected gate, commit message format, "do not push", and any `ARCHITECTURE.md` or ADRs to check fit against.

Close every brief with the acceptance criteria as a checklist and the evidence each needs (the exact test, the captured payload, the rendered string). Workers otherwise judge an item secondary and leave it undone beside a green gate.

Brief template:

- **Deliverable and owner**: the complete result, its checks, and where the report goes.
- **Scope and decisions**: what the worker may decide, what is excluded, what needs the coordinator.
- **Inputs**: spec, base ref, environment, dependencies on other workers.
- **Acceptance evidence**: per criterion, plus what counts as complete.
- **Return conditions**: completion, a blocker with evidence, or a decision outside the brief.

Append `scripts/worker_rules.md` when the launcher does not. For an evaluation batch, also name the fixed cases, controls, budget and decision. Do not copy `pi_bench.py`'s coaching block into a brief; coaching is the opt-in benchmark path (`shadow-benchmarking.md`).

## Isolation and landing

- **Every code build gets its own worktree**, even a single sequential task: Agent tool `isolation: "worktree"`, or `scripts/codex_arm.sh`. A worker only writing tickets or docs can use the main tree, but then commit explicit paths only (never `git add -A`) while any worker is in flight.
- **Dependencies are private to each worker.** No shared writable symlinks to another checkout. State the setup in the brief. Reuse download caches or copy-on-write clones (`--reflink=auto` may silently do a full copy). A finished worker's dependency directory may pass to one successor if manifests, lockfile, runtime and install config match; never share between active workers.
- **Land by rebase or squash, never `git merge --no-ff`.** Rebase onto main then `git merge --ff-only`, or `git merge --squash` then one commit. Squash a branch's internal commits into one landing commit.
- **Rebase in the worktree; merge and push from the main checkout.** In the worktree, `--ff-only` says `Already up to date` and `git push origin main` pushes the unchanged main ref, so nothing lands while both look successful. If `--ff-only` says `Already up to date` for a branch you know is ahead, you are in the wrong directory.
- **After merging**, run the affected gate on the merged result. Fix a failing guard; never weaken it.
- **For parallel fleets**, land completed branches often to keep divergence short, and use `git rerere` for recurring conflicts. Inspect its resolution and rerun the affected gate after each merge.

### Cleanup

Clean up at landing (see SKILL.md). Keep evidence (commit or ref, report, regression output) outside the worktree first, and keep unmerged refs. If cleanup must wait, record why and who owns it. Workers leave cleanup to the coordinator. Remove reproducible dependency and build caches after acceptance.

A shadow never lands, so its worktree goes once it is graded into `runs.jsonl`.

**Make a Go worktree writable before removing it.** Go saves its module cache read-only, so `git worktree remove` and `rm -rf` fail with "Permission denied" on a worker's private cache (such as `build/go-mod/`). Run `chmod -R u+w <worktree>` first.

Sweep with the scripts, after reading `arm-safety.md` and identifying which worktrees this session owns:

```bash
scripts/sweep_worktrees.sh          # dry run; review it
scripts/sweep_worktrees.sh --yes
scripts/compress_logs.sh --yes      # gzip idle bench logs in ~/vault/data/model-bench/logs/
```

The sweep removes worktrees freely but deletes only merged branches, so unmerged work survives as a ref. Bench logs are evidence and stay, gzipped; plain logs have filled the disk.

## Running Codex

Run every Codex model (Sol, Astra) through `codex exec`, never through pi; the Codex harness gets more from them.

```bash
timeout 7200 codex exec --disable plugins --disable plugin_sharing \
  --yolo -C <worktree-dir> \
  -c model="gpt-6.1-sol" -c model_reasoning_effort="high" - < brief.txt
```

- The brief is a scratchpad file on stdin, not a repo plan.md. The plugin flags keep the worker on code editing.
- The 2-hour cap guards against runaways. Exit 124 means incomplete: recover production work as needed; for an experiment, record a resumed attempt separately.
- Run it as exactly one command with literal absolute paths and `run_in_background: true`. The allow rule `Bash(codex exec *)` strips a leading `timeout` but not a variable assignment, a `$VAR` redirect, a `cd ... &&` prefix or a trailing `; echo`; any of those prompts Chris. Take the exit code from the background-task notification.
- `codex exec resume` takes `[SESSION_ID] [PROMPT]` with `-c`, `--last`, `--all`, but not `-C` or `--yolo` (both error), and filters sessions by cwd. For a review-driven fix, prefer a fresh `codex exec` with a self-contained brief naming the prior commit, files and changes; keep `resume` for a genuine timeout with a dirty tree.

## Running an OpenRouter worker

```bash
python3 ~/.claude/skills/delegate/scripts/pi_bench.py --plain \
  <label> <workdir> <brief-file> [model]
```

`--plain` applies `worker_rules.md` and skips coaching, review passes and the ledger row; it prints a usage summary to stderr and the final message to stdout. Without `--plain` the same command is a benchmark run. Background it and cap it with `timeout`.

## Running on the 27agents fleet

In `~/code/27agents`: `export FLEET_GITHUB_TOKEN=$(gh auth token)` (the repo is private; the fleet holds the token only until the job's last fetch), then `node worker/fleet-cli/fleet.mjs run --business box --file brief.json --model <id> --github-token-env FLEET_GITHUB_TOKEN`. The brief needs `task` and `acceptance`; the job starts from the commit you name (default latest `main`) with a cost cap (default $5) and prints only its id. Read back with `fleet status|diff|log|transcript JOB --business box`. The diff applies with `git apply` to the job's start commit, and grading happens here. `FLEET_API_URL` and `FLEET_TOKEN` come from `~/.secret_env`; credentials are never arguments. The job never posts to Slack. Docs: `doc/FLEET-AS-EXECUTOR.md`, `doc/fleet-cli.md`.

## Running through `claude -p`

When pi's route to Anthropic answers 400 "Third-party apps now draw from your extra usage": `claude -p --model opus --allowedTools Read --max-turns <n> < brief.md > out.txt`. Only the `opus` and `sonnet` aliases work, not dated ids. It works from pi, not from inside a Claude Code session.

## Review before merge

- **Read outward from the diff.** Workers nail the spec and miss adjacent things it falsifies: a hardcoded default, a now-wrong docstring, a test edited to match their own regression. For Codex, diff every touched test file against its pre-change version.
- **Prove the new thing is reached.** For anything that must load or fire (a reporter, hook, registration, scheduled job, config entry), the evidence is a probe showing it ran on the command the ticket names. Tests written beside the code share the author's wiring mistake.
- **Scale independent review to risk.** Security or privacy boundaries, consequential architecture and conflicting evidence get a fresh reviewer with a completed artefact and a specific question. Routine changes do not need separate review agents, but the coordinator still reviews, runs the gate and gets evidence the behaviour works. Where a repo has mutation testing and the area is high-risk, run it before accepting agent-written tests.
- **Review round N carries rounds 1 to N−1**: findings, verdicts and fixes, so the reviewer verifies rather than re-derives.
- **Fix Important findings only**; collect Nits into one follow-up issue. Set this before round one.
- **Stop after two fix rounds.** If a third review still raises an Important finding, merge nothing and bring it to Chris with a simpler option.
- **The same defect class found twice from different angles means redesign**, not a third patch: derive the truth from the artefact that already holds it (tool outputs, receipts, logs) and record the change in the delegation log.

## Continuation and parallelism

After a worker returns, send one consolidated correction brief if needed. Continue the same worker for a small correction in the same area; a new substantial deliverable gets a fresh worker with a focused brief (commit, findings, open questions), not the whole conversation. An idle worker with a finished report needs no nudge. Run independent tasks in parallel across any mix of workers; serialise only when two tasks edit the same seam and merging would be a rewrite.

## Delegation log

If the project keeps one (its `CLAUDE.md` names it), append one entry per delegation: task, worker with effort (`opus/high`, `sonnet`, Codex with model), outcome, rework. Record failures as faithfully as wins. After a change to how coordination works, also record tokens by role and model and cost per accepted outcome for the next real job, with missing measurements as unknown.

`/ralph` loads this skill before dispatching a ticket build; a project's own `CLAUDE.md` carries its delegation policy.
