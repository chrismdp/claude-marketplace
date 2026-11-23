# Arm safety

An arm is one worker run started by a launcher script.

## Never edit a launcher script while it is running

Bash reads a script from disk by byte offset as it runs, so rewriting it in place kills the running arm, usually silently, before it writes its sentinel or ledger row. That leaves any watcher waiting forever and a paid run unrecorded.

Before editing anything in `scripts/`, check `ps -eo args | grep '[c]odex_arm'`. If an arm is running, wait, or write the new version to a temp file and `mv` it into place (an atomic rename leaves the running process on the old file).

The sentinel is written after the timeout whatever the exit status, so a missing sentinel means the script was destroyed, not that it timed out. Do not grade that arm: recover the work with a fresh `codex exec` on the dirty worktree and record the arm as inconclusive.

## The sweep is not multi-session safe

`sweep_worktrees.sh` judges a worktree spent from its sentinel and tip age, not from which session launched it, so it will remove another session's worktrees. Where another session may be working, run `git worktree list`, account for each, and remove only the arms you launched, by name.

## Watch three signals: sentinel, process, log growth

An arm can wedge itself (for example, a script it wrote loops forever), and then the sentinel is absent, the process is alive and the tree is clean, exactly as for slow work. The separating signal is log growth: `pi_bench.py` streams to `~/vault/data/model-bench/logs/<stamp>-<label>.jsonl`, and five flat minutes on a live process is a stall worth inspecting.

Watch a worker by its completion sentinel and real process exit, never by a log phrase or `pgrep -f`, which matches the watcher's own command line and never ends.

- **Diagnose with the process tree**: `ps -eo pid,ppid,etimes,stat,args --forest` under the `pi_bench.py` pid. A child in state `R` with elapsed time near the stall length is the culprit.
- **Unwedge rather than kill the arm**: kill the runaway child by PID, never `pkill -f` (it matches your own shell). Record the intervention in the ledger row; grade the diff but treat its timing as void.

## Read progress from commits, not `git status`

A clean tree means either "committed its work" or "did nothing", so a dirty-file count inverts the moment an arm succeeds.

```bash
git -C "$W" log --oneline "$BASE"..HEAD     # the real answer
git -C "$W" status --short | wc -l          # only alongside the above
```

The sentinel's `head=` and `uncommitted_files=` are written by the arm itself; when it disagrees with your poll, trust the sentinel. A wrong ledger row is worse than a missing one.
