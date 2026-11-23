#!/usr/bin/env bash
# Launch a Codex build arm in one command.
#
# It exists for the same reason shadow_arm.sh does: an Agent-tool arm is a single
# call with isolation:"worktree", while codex was a manual worktree, a manual
# dependency symlink and a five-flag invocation. Routing follows the path of
# least setup, and on 2026-08-03 that asymmetry produced a ten-ticket raft with
# zero codex runs in it. One command each, so the choice is about fit.
#
# Usage:
#   codex_arm.sh <label> <brief-file> [base-ref] [model] [effort]
#
#   label      short slug, e.g. 218-tool-round (also names the branch/worktree)
#   brief-file the brief to hand the worker, read on stdin by codex exec
#   base-ref   commit to branch from (default: HEAD)
#   model      codex model id (default: gpt-6.1-sol; pass the full id, bare
#              version numbers 400 on this account)
#   effort     reasoning effort (default: high)
#
# Run it from anywhere inside the repo. Backgrounding is the caller's job.
set -euo pipefail

label=${1:?usage: codex_arm.sh <label> <brief-file> [base-ref] [model] [effort]}
brief=${2:?usage: codex_arm.sh <label> <brief-file> [base-ref] [model] [effort]}
base=${3:-HEAD}
model=${4:-gpt-6.1-sol}
effort=${5:-high}

[ -f "$brief" ] || { echo "codex_arm: no such brief: $brief" >&2; exit 2; }

root=$(git rev-parse --show-toplevel)
# shellcheck source=arm_common.sh
. "$(dirname "$0")/arm_common.sh"
wt="$root/.claude/worktrees/codex-$label"
branch="codex-$label"

if [ -e "$wt" ]; then
  echo "codex_arm: $wt already exists; remove it or pick another label" >&2
  exit 3
fi

git -C "$root" worktree add "$wt" -b "$branch" "$base" >/dev/null
echo "codex_arm: worktree $wt at $(git -C "$root" rev-parse --short "$base")"

# Symlink installed deps rather than reinstalling: minutes saved per run, and the
# brief tells the worker not to install. Only link what the repo actually has.
for d in node_modules web/node_modules worker/node_modules; do
  [ -d "$root/$d" ] && ln -sfn "$root/$d" "$wt/$d"
done

# --disable plugins/plugin_sharing keeps an autonomous run on the narrow
# code-editing surface even when the local install has marketplace plugins.
# --dangerously-bypass-approvals-and-sandbox is the flag this version takes
# (NOT --yolo). 2-hour cap: a GUARD against a runaway, not a budget. 40 minutes
# was too short (Chris, 2026-08-19) — a real ticket that touches a store, its
# runner and an admin page runs past it, and a timeout produces exit 124 with a
# dirty tree and no commit, which is indistinguishable from the model failing.
scripts=$(cd "$(dirname "$0")" && pwd)

# Both arms get the same boundary. shadow_arm.sh gets it via pi_bench, which
# appends the same file; codex does not go through pi_bench, so it is stamped
# here. One file, so the two arms cannot drift apart.
brief_stamped=$(mktemp)
trap 'rm -f "$brief_stamped"' EXIT
cat "$brief" "$scripts/worker_rules.md" > "$brief_stamped"

# --json makes the run MEASURABLE: `turn.completed` carries the token breakdown,
# where the plain-text stream reports only a rounded total with no input/output
# split — useless at a 6x output multiplier. --output-last-message keeps the
# human-readable report, which the JSON stream would otherwise cost us.
logdir="$HOME/vault/data/model-bench/logs"
mkdir -p "$logdir"
jsonlog="$logdir/$(date +%Y%m%dT%H%M%S)-$label-codex.jsonl"
lastmsg="$logdir/$(date +%Y%m%dT%H%M%S)-$label-codex.final.md"

echo "codex_arm: running $model (2h cap), events -> $jsonlog"
start=$SECONDS
timeout 7200 codex exec --json --disable plugins --disable plugin_sharing \
  --dangerously-bypass-approvals-and-sandbox -C "$wt" \
  -o "$lastmsg" \
  -c model="$model" -c model_reasoning_effort="$effort" - < "$brief_stamped" > "$jsonlog"
status=$?
wall=$((SECONDS - start))

# A completion SENTINEL, so waiting on an arm never means grepping a process
# table. `pgrep -f '<pattern>'` matches the watcher's own command line whenever
# the pattern is written inline, so the arm reads as running forever and the
# watch stays silent past the moment it was armed for — that cost a whole
# turn on 2026-08-04, having already been diagnosed twice the same day.
# Wait on this file instead: it cannot match itself.
arm_done "$branch" "$status" "$wt"

# Record the CONTROL half of the pair from its own token counts, now, while the
# numbers exist. The ledger's first 27 rows have no control at all, so no cost
# question about them can be answered with a measurement — only with the
# challenger's volume repriced. Never block the arm on a bookkeeping failure.
python3 "$scripts/pi_bench.py" --record-control \
  --label "$label" --model "$model" \
  --from-codex-log "$jsonlog" --wall-s "$wall" --worktree "$wt" \
  || echo "codex_arm: WARNING control row not recorded (log kept at $jsonlog)" >&2

if [ -s "$lastmsg" ]; then
  echo "--- worker final message ---"
  cat "$lastmsg"
fi
echo "codex_arm: $label exited $status in ${wall}s (worktree $wt, branch $branch)"
exit $status
