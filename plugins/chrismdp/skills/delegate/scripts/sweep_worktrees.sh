#!/usr/bin/env bash
# Sweep spent delegation worktrees.
#
# It exists because the "clean up after landing" rule in SKILL.md / references/run-mechanics.md did not fire for
# the things that actually accumulated. On 2026-08-07 a repo held 33 worktrees; 24
# were SHADOW arms, which by design are never landed, so a rule phrased "after
# landing" never applied to them. A shadow's worktree is spent once it has been
# GRADED — the bench ledger is the record, not the working directory.
#
# Safety, in order:
#   - never touches a worktree it believes is live (see --min-age-hours)
#   - dry run unless --yes
#   - removes WORKTREES freely, but only deletes branches that are MERGED
#     (git branch -d refuses unmerged ones; unmerged shadow refs are kept, since
#     they hold the graded diff and cost nothing but a ref)
#
# Usage:
#   sweep_worktrees.sh                    # dry run, show what would go
#   sweep_worktrees.sh --yes              # do it
#   sweep_worktrees.sh --yes --min-age-hours 2
#   sweep_worktrees.sh --yes --keep foo --keep bar
set -euo pipefail

dry=1
min_age_hours=6
keep=()

while [ $# -gt 0 ]; do
  case "$1" in
    --yes) dry=0; shift ;;
    --min-age-hours) min_age_hours=${2:?}; shift 2 ;;
    --keep) keep+=("${2:?}"); shift 2 ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    *) echo "sweep_worktrees: unknown arg: $1" >&2; exit 2 ;;
  esac
done

root=$(git rev-parse --show-toplevel)
cd "$root"
status_dir="$root/.claude/arm-status"
now=$(date +%s)
removed=0; kept_live=0

is_kept() {
  local n=$1
  for k in ${keep+"${keep[@]}"}; do [ "$k" = "$n" ] && return 0; done
  return 1
}

# Longest paths first so nested worktrees go before their parents.
while IFS=$'\t' read -r wt br; do
  [ "$wt" = "$root" ] && continue
  name=$(basename "$wt")
  short=${br#refs/heads/}

  if is_kept "$name" || is_kept "$short"; then
    echo "KEEP  $name (--keep)"; kept_live=$((kept_live + 1)); continue
  fi

  # An arm writes .claude/arm-status/<branch>.done when it exits. No sentinel plus a
  # recent commit means it is probably still running, so leave it alone. This is the
  # rule that makes the sweep safe to run while a build is in flight.
  if [ ! -f "$status_dir/$short.done" ]; then
    tip=$(git -C "$wt" log -1 --format=%ct 2>/dev/null || echo "$now")
    age_h=$(( (now - tip) / 3600 ))
    if [ "$age_h" -lt "$min_age_hours" ]; then
      echo "KEEP  $name (no sentinel, tip ${age_h}h old < ${min_age_hours}h — may be live)"
      kept_live=$((kept_live + 1)); continue
    fi
  fi

  dirty=$(git -C "$wt" status --porcelain 2>/dev/null | wc -l)
  note=""
  [ "$dirty" -gt 0 ] && note=" (discarding $dirty uncommitted files)"
  if [ "$dry" -eq 1 ]; then
    echo "would remove  $name$note"
  else
    git worktree remove --force "$wt" >/dev/null 2>&1 && echo "removed  $name$note"
  fi
  removed=$((removed + 1))
done < <(git worktree list --porcelain \
          | awk '/^worktree /{w=$2} /^branch /{print w"\t"$2}' \
          | awk '{print length, $0}' | sort -rn | cut -d' ' -f2-)

if [ "$dry" -eq 0 ]; then
  git worktree prune
  # Merged only: the content is already on main, so the ref is pure clutter.
  # git branch -d refuses anything unmerged, which is the guard, not an accident.
  git branch --merged main | grep -vE '^\*|^\s*main$' | while read -r b; do
    is_kept "$b" && continue
    git branch -d "$b" >/dev/null 2>&1 && echo "deleted branch  $b"
  done
fi

echo
echo "worktrees swept: $removed   kept as live: $kept_live"
echo "unmerged branches retained (graded shadow diffs): $(git branch --no-merged main | wc -l)"
[ "$dry" -eq 1 ] && echo "DRY RUN — re-run with --yes to act."
exit 0
