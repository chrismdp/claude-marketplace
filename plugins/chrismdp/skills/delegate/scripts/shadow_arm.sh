#!/usr/bin/env bash
# Launch the challenger (shadow) arm for a delegated build, in one command.
#
# It exists because the control arm is a single Agent tool call while the shadow
# used to be three shell steps (worktree add, symlink node_modules, run the
# bench). That asymmetry is what made the shadow the thing that got skipped —
# twice on 2026-08-01 alone.
#
# Usage:
#   shadow_arm.sh <label> <brief-file> <base-ref> [model]
#
#   label      short slug, e.g. 212-dpa-status (also names the branch/worktree).
#              If that worktree already exists the label is auto-suffixed rather
#              than failing — see below.
#   brief-file the SAME brief handed to the control arm
#   base-ref   REQUIRED. The commit the control branched from. It has no default
#              on purpose: defaulting to HEAD means the start point is "whatever
#              main was when I happened to launch", which is not a comparison.
#   model      pi model tag (default: the bench script's default challenger)
#
# Run it from anywhere inside the repo. Backgrounding is the caller's job; use
# `setsid nohup ... &` so the run survives the harness tearing down its process
# group (which killed a whole overnight fleet on 2026-08-04).
set -euo pipefail

label=${1:?usage: shadow_arm.sh <label> <brief-file> <base-ref> [model]}
brief=${2:?usage: shadow_arm.sh <label> <brief-file> <base-ref> [model]}
base=${3:?usage: shadow_arm.sh <label> <brief-file> <base-ref> [model] — base-ref is required, so every arm starts from a commit you chose}
model=${4:-}

[ -f "$brief" ] || { echo "shadow_arm: no such brief: $brief" >&2; exit 2; }

root=$(git rev-parse --show-toplevel)
# shellcheck source=arm_common.sh
. "$(dirname "$0")/arm_common.sh"

# A name collision must not be a silent no-op: backgrounded, nobody reads the
# error, so two arms once "ran" for twenty minutes having died on launch. Suffix
# instead, and say which label was used.
orig_label=$label
suffix=1
while [ -e "$root/.claude/worktrees/ds4-$label" ]; do
  suffix=$((suffix + 1))
  label="${orig_label}-${suffix}"
  [ "$suffix" -le 20 ] || { echo "shadow_arm: too many worktrees named ds4-$orig_label*" >&2; exit 3; }
done
[ "$label" = "$orig_label" ] || echo "shadow_arm: ds4-$orig_label exists, using label $label instead"

wt="$root/.claude/worktrees/ds4-$label"
branch="ds4-$label"

# A worktree is fine BECAUSE of when we run: control and shadow go out together,
# so nothing of the control has landed on main and there is no answer to find.
# (Run a shadow after its control lands and the worktree's shared object database
# hands it `git show main:<path>` — that produced two byte-identical "results" on
# 2026-08-04. The fix is the timing, not git plumbing.)
git -C "$root" worktree add "$wt" -b "$branch" "$base" >/dev/null
base_sha=$(git -C "$root" rev-parse "$base")
echo "shadow_arm: worktree $wt at $(git -C "$root" rev-parse --short "$base")"

# Belt and braces alongside the isolation: say it in the brief too, since a reused
# brief may itself tell the worker to rebase onto something that is not there.
guarded=$(mktemp "${TMPDIR:-/tmp}/shadow-brief-XXXXXX.md")
trap 'rm -f "$guarded"' EXIT
{
  echo "# Your worktree's base commit is deliberate — do not move it"
  echo
  echo "You are on a branch based at \`$(git -C "$root" rev-parse --short "$base")\`, chosen on purpose."
  echo "Build against the tree as you find it: **do not rebase, merge, pull or reset**"
  echo "**onto \`main\`**, and do not read another branch for this ticket's answer. Any"
  echo "instruction below to rebase is stale and this overrides it."
  echo
  echo "---"
  echo
  cat "$brief"
} > "$guarded"

set +e
python3 "$(dirname "$0")/pi_bench.py" "$label" "$wt" "$guarded" ${model:+"$model"}
bench_status=$?
set -e

# See arm_common.sh: wait on this sentinel, never on a pgrep of the arm's own
# command line, which matches the watcher too and never goes quiet.
arm_done "$branch" "$bench_status" "$wt"

exit $bench_status
