---
name: delegate
description: Delegate bounded coding tasks to workers, with Astra or Opus 5.5 coordinating scope, review, and integration. Load before dispatching coding subagents or background builds. Also use for finite model experiments, benchmarking, worker routing decisions, and picking a metered open-weight model when the subscription limits are spent.
---

# Delegate

The coordinator (Astra or Opus 5.5 when available) owns decomposition, briefs, routing, review, the affected gate, integration and shipping. Workers own one bounded deliverable each: the implementation or investigation, its checks, its evidence and its report. Never delegate the final review or security judgement. Global `CLAUDE.md` says when to delegate and that the main channel is for orchestration; this skill says how.

- **Keep for yourself any work whose design you cannot fully spell out in the brief**, and delegate security-boundary tests only after you have named all four boundaries in the brief yourself.
- **One implementation per task.** Model experiments are optional, on demand, and never hold up shipping (see `references/shadow-benchmarking.md`).
- **Work Chris hands straight to a worker** comes into the coordinator's review with its brief and result, so it is not an invisible side task.
- **A repo that a project's relay owns takes code only as a ticket for that project.** No other session builds, pushes or releases there; its relay lands work through its own checks, and a second builder ships the relay's unfinished commits and blocks its landing.
- **A second opinion** on tricky work, conflicting evidence or a consequential decision: a fresh expert at a higher supported effort, given the original task, constraints, artefacts and the specific doubt, not the coordinator's conclusion. Record the effort setting. Not for routine work. When Chris names a model, provider or effort for a task, keep it; neither the second-opinion escalation nor the routing defaults override his choice.
- **Messages between agents** carry only completion, a genuine blocker, or a decision outside the brief. Wait on completion notifications, not sleep or status-poll loops; quiet output alone is not a stall. Keep Chris updated normally.
- **Judge by accepted outcome**, counting Chris's correction time and coordinator review, not token price alone.

## Who sees the output decides whether to delegate

Ask who ends up looking at the output, not how hard the ticket is. Judge by what a human sees, not which workspace the diff is in: a backend change that alters what a page shows is a UX ticket; a frontend caching change is not.

- **No human-visible surface, verifiable from here** (a test, a curl, a telemetry query, a stored row): delegate it whole, in the background, several at once, and close on green.
- **A UX design call with nothing decided behind it** (layout, placement, a new page or flow, what a screen is): build it interactively with Chris against a dev server he can drive. Agents are reliable at logic and blind to what a person sees. A well-written brief does not lift this; an artboard does.
- **A design question that turns on Chris's intent** rather than anything in the repo: delegate only the reading (what the tickets say, contradictions, what each option forecloses) as a spike that stops before recommending. Then decide with him. Once a recommendation exists he is anchored.

### Copy is not a blocker

Wording never blocks a ticket, never makes it interactive, and is never parked for Chris to check.

1. The artboard wins. A string on a prototype ships verbatim.
2. Where nothing supplies a string, write the obvious one, ship it, and list every composed string in the report. If the surface has an artboard, add the new string to it in the same change.
3. Copy an agent speaks (replies, prompts, tool descriptions) is corrected by evals, not by Chris.

### Delegating UX: the artboard is the entry condition

UX work is delegable when the design is fixed in an artboard or prototype the brief names by path. The brief then says:

1. The prototype is the authority and the prose summarises it; where they disagree, follow the prototype and say so.
2. Follow its copy exactly, and never borrow a string from an unrelated surface.
3. Name every surface the prototype covers, and check each one, including worker or agent strings the change makes untrue.
4. Return the artefact (the exact rendered string), not a claim about it.

A prototype settles the taste question, so the worker builds rather than evaluates, and routing follows the logic, not the taste column. Gaps the prototype does not draw (a state, an error case) are a question if they are a design call, and written if they are only wording.

## Verify every worker yourself

A worker's "done" is a claim, whatever the model. Before trusting a branch: confirm a commit exists (`git log -1`), the worktree is clean, and re-run the affected gate yourself. A report that does not quote each gate step's literal exit status or pass count is unverified. In a repo with CI, a PR has passed only when its checks report green: queued or running means wait, and no checks reported means it has not passed (a workflow file GitHub cannot parse runs nothing and reports nothing). In a repo with no CI, the affected gate is the bar.

### The gate is the AFFECTED gate

Each repo's `CLAUDE.md` defines two gates. **Affected**: the tests the diff can reach (in vitest, `--changed <base-ref>`) plus a typecheck per touched area; workers run it and you re-run it. **Full**: the whole suite, run by CI on every push; nobody runs it locally without a specific reason, because parallel workers on one box starve each other.

- Never put a suite-wide command in a brief (`npm run check`, `npm test --workspace <name>`, a bare `vitest run`). A workspace-scoped test script is usually the full suite under a smaller name.
- Do not restate gate commands in the brief; name the base ref for `--changed`.
- `codex_arm.sh` and `pi_bench.py` append `scripts/worker_rules.md` (job boundary, gate, no push, no delegating). Agent-tool workers get neither, so append its contents to every Agent-tool brief.

### Landing ends with removing the worktree

Once a worker's commit is on the remote, stop anything still running from its directory, `git worktree remove` it, and `git branch -d` its branch (merged only; keep unmerged refs). Agent-tool `isolation: "worktree"` only removes worktrees with no changes, so every committing worker leaves one behind. A task whose worktree still exists is not finished.

## Routing

Pick the cheapest worker that clears the bar. When axes conflict on anything that ships: intelligence > taste > cost. Escalate to a smarter worker without asking when output misses the bar. Never use Haiku. Use Astra, Opus 5.5 or Fable 5.2 workers only for a named hard question or consequential judgement.

Scores scaled 1–10 from the Artificial Analysis index and cost per task (2026-10-29); higher is better, and cheaper on cost. Taste is Chris's judgement.

| model | cost | intelligence | taste | reach |
|---|---|---|---|---|
| gpt-6.1-sol / xhigh | 9 | 9 | 5 (unjudged) | `scripts/codex_arm.sh` default |
| gpt-6-astra / xhigh | 6 | 9.5 | 8 | `codex_arm.sh` model argument `gpt-6-astra`; CLI default in `~/.codex/config.toml` |
| opus-5.5 / xhigh | 4 | 10 | 9 | Agent tool `model: "opus"`, `effort: "xhigh"` |
| sonnet-5.5 / xhigh | 5 | 8.5 | 7 | Agent tool `model: "sonnet"` |
| fable-5.2 / high | 3 (replays) | unscored | unscored | Agent tool `model: "fable"`, `effort: "high"` |

Run workers at high effort. Use xhigh only for a named hard task: a fault with an unknown cause or a second opinion. Security and privacy boundaries go to Fable at high. The table was measured at xhigh, Fable at high.

- **Codex gpt-6.1-sol**: the default worker for every task, hard ones and visual polish included, because Opus budget runs out. Give UI tasks an exact spec or artboard. Fire and forget. Its known failure is weakening a test to pass, so either put security- or privacy-boundary tests on fable/high or diff every touched test file against its pre-change version.
- **Agent tool sonnet / opus**: when you need to steer mid-flight, or a Codex result missed the bar. Sonnet for mechanical work (bulk edits, renames, scaffolds, doc updates, broad searches); opus for a redo and aesthetic work with no artboard. Pass `effort` explicitly on every opus or fable dispatch and record it (`opus/high`), because the default can silently drop.
- **Agent tool fable / high**: security- and privacy-boundary work, and any change that must hold an invariant a spec states. In replays of past tickets it alone held a spec-stated approval rule; elsewhere it matched Opus at about 1.2× Opus's token cost.
- **Taste ≥ 7** only for aesthetic judgement: visual design, or an API shape others must live with. Composing a string does not count, an artboard removes the requirement, and logic a user can reach (redirects, access gates, migrations, stores, CLIs) is not a taste job.
- **Metered lane** (OpenRouter, paid per token), when the subscriptions are spent or a cheap open-weight model suits the task: `z-ai/glm-5.3-flash` by default, `z-ai/glm-5.3` for a verification rig, a judgement between paths, or a retry. Code-only slices, never UI or API shape. Run the acceptance check yourself: both sometimes leave an acceptance item undone beside a green gate. Run with `pi_bench.py --plain` (see `references/run-mechanics.md`).
- **The 27agents fleet** runs a bounded task in the production sandbox on any OpenRouter model under a per-job cost cap: for a non-Anthropic model, or parallel runs that would overload this box. Claude workers stay local. Commands: `references/run-mechanics.md`.
- **If pi's Anthropic route answers 400 "Third-party apps now draw from your extra usage"**, use `claude -p` instead (see `references/run-mechanics.md`).
- **Before dispatching**, check `jq -r '.models[].slug' ~/.codex/models_cache.json`. If it lists a newer Sol or Astra than the table, use it and tell Chris the table needs a refresh from Artificial Analysis.

Dispatch Codex with `scripts/codex_arm.sh <label> <brief-file> [base-ref]`, which prepares a worktree and starts the run. Check dependency setup before dispatch rather than assuming the launcher supplies it. The cost ledger is `~/vault/data/model-bench/runs.jsonl`, read alongside the project's delegation log; keep missing measurements as unknown.

## References

- `references/run-mechanics.md`: read at each phase. Task shape (plan, fix, spike); briefing and the brief template; isolation, dependencies and landing (rebase or squash from the main checkout, the sweep, Go worktree cleanup); running Codex, an OpenRouter worker, the fleet, or `claude -p`; review before merge and review-round limits; continuation; the delegation log.
- `references/shadow-benchmarking.md`: before running or grading a model experiment.
- `references/arm-safety.md`: before changing a launcher script, watching a long-running worker, or sweeping worktrees.
