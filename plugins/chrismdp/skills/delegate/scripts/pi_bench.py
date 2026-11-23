#!/usr/bin/env python3
"""Run a brief through `pi` in a worktree, measure it, append one ledger line.

  pi_bench.py <label> <worktree> <brief-file> [model]   # run + log (challenger)
  pi_bench.py --plain <label> <worktree> <brief-file> [model]
      # one pass, no coaching, no review, no ledger row: an ordinary worker run.
      # Use this for delegation. The flags below are the opt-in comparison.
  pi_bench.py --record-control --label L --model M \
      (--from-agent-transcript F | --from-codex-log F)
  pi_bench.py --compare                                 # cost/time/quality by control

Cost is computed here from token counts, NOT from a runner's own `cost` field —
pi falls back to default pricing for model ids missing from its catalog (the
dated `-0731` tags) and reports roughly 4x too high.

This file is the only place prices live. A copy anywhere else drifts silently,
because nothing compares the two — point at this table rather than restating it.
"""
import json, os, subprocess, sys, time
from datetime import datetime
from pathlib import Path

# USD per token: (uncached input, output, cached input).
#
# Challenger rates from https://openrouter.ai/api/v1/models; control rates are
# each vendor's published headline meter rate. Controls are priced here so a
# control arm's cost is MEASURED from its own token counts rather than
# reconstructed later from the challenger's volume — which is all the ledger
# could do for its first 27 rows, because nothing recorded the control at all.
PRICES = {
    # Challengers (OpenRouter)
    # The DATED tag, checked against OpenRouter's catalog 2026-08-04. It is
    # cheaper than the floating `-flash` alias (0.14/0.28) — check which one an
    # arm actually ran before pricing it.
    "deepseek/deepseek-v4-flash-0731": (0.09e-6, 0.18e-6, 0.018e-6),
    "deepseek/deepseek-v4-pro": (0.435e-6, 0.87e-6, 0.0087e-6),
    # Open-weight candidates added 2026-09-17 for the openweight-delegation
    # experiment (all from https://openrouter.ai/api/v1/models, read that day).
    # Every one of these is open-weight (`hugging_face_id` set) and supports
    # tool calls; all cost $10/M output or less. Keep this list and
    # `doc/openweight-delegation-experiment-2026-09-17.md` in step.
    "z-ai/glm-5.3": (1.4e-6, 4.4e-6, 0.26e-6),
    "z-ai/glm-5.3-flash": (0.09e-6, 0.3e-6, 0.018e-6),
    "deepseek/deepseek-v4.1-flash": (0.15e-6, 0.6e-6, 0.003e-6),
    "minimax/minimax-m3": (0.3e-6, 1.2e-6, 0.06e-6),
    "moonshotai/kimi-k2.7-code": (0.7062e-6, 3.21e-6, 0.18e-6),
    "qwen/qwen3.8-2.4t-a95b": (2.0e-6, 6.0e-6, 0.25e-6),
    # Controls, headline meter rates (checked 2026-08-07). Cached input is 10%
    # of the uncached rate for every vendor here.
    "gpt-5.6-sol": (5e-6, 30e-6, 0.5e-6),
    "claude-fable-5": (10e-6, 50e-6, 1.0e-6),
    "claude-fable-5-2": (8e-6, 40e-6, 0.2e-6),
    "claude-opus-5-5": (4e-6, 20e-6, 0.2e-6),
    "claude-opus-5": (5e-6, 25e-6, 0.5e-6),
    "claude-opus-4-8": (5e-6, 25e-6, 0.5e-6),
    # Sonnet 5 headline is $3/$15; an intro rate of $2/$10 runs to 2026-08-31.
    # The headline is what a meter charges after that, so it is what we compare.
    "claude-sonnet-5": (3e-6, 15e-6, 0.3e-6),
}
# Outcomes a pair can be COMPARED on. `rejected` belongs here and its absence
# was the fourth silent bug in this ledger, all four erring the challenger's
# way (2026-08-21). Excluding it meant a pair whose challenger produced
# nothing usable vanished from the table entirely: the quality column could
# not report a failure even in principle, so it always read as some mix of
# clean and with-fixes, and the money spent on runs that delivered nothing
# was left out of the cost ratio. Seven pairs were hidden this way, five of
# them against gpt-5.6-sol controls. A comparison that cannot show a loss is
# not a comparison.
COMPARABLE = {"shipped-clean", "shipped-with-fixes", "rejected"}
DEFAULT_MODEL = "deepseek/deepseek-v4-flash-0731"
# Overridable so the write paths can be exercised without appending test rows to
# the real ledger. A recording script with no safe way to rehearse it gets
# rehearsed on production data, once, by someone in a hurry.
LEDGER = Path(os.environ.get("BENCH_LEDGER") or Path.home() / "vault/data/model-bench/runs.jsonl")
LOGS = LEDGER.parent / "logs"  # gitignored; a long run writes gigabytes, compress_logs.sh gzips finished ones


def cost_of(model, u):
    """USD for one run's usage, or None if the model has no price on file.

    Cache WRITES are charged as a multiple of the input rate rather than as their
    own column, because the multiple is a vendor fact rather than a per-model
    price: Anthropic bills 1.25x for a 5-minute entry and 2x for a 1-hour one,
    while OpenAI charges writes at the plain input rate. `u` may carry
    `cacheWrite5m` / `cacheWrite1h`; a run that reports neither is unaffected.

    This is not a rounding detail. One reconstructed control arm wrote 1.9M
    cache-creation tokens — about $12 at Opus rates — which a model that only
    counted reads would have silently dropped from the comparison.
    """
    pin, pout, pcache = PRICES.get(model, (None, None, None))
    if pin is None:
        return None
    w5, w1 = (1.25, 2.0) if model.startswith("claude-") else (1.0, 1.0)
    return (u["input"] * pin
            + u["output"] * pout
            + u["cacheRead"] * pcache
            + u.get("cacheWrite5m", 0) * pin * w5
            + u.get("cacheWrite1h", 0) * pin * w1)


def measure(log):
    """Sum usage over assistant messages, from the per-message `message_end`
    events rather than from `agent_end`'s list.

    `agent_end.messages` is only the messages still in the context WINDOW, so a
    run that compacted reports a fraction of what it spent — and the fraction
    lands in the ledger looking like an ordinary number, understating exactly
    the long runs that cost the most. Caught 2026-08-11: one challenger's
    agent_end held 2 assistant messages and 2,942 output tokens where
    message_end had 59 and 29,625, a ~10x understatement that would have been
    published as a 3,100x cost win over its control.

    The two agree exactly when nothing compacts, so this is strictly better
    rather than a trade. `agent_end` still supplies the run's final text and,
    by its absence, the `truncated` flag."""
    msgs, ends, turns, tools, final, stop = None, [], 0, 0, "", None
    for line in log.read_text(errors="replace").splitlines():
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "agent_end":
            msgs = ev.get("messages") or msgs
        elif ev.get("type") == "message_end":
            m = ev.get("message") or {}
            ends.append(m)
            # The LAST assistant stop reason. "length" means the model was cut off
            # mid-work by a context/output ceiling — a very different thing from
            # finishing badly, and invisible in `truncated`, which only detects a
            # killed process. Two runs were graded as capability failures on
            # 2026-08-03 when they had in fact hit this ceiling.
            if m.get("stopReason"):
                stop = m["stopReason"]
        elif ev.get("type") == "turn_end":
            turns += 1
            tools += len(ev.get("toolResults") or [])
    u = {k: 0 for k in ("input", "output", "cacheRead", "reasoning")}
    for m in ends if ends else (msgs or []):
        if m.get("role") != "assistant":
            continue
        for k in u:
            u[k] += (m.get("usage") or {}).get(k) or 0
    # The deliverable is whichever message ENDED the run, and agent_end is the
    # authority on that. Falling back to the message_end stream keeps a killed
    # run's last words.
    for m in msgs if msgs is not None else ends:
        if m.get("role") != "assistant":
            continue
        for c in m.get("content") or []:
            if c.get("type") == "text" and c.get("text"):
                final = c["text"]
    return u, turns, tools, final, msgs is None, stop


# Appended to EVERY arm's brief, control and challenger alike. Unlike COACHING
# below it is not levelling — it is the boundary of the job, so it applies to
# whoever is doing it. It lives in a plain file that this runner and the shell arm
# scripts both read, so the two arms cannot drift apart.
#
# A capable worker with spare time will helpfully do the coordinator's job — grade
# arms, compare branches, write the log — unless told the job has edges, and one
# that did so reported confidently on the wrong arm. Telling it is deterministic;
# remembering to tell it is not, which is why this lives in the runner.
WORKER_RULES = (Path(__file__).parent / "worker_rules.md").read_text()


# Appended to every challenger brief, automatically (Chris, 2026-08-01).
#
# It lives HERE rather than in the brief because the coordinator has to remember
# to paste it there, and demonstrably does not. Baked into the runner it cannot
# be forgotten, and every row in the ledger from COACHING_FROM onward had it.
#
# This deliberately makes the challenger's brief differ from the control's. That
# is levelling, not tilting: the Agent-tool control already gets this coaching
# free from its harness (skills, project CLAUDE.md, tool access) and the pi
# challenger has none of it. The question being measured is "how good is this
# model as a worker WITH a harness", not "which raw model wins on an identical
# prompt". Give each arm its best shot; grade the diff.
#
# Both instructions target one observed failure shape: the challenger does the
# literal task well and stops at its edge.
# BUMP THIS DATE whenever the COACHING text below changes. It is stamped onto
# every ledger row, so each generation of the instructions stays comparable
# against the others. Leaving it stale silently merges two different experiments.
COACHING_VERSION = "2026-08-21"
COACHING = """

---

## Standing instructions for this run

**Finish what you notice, or say plainly that you are not.** If you spot a
problem your change creates or exposes (a sentence that now reads badly, a value
that is now wrong, an adjacent case your fix makes reachable), fix it if it is
inside the spirit of this task, and flag it explicitly in your report if it is
not. What is not acceptable is noticing it, mentioning it in passing, and leaving
it half-done. Spotting a defect and reporting it is worth much less than spotting
it and closing it.

**Protect what survives.** Whatever you delete, refactor, or move, the code and
behaviour that REMAINS must end up at least as well covered as it started. If a
test file you remove was the only coverage of something that is staying, re-home
that coverage before you delete it. Report the test count before and after and
account for the difference explicitly: an unexplained drop will be read as lost
coverage, not as cleanup.

**Fix the class, not the instance.** Before you fix the thing the ticket names,
search the whole repo for every other place with the same defect, the same stale
string, the same pattern — every workspace, not only the one your file is in. A
worker string can be made untrue by a web change. List what you find, then fix
all of it. Half a sweep is not a smaller version of the right answer: the sites
you left behind now contradict the ones you changed.

**Never edit a test, a fixture, or a fake so your change passes.** Changing a
test double to emit what your fix expects is the same defect as relaxing an
assertion, and it is harder to see. If a fake has to change for your code to go
green, that is evidence your code is wrong, not that the fake was.

**Commit before you stop.** Your branch is the deliverable. A tidy finish with an
uncommitted worktree is a failed run, however good the diff was. If you are
running short of room, commit what is coherent and say in your report what is
missing.

**Do not write a justification you have not checked.** If your reason for a
shortcut depends on how an external system or library behaves, verify it and say
what you checked. A confident comment asserting behaviour you never verified is
worse than no comment, because it will be read as a finding.
"""


# The review pass, run by this runner after the model believes it has finished
# (Chris, 2026-08-19). Across 57 coached runs the dominant failure was not a
# wrong diff but a premature stop: ten swept part of a class, three finished
# cleanly and never committed anything at all. More instructions in the brief
# have 57 rows of evidence against them, because the failure IS the stop — so
# rather than ask harder, the runner re-enters the worktree with a fresh context
# and makes the model look at its own work.
REVIEW = """
# Review pass

You have already worked this ticket in this worktree and believed you were
finished. This is a second look with a fresh head.

**Do not start the ticket again and do not widen it.** Your job is to find what
the first pass left undone, finish that, and commit.

Start with what is actually there:

    git status --short
    git diff
    git log --oneline -3

Then check each of these against the ticket, and fix what fails:

1. **Is it committed?** An uncommitted worktree is a failed run however good the
   diff is. If work is stranded, commit it.
2. **Did you sweep the class, or only the instance?** Search the whole repo —
   every workspace, not just the one you edited — for other sites with the same
   defect, stale string, or pattern. A sweep that landed some sites and not
   others has left the repo contradicting itself.
3. **Did a test, fixture, or fake change to accommodate your code?** Diff every
   test file you touched against its pre-change version. If a double now emits
   what your fix expects, the fix is the defect.
4. **Does the affected gate still pass?** Re-run it and quote the literal
   output. **If it fails, first find out whether the failure is yours.** Stash
   your whole diff, re-run at the base ref named in your brief, and restore.
   A failure that reproduces at the base predates you: do not repair it, do not
   work around it, report it and answer BLOCKED below. A failure that does not
   reproduce is yours, so fix it.
5. **Did you make a comment, doc line or string FALSE?** Not only ones you
   wrote: anything your change contradicts, anywhere in the repo. Read outward
   from your diff and fix what it falsified, or say why you left it.

End your final message with exactly one of these lines, and nothing after it:

    REVIEW: FIXED       - you changed something, so another look is warranted
    REVIEW: COMPLETE    - you checked all five and there was nothing left to do
    REVIEW: BLOCKED     - the affected gate fails for a reason that predates your
                          diff, proven at the base ref. Say which test and what
                          you saw. Your own work may still be sound; this says
                          the bar is red and not by your hand
"""

# How many review passes at most. Two is a bound, not a target: the loop stops as
# soon as a pass reports COMPLETE. Env-overridable so the write path can be
# rehearsed without burning real passes.
MAX_REVIEW_PASSES = int(os.environ.get("BENCH_MAX_REVIEW_PASSES") or 2)

# A run that ended normally can be reviewed. So can one that hit the context
# ceiling - a fresh context is exactly what stranded work needs. A run that died
# (error, or no stop reason at all) says nothing about the model, and reviewing
# it would spend money turning an inconclusive row into a misleading one.
REVIEWABLE_STOPS = {"stop", "length"}


def should_review(stop_reason):
    return stop_reason in REVIEWABLE_STOPS


def review_verdict(final):
    """FIXED / COMPLETE / BLOCKED / None from the reviewer's final message.

    BLOCKED exists because its absence made an arm lie. On #317 (2026-08-21) a
    challenger inherited a red gate it had not caused, and the only two verdicts
    it could give were COMPLETE, which was false, or FIXED, which would loop it
    against a failure it must not touch. It answered COMPLETE and was graded
    gate=fail for walking past a red bar. The instruction to re-run and quote the
    gate was already there and was obeyable; what was missing was any way to
    report the result truthfully. Check whether obeying is POSSIBLE before
    rewriting the words.

    Takes the LAST sentinel, not the first: a model that restates its
    instructions before obeying them would otherwise read as already finished.
    """
    if not final:
        return None
    seen = None
    for line in final.splitlines():
        t = line.strip()
        if t in ("REVIEW: FIXED", "REVIEW: COMPLETE", "REVIEW: BLOCKED"):
            seen = t.split(": ", 1)[1]
    return seen


def review_should_continue(verdict):
    """Only an explicit FIXED earns another pass.

    An absent verdict must NOT read as 'keep going', or a model that cannot
    follow the sentinel instruction would loop to the cap on every single run.
    """
    return verdict == "FIXED"


def arm_identity(row):
    """The challenger as `model @ harness`, e.g. `deepseek-v4-flash-0731 @ 0819`.

    A model and the instructions it was given are ONE arm, not two facts about a
    row: the same weights under different coaching are a different worker, and
    averaging the two generations together hides whichever change was being
    tested. Rows with no `coaching` key ran before the harness existed and say so
    rather than defaulting to the current one.
    """
    model = (row.get("model") or "?").split("/")[-1]
    v = row.get("coaching")
    return f"{model} @ {v[5:7]}{v[8:10]}" if v else f"{model} @ uncoached"


def merge_usage(usages):
    keys = ("input", "output", "cacheRead", "reasoning")
    return {k: sum(u.get(k, 0) for u in usages) for k in keys}


def assemble_prompt(brief_text, plain=False):
    """The full prompt for one worker run.

    The job boundary (`worker_rules.md`) applies to every run. The COACHING text
    is part of the benchmark harness: it levels the field for a comparison and
    its version is stamped onto each ledger row, so a plain run leaves it out.
    """
    return brief_text + WORKER_RULES + ("" if plain else COACHING)


def _pi(model, workdir, prompt, log):
    """One `pi` invocation into its own log. Returns (proc, measurement)."""
    with log.open("wb") as out:
        proc = subprocess.run(
            ["pi", "--model", f"openrouter/{model}", "--mode", "json", "--no-session", "-p"],
            cwd=workdir, input=prompt, stdout=out, stderr=subprocess.PIPE,
        )
    return proc, measure(log)


def run(label, workdir, brief, model, plain=False):
    LOGS.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now():%Y%m%dT%H%M%S}"
    log = LOGS / f"{stamp}-{label}.jsonl"
    mode = "plain" if plain else "coached"
    print(f"[pi-bench] {label} :: {model} in {workdir} ({mode})", file=sys.stderr)

    prompt = assemble_prompt(Path(brief).read_text(), plain=plain).encode()

    t0 = time.monotonic()
    p, (u, turns, tools, final, truncated, stop_reason) = _pi(model, workdir, prompt, log)

    # The review pass (see REVIEW above). The arm is not finished when the model
    # says so; it is finished when a fresh-context pass over its own worktree
    # finds nothing left. Every pass is summed into the ONE row below, so cost
    # and effort describe the whole arm rather than only its first half.
    usages, logs = [u], [str(log)]
    review_passes, verdict, skipped = 0, None, None
    review_stop = None
    if plain:
        # Plain mode is one pass by definition: the review loop is the harness.
        skipped = "plain-mode"
    elif should_review(stop_reason):
        while review_passes < MAX_REVIEW_PASSES:
            review_passes += 1
            rlog = LOGS / f"{stamp}-{label}-review{review_passes}.jsonl"
            print(f"[pi-bench] {label} :: review pass {review_passes}", file=sys.stderr)
            p, (ru, rturns, rtools, rfinal, _rt, review_stop) = _pi(
                model, workdir, REVIEW.encode(), rlog)
            usages.append(ru); logs.append(str(rlog))
            turns += rturns; tools += rtools
            if rfinal:
                final = rfinal
            verdict = review_verdict(rfinal)
            if not review_should_continue(verdict):
                break
    else:
        skipped = stop_reason or "no-stop-reason"

    wall = time.monotonic() - t0
    u = merge_usage(usages)
    cost = cost_of(model, u)

    row = {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        # Which side of the pair this row is. Rows are joined on `label`, so a
        # ticket's control and challenger share one label and differ here.
        # Rows written before 2026-08-07 have no `arm` key; every one of them is
        # a challenger, because nothing recorded controls at all.
        "arm": "challenger",
        "label": label, "model": model, "wall_s": round(wall, 1),
        "in": u["input"], "out": u["output"], "cache_read": u["cacheRead"],
        "reasoning": u["reasoning"], "turns": turns, "tool_calls": tools,
        "tok_per_s": round(u["output"] / wall, 1) if wall else None,
        "cost_usd": round(cost, 5) if cost is not None else None,
        "exit": p.returncode, "truncated": truncated, "stop_reason": stop_reason,
        "worktree": str(workdir), "log": str(log), "logs": logs,
        # `stop_reason` stays the FIRST pass's, so it means what it meant in the
        # 63 rows written before the review pass existed: did the model stop on
        # its own, or was it cut off. How the ARM ended is `review_stop_reason`
        # plus `review_verdict`. Redefining the old field in place would have
        # silently merged two different measurements, which is how this ledger
        # has been corrupted three times before.
        "passes": 1 + review_passes, "review_passes": review_passes,
        "review_verdict": verdict, "review_stop_reason": review_stop,
        "review_skipped": skipped,
        # WHICH coaching this run got, as a version stamp, not a boolean. Rows
        # written before 2026-08-01 have no `coaching` key at all and ran
        # uncoached. A boolean would silently conflate every future revision of
        # COACHING with the first one; the date keeps each generation of the
        # instructions comparable against the others, the same way any other
        # coaching change is tracked.
        "coaching": COACHING_VERSION,
        "gate": None, "outcome": "pending-review",
    }
    if not plain:
        with LEDGER.open("a") as f:
            f.write(json.dumps(row) + "\n")

    if p.stderr:
        for line in p.stderr.decode(errors="replace").strip().splitlines()[-5:]:
            print(f"[pi stderr] {line}", file=sys.stderr)
    if plain:
        cost_s = f"${cost:.4f}" if cost is not None else "unknown"
        print(
            f"[pi-worker] {label} :: wall {round(wall, 1)}s, "
            f"out {u['output']} tokens, cost {cost_s}, exit {p.returncode}",
            file=sys.stderr,
        )
    else:
        print(json.dumps(row, indent=2))
    if final:
        print("\n--- worker final message ---\n" + final)
    return p.returncode


def measure_codex(log):
    """Usage for a `codex exec --json` run, summed over its turn.completed events.

    Verified against codex-cli 0.142.5 on 2026-08-07: one exec emits exactly one
    `turn.completed`, whose usage aggregates every model request inside the turn
    (a two-tool-call probe reported 52,887 input against 17,494 for a trivial
    one). Summing is therefore both correct today and safe if codex ever splits
    a run across turns.

    `input_tokens` is the OpenAI-standard TOTAL and INCLUDES `cached_input_tokens`,
    so the uncached remainder is the difference. Getting that backwards would
    double-count the cached span at 10x its real rate.
    """
    u = {k: 0 for k in ("input", "output", "cacheRead", "reasoning")}
    for line in Path(log).read_text(errors="replace").splitlines():
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") != "turn.completed":
            continue
        usage = ev.get("usage") or {}
        cached = usage.get("cached_input_tokens") or 0
        u["cacheRead"] += cached
        u["input"] += max((usage.get("input_tokens") or 0) - cached, 0)
        u["output"] += usage.get("output_tokens") or 0
        u["reasoning"] += usage.get("reasoning_output_tokens") or 0
    return u


def measure_agent(log):
    """Usage for an Agent-tool arm, from its Claude Code subagent transcript.

    Transcripts live at
    ~/.claude/projects/<project>/<session-id>/subagents/agent-<agentId>.jsonl,
    and the agentId is on the Task tool result. This is the ONLY durable record
    of what an Agent-tool arm cost: the completion notification carries the
    numbers once and is then gone, which is why the ledger's first 27 runs had no
    control side at all.

    Anthropic reports cache creation split by TTL and the two bill differently
    (1.25x vs 2x input), so they are kept apart rather than summed into one
    figure that cannot be priced.
    """
    u = {k: 0 for k in ("input", "output", "cacheRead", "cacheWrite5m", "cacheWrite1h")}
    model, first, last, n = None, None, None, 0
    for line in Path(log).read_text(errors="replace").splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("timestamp"):
            first = first or ev["timestamp"]
            last = ev["timestamp"]
        m = ev.get("message") or {}
        usage = m.get("usage")
        if not usage:
            continue
        n += 1
        # `claude-opus-5[1m]` is the 1M-context variant at the same rate; strip
        # the suffix so it prices instead of falling through as an unknown id.
        model = (m.get("model") or model or "").replace("[1m]", "") or None
        cc = usage.get("cache_creation") or {}
        u["input"] += usage.get("input_tokens") or 0
        u["output"] += usage.get("output_tokens") or 0
        u["cacheRead"] += usage.get("cache_read_input_tokens") or 0
        u["cacheWrite5m"] += cc.get("ephemeral_5m_input_tokens") or 0
        u["cacheWrite1h"] += cc.get("ephemeral_1h_input_tokens") or 0
    wall = None
    if first and last:
        try:
            wall = (datetime.fromisoformat(last.replace("Z", "+00:00"))
                    - datetime.fromisoformat(first.replace("Z", "+00:00"))).total_seconds()
        except ValueError:
            pass
    return u, model, wall, n


def record_control(label, model, u, wall_s=None, worktree=None, log=None):
    """Append a CONTROL row for `label`, priced from its own token counts.

    The control is half of every comparison and was, for the ledger's first 27
    rows, entirely absent — so no cost question about them can ever be answered
    with a measurement, only with the challenger's volume repriced. This is the
    fix; use it for every arm, including Agent-tool controls, where the numbers
    exist only in the completion notification and are gone once it scrolls past.
    """
    cost = cost_of(model, u)
    row = {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "arm": "control",
        "label": label, "model": model,
        "wall_s": round(wall_s, 1) if wall_s is not None else None,
        # Sources differ in what they report — a pi run has `reasoning` and no
        # cache-write split, a Claude Code transcript the reverse — so every
        # field is optional and absent ones stay absent rather than being
        # invented as zero.
        "in": u["input"], "out": u["output"], "cache_read": u["cacheRead"],
        **({"reasoning": u["reasoning"]} if "reasoning" in u else {}),
        **({"cache_write_5m": u["cacheWrite5m"]} if u.get("cacheWrite5m") else {}),
        **({"cache_write_1h": u["cacheWrite1h"]} if u.get("cacheWrite1h") else {}),
        "cost_usd": round(cost, 5) if cost is not None else None,
        "worktree": str(worktree) if worktree else None,
        "log": str(log) if log else None,
        "gate": None, "outcome": "pending-review",
    }
    with LEDGER.open("a") as f:
        f.write(json.dumps(row) + "\n")
    print(json.dumps(row, indent=2))
    if cost is None:
        print(f"\n[pi-bench] WARNING: no price on file for {model!r}; cost_usd is null.\n"
              f"Add it to PRICES in {__file__} rather than pricing it in prose.",
              file=sys.stderr)
    return 0



def compare():
    """Cost, time and quality of the challenger against each control model.

    Rows join on `label`; a ticket's two arms share one. Only pairs where the
    challenger actually finished carry a comparison — a contaminated or
    context-truncated arm is real spend but not a real result, and would inflate
    every column while meaning nothing.
    """
    rows = [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]
    by = {}
    for r in rows:
        by.setdefault(r["label"], {})[r.get("arm", "challenger")] = r

    g, missing, ungraded, no_time = {}, [], [], 0
    for label, arms in sorted(by.items()):
        c, k = arms.get("control"), arms.get("challenger")
        # Two different reasons a pair cannot be compared, kept apart because the
        # single word "excluded" hid the one that mattered. A pair with both arms
        # whose challenger is still `pending-review` is UNGRADED and will return
        # to the table; a pair with one arm never will.
        if not c or not k:
            missing.append(label)
            continue
        if k.get("outcome") not in COMPARABLE:
            ungraded.append(label)
            continue
        # Keyed on the CHALLENGER's harness as well as the control, so bumping
        # COACHING_VERSION starts a fresh cohort instead of diluting itself into
        # the old one's average (Chris, 2026-08-19).
        a = g.setdefault((c["model"], arm_identity(k)),
                         {"n": 0, "cc": 0.0, "kc": 0.0,
                          "cw": 0.0, "kw": 0.0, "tn": 0, "out": {}})
        a["n"] += 1
        a["cc"] += c.get("cost_usd") or 0
        a["kc"] += k.get("cost_usd") or 0
        a["out"][k["outcome"]] = a["out"].get(k["outcome"], 0) + 1
        # A control's wall clock is the span of its transcript, which on a
        # stalled or resumed run measures elapsed time rather than work. Where it
        # dwarfs the challenger it is idle, not effort, so it is left out of the
        # time column instead of quietly tripling it.
        cw, kw = c.get("wall_s"), k.get("wall_s")
        if cw and kw and not (cw > 3 * kw and cw > 7200):
            a["cw"] += cw
            a["kw"] += kw
            a["tn"] += 1
        else:
            no_time += 1

    print("| control | challenger | pairs | control $ | challenger $ | cost | control time | challenger time | time | challenger quality |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for (m, kid), a in sorted(g.items(), key=lambda x: -x[1]["cc"]):
        q = ", ".join(f"{v} {kk.replace('shipped-', '')}" for kk, v in sorted(a["out"].items()))
        t = (f"{a['cw']/60:.0f}m | {a['kw']/60:.0f}m | {a['cw']/a['kw']:.2f}x"
             if a["tn"] else "— | — | —")
        print(f"| {m} | {kid} | {a['n']} | ${a['cc']:.2f} | ${a['kc']:.2f} "
              f"| {a['cc']/a['kc']:.0f}x | {t} | {q} |")
    tc = sum(a["cc"] for a in g.values())
    tk = sum(a["kc"] for a in g.values())
    if tk:
        print(f"\nAll comparable pairs: control ${tc:.2f} vs challenger ${tk:.2f} ({tc/tk:.0f}x).")
    print(f"Excluded: {len(missing)} pair(s) missing an arm; {len(ungraded)} not yet "
          f"graded to a terminal outcome; {no_time} more from the time column only, "
          f"as elapsed-not-worked.")



def _flag(argv, name, cast=str):
    """Value of `--name VALUE` in argv, or None if absent or valueless.

    The --record-control block below called this six times and it was never
    defined, so EVERY control-side recording died on a NameError. It stayed
    invisible because codex_arm.sh deliberately does not fail an arm over
    bookkeeping — it warns to stderr and exits 0 — so the ledger reached 47 rows
    without a single control row while every arm reported success (2026-08-07).
    """
    try:
        i = argv.index(name)
    except ValueError:
        return None
    # A truncated command line is a missing value, not a crash.
    return cast(argv[i + 1]) if i + 1 < len(argv) else None


if __name__ == "__main__":
    argv = sys.argv
    if "--compare" in argv:
        compare()
    elif "--record-control" in argv:
        label, model = _flag(argv, "--label"), _flag(argv, "--model")
        if not label or not model:
            sys.exit("--record-control needs --label and --model")
        log = _flag(argv, "--from-codex-log") or _flag(argv, "--from-agent-transcript")
        wall = _flag(argv, "--wall-s", float)
        if _flag(argv, "--from-codex-log"):
            u = measure_codex(log)
        elif _flag(argv, "--from-agent-transcript"):
            u, found_model, found_wall, n = measure_agent(log)
            if n == 0:
                sys.exit(f"no usage found in {log} — wrong transcript?")
            # The transcript names the model it actually ran, which beats what
            # the caller believed it dispatched.
            model, wall = found_model or model, wall if wall is not None else found_wall
        else:
            sys.exit("--record-control needs --from-agent-transcript or --from-codex-log")
        sys.exit(record_control(
            label, model, u,
            wall_s=wall,
            worktree=_flag(argv, "--worktree"),
            log=log,
        ))
    else:
        plain = "--plain" in argv
        args = [a for a in argv[1:] if a != "--plain"]
        if len(args) < 3:
            sys.exit(__doc__)
        sys.exit(run(args[0], args[1], args[2],
                     args[3] if len(args) > 3 else DEFAULT_MODEL,
                     plain=plain))
