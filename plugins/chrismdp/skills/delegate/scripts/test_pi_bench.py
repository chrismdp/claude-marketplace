"""Tests for the pi_bench measurement layer.

The parser is the part worth pinning: a silent bug there produces plausible-
looking but wrong cost/token data, which is worse than no data at all.

Run: python3 -m pytest ~/.claude/skills/delegate/scripts/ -q
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pi_bench  # noqa: E402


def usage(inp=0, out=0, cache=0, reasoning=0):
    return {"input": inp, "output": out, "cacheRead": cache, "reasoning": reasoning}


def assistant(inp=0, out=0, cache=0, reasoning=0, text=None):
    content = [{"type": "text", "text": text}] if text else []
    return {"role": "assistant", "content": content,
            "usage": usage(inp, out, cache, reasoning)}


def write_log(tmp_path, events):
    p = tmp_path / "run.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in events))
    return p


def test_sums_usage_across_assistant_messages(tmp_path):
    log = write_log(tmp_path, [
        {"type": "agent_end", "messages": [
            assistant(inp=100, out=10, cache=5, reasoning=2),
            assistant(inp=200, out=20, cache=7, reasoning=3),
        ]},
    ])
    u, _, _, _, truncated, _stop = pi_bench.measure(log)
    assert u == {"input": 300, "output": 30, "cacheRead": 12, "reasoning": 5}
    assert truncated is False


def test_the_two_event_kinds_are_not_double_counted(tmp_path):
    """Both event kinds carry the same usage; counting both would double it."""
    msg = assistant(inp=100, out=10)
    log = write_log(tmp_path, [
        {"type": "message_end", "message": msg},
        {"type": "agent_end", "messages": [msg]},
    ])
    u, _, _, _, truncated, _stop = pi_bench.measure(log)
    assert u["input"] == 100 and u["output"] == 10
    assert truncated is False


def test_a_compacted_run_is_measured_whole(tmp_path):
    """agent_end carries only the messages still in the window.

    A run that compacted therefore reports a fraction of what it spent, and the
    fraction lands in the ledger looking like an ordinary number. Caught live on
    2026-08-11: a challenger's agent_end held 2 assistant messages and 2,942
    output tokens where message_end had 59 and 29,625, so the row understated
    the run by roughly ten times and made that arm look far cheaper than it was.
    """
    log = write_log(tmp_path, [
        {"type": "message_end", "message": assistant(inp=100, out=10)},
        {"type": "message_end", "message": assistant(inp=200, out=20)},
        {"type": "message_end", "message": assistant(inp=400, out=40)},
        # Compaction dropped the first two from the window.
        {"type": "agent_end", "messages": [assistant(inp=400, out=40)]},
    ])
    u, _, _, _, truncated, _stop = pi_bench.measure(log)
    assert u["input"] == 700 and u["output"] == 70
    assert truncated is False


def test_the_final_text_still_comes_from_agent_end(tmp_path):
    """Usage moved to message_end; the report text must not follow it there.

    agent_end's list is the authority on which message ENDED the run, and it is
    the run's deliverable, so it keeps coming from there.
    """
    log = write_log(tmp_path, [
        {"type": "message_end", "message": assistant(inp=1, text="early draft")},
        {"type": "agent_end", "messages": [assistant(inp=1, text="the report")]},
    ])
    _u, _, _, final, _truncated, _stop = pi_bench.measure(log)
    assert final == "the report"


def test_falls_back_to_message_end_when_killed_midrun(tmp_path):
    """A timeout kill leaves no agent_end — we still want the partial spend."""
    log = write_log(tmp_path, [
        {"type": "message_end", "message": assistant(inp=100, out=10)},
        {"type": "message_end", "message": assistant(inp=50, out=5)},
    ])
    u, _, _, _, truncated, _stop = pi_bench.measure(log)
    assert u["input"] == 150 and u["output"] == 15
    assert truncated is True


def test_ignores_user_messages(tmp_path):
    log = write_log(tmp_path, [
        {"type": "agent_end", "messages": [
            {"role": "user", "content": [], "usage": usage(inp=9999)},
            assistant(inp=100),
        ]},
    ])
    u, _, _, _, _, _stop = pi_bench.measure(log)
    assert u["input"] == 100


def test_counts_turns_and_tool_calls(tmp_path):
    log = write_log(tmp_path, [
        {"type": "turn_end", "toolResults": [{}, {}]},
        {"type": "turn_end", "toolResults": [{}]},
        {"type": "turn_end"},
        {"type": "agent_end", "messages": [assistant(inp=1)]},
    ])
    _, turns, tools, _, _, _stop = pi_bench.measure(log)
    assert turns == 3
    assert tools == 3


def test_returns_last_assistant_text(tmp_path):
    log = write_log(tmp_path, [
        {"type": "agent_end", "messages": [
            assistant(text="first"), assistant(text="final answer")]},
    ])
    _, _, _, final, _, _stop = pi_bench.measure(log)
    assert final == "final answer"


def test_skips_malformed_and_non_json_lines(tmp_path):
    p = tmp_path / "run.jsonl"
    p.write_text(
        'Warning: Model not found for provider "openrouter".\n'
        "{not valid json\n"
        + json.dumps({"type": "agent_end", "messages": [assistant(inp=42)]}) + "\n"
    )
    u, _, _, _, _, _stop = pi_bench.measure(p)
    assert u["input"] == 42


def test_missing_usage_fields_default_to_zero(tmp_path):
    log = write_log(tmp_path, [
        {"type": "agent_end", "messages": [{"role": "assistant", "content": []}]},
    ])
    u, _, _, _, _, _stop = pi_bench.measure(log)
    assert u == {"input": 0, "output": 0, "cacheRead": 0, "reasoning": 0}


def test_cost_uses_our_prices_not_pis(tmp_path):
    u = usage(inp=1_000_000, out=1_000_000, cache=1_000_000)
    cost = pi_bench.cost_of("deepseek/deepseek-v4-flash-0731", u)
    # The DATED tag's real prices (OpenRouter, verified 2026-08-04). Deliberately
    # NOT the floating alias's 0.14/0.28 — pinning those here is what made every
    # recorded cost ~55% too high until it was caught.
    assert cost == 0.09 + 0.18 + 0.018


def test_cost_is_none_for_unpriced_model():
    assert pi_bench.cost_of("some/unknown-model", usage(inp=100)) is None


# --- CLI flag parsing -------------------------------------------------------
# `_flag` was USED six times in the --record-control block and never defined, so
# every control-side recording died on `NameError: name '_flag' is not defined`.
# Nothing noticed because codex_arm.sh deliberately does not block an arm on a
# bookkeeping failure — it warns to stderr and exits 0. The result was a ledger
# of 47 rows without a single control row in it (found 2026-08-07).

def test_flag_reads_the_value_after_the_name():
    assert pi_bench._flag(["x", "--label", "229-race"], "--label") == "229-race"


def test_flag_is_none_when_absent():
    assert pi_bench._flag(["x", "--model", "m"], "--label") is None


def test_flag_casts_when_asked():
    assert pi_bench._flag(["x", "--wall-s", "616.5"], "--wall-s", float) == 616.5


def test_flag_is_none_when_name_is_last_and_has_no_value():
    # A truncated command line must not IndexError the whole run.
    assert pi_bench._flag(["x", "--label"], "--label") is None


# --- The review pass on STOP (Chris, 2026-08-19) ------------------------------
#
# The dominant failure in 57 coached flash runs was not a wrong diff, it was a
# run that stopped while the job was still half done: 10 swept part of a class,
# 3 finished cleanly and never committed at all. Telling the model "be thorough"
# in the brief has 57 rows of evidence against it, because the failure IS the
# stop. So the runner re-enters the worktree after the model believes it is
# finished and makes it look at its own work with a fresh context.


def test_review_runs_after_a_clean_stop():
    assert pi_bench.should_review("stop") is True


def test_review_also_runs_after_a_context_ceiling():
    """A fresh context is exactly what a run that ran out of room needs: the
    work is stranded in the worktree and one more pass can commit it."""
    assert pi_bench.should_review("length") is True


def test_review_is_skipped_when_the_run_itself_failed():
    """stop_reason error/None means the run died, which says nothing about the
    model. Reviewing it would spend money turning an inconclusive row into a
    misleading one."""
    assert pi_bench.should_review("error") is False
    assert pi_bench.should_review(None) is False


def test_verdict_reads_the_sentinel():
    assert pi_bench.review_verdict("Swept the rest of the class.\nREVIEW: FIXED") == "FIXED"
    assert pi_bench.review_verdict("Nothing outstanding.\nREVIEW: COMPLETE") == "COMPLETE"


def test_an_inherited_red_gate_can_be_reported_without_lying():
    """BLOCKED is a verdict, and it does NOT earn another pass.

    Without it an arm that inherits a failing test has only COMPLETE, which is
    false, or FIXED, which loops it against a failure it must not touch. On #317
    (2026-08-21) one answered COMPLETE and was graded gate=fail for it.
    """
    assert pi_bench.review_verdict(
        "eval-harness.test.ts fails at the base ref too.\nREVIEW: BLOCKED"
    ) == "BLOCKED"
    # Looping cannot help: the arm is forbidden from repairing it.
    assert pi_bench.review_should_continue("BLOCKED") is False


def test_verdict_takes_the_LAST_sentinel_not_the_first():
    """A model that restates its instructions before obeying them would
    otherwise be read as having already finished."""
    final = "I will end with REVIEW: COMPLETE when done.\nFixed 3 sites.\nREVIEW: FIXED"
    assert pi_bench.review_verdict(final) == "FIXED"


def test_verdict_is_none_when_the_model_never_emitted_one():
    assert pi_bench.review_verdict("I think that's everything.") is None
    assert pi_bench.review_verdict(None) is None


def test_a_missing_verdict_stops_the_loop_rather_than_spinning():
    """Unknown must not read as 'keep going' — a model that cannot follow the
    sentinel instruction would loop to the cap every single run."""
    assert pi_bench.review_should_continue(None) is False
    assert pi_bench.review_should_continue("COMPLETE") is False
    assert pi_bench.review_should_continue("FIXED") is True


def test_usage_is_summed_across_passes_so_one_row_carries_the_whole_cost():
    a = usage(inp=100, out=10, cache=5, reasoning=2)
    b = usage(inp=50, out=4, cache=1, reasoning=1)
    assert pi_bench.merge_usage([a, b]) == {
        "input": 150, "output": 14, "cacheRead": 6, "reasoning": 3}


def test_merging_no_passes_is_zero_not_a_crash():
    assert pi_bench.merge_usage([]) == {
        "input": 0, "output": 0, "cacheRead": 0, "reasoning": 0}


def test_the_coaching_stamp_moved_so_the_cohorts_stay_separable():
    assert pi_bench.COACHING_VERSION == "2026-08-21"


# --- run() orchestration: the review pass actually happens --------------------

FAKE_PI = r'''#!/usr/bin/env python3
"""Stands in for `pi`: records the prompt it was given, emits one turn.

Emits message_end AND agent_end because the real runner reads the stop reason
from message_end and the final text from agent_end - a fake that emits only one
of them silently skips the review pass.
"""
import json, os, sys
from pathlib import Path
d = Path(os.environ["FAKE_PI_DIR"])
n = len(sorted(d.glob("prompt-*.txt"))) + 1
(d / f"prompt-{n}.txt").write_text(sys.stdin.read())
text = "done" if n == 1 else "checked everything\nREVIEW: COMPLETE"
msg = {"role": "assistant", "content": [{"type": "text", "text": text}],
       "stopReason": "stop",
       "usage": {"input": 10, "output": 5, "cacheRead": 1, "reasoning": 0}}
print(json.dumps({"type": "message_end", "message": msg}))
print(json.dumps({"type": "turn_end", "toolResults": []}))
print(json.dumps({"type": "agent_end", "stopReason": "stop", "messages": [msg]}))
'''


def _fake_pi_env(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"; bindir.mkdir()
    pi = bindir / "pi"; pi.write_text(FAKE_PI); pi.chmod(0o755)
    calls = tmp_path / "calls"; calls.mkdir()
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_PI_DIR", str(calls))
    monkeypatch.setattr(pi_bench, "LEDGER", tmp_path / "runs.jsonl")
    monkeypatch.setattr(pi_bench, "LOGS", tmp_path / "logs")
    return calls


def test_a_clean_stop_gets_a_review_pass_carrying_the_review_prompt(tmp_path, monkeypatch):
    calls = _fake_pi_env(tmp_path, monkeypatch)
    brief = tmp_path / "brief.md"; brief.write_text("# do the ticket\n")
    pi_bench.run("t1", tmp_path, brief, "deepseek/deepseek-v4-flash-0731")

    sent = sorted(calls.glob("prompt-*.txt"))
    assert len(sent) == 2, "the model was never asked to review its own work"
    assert "do the ticket" in sent[0].read_text()
    assert "Review pass" in sent[1].read_text()
    assert "REVIEW: COMPLETE" in sent[1].read_text()


def test_the_row_carries_the_whole_arm_not_just_the_first_pass(tmp_path, monkeypatch):
    _fake_pi_env(tmp_path, monkeypatch)
    brief = tmp_path / "brief.md"; brief.write_text("x")
    pi_bench.run("t2", tmp_path, brief, "deepseek/deepseek-v4-flash-0731")

    row = json.loads((tmp_path / "runs.jsonl").read_text().strip().splitlines()[-1])
    assert row["passes"] == 2 and row["review_passes"] == 1
    assert row["review_verdict"] == "COMPLETE"
    assert row["out"] == 10, "output tokens must sum both passes, or cost is understated"
    assert row["coaching"] == "2026-08-21"


def test_a_dead_run_is_not_reviewed(tmp_path, monkeypatch):
    """Spending a second pass on a run that died turns an inconclusive row into
    a misleading one, and costs money to do it."""
    calls = _fake_pi_env(tmp_path, monkeypatch)
    monkeypatch.setattr(pi_bench, "measure",
                        lambda log: (usage(inp=1, out=1), 1, 1, "died", False, "error"))
    brief = tmp_path / "brief.md"; brief.write_text("x")
    pi_bench.run("t3", tmp_path, brief, "deepseek/deepseek-v4-flash-0731")

    assert len(sorted(calls.glob("prompt-*.txt"))) == 1
    row = json.loads((tmp_path / "runs.jsonl").read_text().strip().splitlines()[-1])
    assert row["passes"] == 1 and row["review_skipped"] == "error"


ALWAYS_FIXED_PI = r'''#!/usr/bin/env python3
"""A model that always claims it fixed something more. Must not loop forever."""
import json, os, sys
from pathlib import Path
d = Path(os.environ["FAKE_PI_DIR"])
n = len(sorted(d.glob("prompt-*.txt"))) + 1
(d / f"prompt-{n}.txt").write_text(sys.stdin.read())
msg = {"role": "assistant", "content": [{"type": "text", "text": "more!\nREVIEW: FIXED"}],
       "stopReason": "stop",
       "usage": {"input": 1, "output": 1, "cacheRead": 0, "reasoning": 0}}
print(json.dumps({"type": "message_end", "message": msg}))
print(json.dumps({"type": "agent_end", "stopReason": "stop", "messages": [msg]}))
'''


def test_a_model_that_always_says_FIXED_stops_at_the_cap(tmp_path, monkeypatch):
    """The loop is bounded, not trusting. Without this an arm that always claims
    more work would spend until something else killed it."""
    calls = _fake_pi_env(tmp_path, monkeypatch)
    (tmp_path / "bin" / "pi").write_text(ALWAYS_FIXED_PI)
    monkeypatch.setattr(pi_bench, "MAX_REVIEW_PASSES", 2)
    brief = tmp_path / "brief.md"; brief.write_text("x")
    pi_bench.run("cap", tmp_path, brief, "deepseek/deepseek-v4-flash-0731")

    assert len(sorted(calls.glob("prompt-*.txt"))) == 3, "1 build + 2 reviews, capped"
    row = json.loads((tmp_path / "runs.jsonl").read_text().strip().splitlines()[-1])
    assert row["review_passes"] == 2 and row["review_verdict"] == "FIXED"


# --- The harness is part of the arm's identity (Chris, 2026-08-19) ------------


def test_arm_identity_names_the_harness_not_just_the_model():
    assert pi_bench.arm_identity(
        {"model": "deepseek/deepseek-v4-flash-0731", "coaching": "2026-08-19"}
    ) == "deepseek-v4-flash-0731 @ 0819"


def test_an_uncoached_row_says_so_rather_than_looking_current():
    assert pi_bench.arm_identity(
        {"model": "deepseek/deepseek-v4-flash-0731"}
    ) == "deepseek-v4-flash-0731 @ uncoached"


def _pair(label, coaching, cost, outcome="shipped-clean"):
    return [
        {"label": label, "arm": "control", "model": "claude-fable-5",
         "cost_usd": 10.0, "wall_s": 100, "outcome": outcome},
        {"label": label, "arm": "challenger", "model": "deepseek/deepseek-v4-flash-0731",
         "coaching": coaching, "cost_usd": cost, "wall_s": 100, "outcome": outcome},
    ]


def test_compare_does_not_merge_two_harness_generations(tmp_path, monkeypatch, capsys):
    """A checkpoint is worthless if the new harness's runs are averaged into the
    old one's — the whole point is telling the two apart."""
    rows = _pair("a", "2026-08-01", 1.0) + _pair("b", "2026-08-19", 2.0)
    led = tmp_path / "runs.jsonl"
    led.write_text("".join(json.dumps(r) + "\n" for r in rows))
    monkeypatch.setattr(pi_bench, "LEDGER", led)

    pi_bench.compare()
    out = capsys.readouterr().out
    assert "@ 0801" in out and "@ 0819" in out, "harness generations were merged"


# --- Plain mode: the comparison harness is opt-in (Chris, 2026-09-18) ---------
#
# Coaching, review passes and the ledger row ARE the experiment. An ordinary
# delegation is one pass with no ledger; comparisons are run ad hoc, on demand.
# The job boundary (worker_rules) still applies to every run, plain or not.


def test_plain_mode_keeps_the_job_boundary_but_drops_the_coaching():
    plain = pi_bench.assemble_prompt("BRIEF", plain=True)
    assert plain.startswith("BRIEF")
    assert pi_bench.WORKER_RULES in plain
    assert pi_bench.COACHING not in plain


def test_coached_mode_still_carries_both():
    coached = pi_bench.assemble_prompt("BRIEF", plain=False)
    assert pi_bench.WORKER_RULES in coached
    assert pi_bench.COACHING in coached
