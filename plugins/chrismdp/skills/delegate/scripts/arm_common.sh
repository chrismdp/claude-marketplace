#!/usr/bin/env bash
# Shared helpers for the build arms (codex_arm.sh, shadow_arm.sh).
# Sourced, never executed.

# The status dir depends on $root, which the ARM SCRIPTS set but a bare
# `source arm_common.sh` does not. Unset, the helpers below resolved
# "/.claude/arm-status", a path that exists on some boxes and never receives a
# sentinel — so arm_wait polled a directory that could not answer and spun
# silently. On 2026-08-11 that ate 8 hours: both arms of ticket 242 finished in
# 20 minutes and the watch never fired. Default it here so sourcing the file
# standalone (the documented way to run arm_wait as a monitor) just works.
: "${root:=$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"

# Record that an arm has finished, as a FILE.
#
# Why a file and not a process check: the obvious way to wait on a backgrounded
# arm is `pgrep -f '<something in its command line>'`, and that is a trap. pgrep
# matches full command lines, including the WATCHER'S OWN — so a poll loop
# containing the pattern literally matches itself, the arm reads as running
# forever, and the watch never fires. On 2026-08-04 that swallowed the
# completion of two arms that had both finished cleanly, after the same
# self-match had already been diagnosed twice that day. The `[c]odex` bracket
# workaround relies on remembering it in the moment, which is exactly what
# failed. A sentinel cannot match itself.
#
# Usage: arm_done <branch> <exit-status> <worktree>
arm_done() {
  local branch=$1 status=$2 wt=$3
  local dir="${ARM_STATUS_DIR:-$root/.claude/arm-status}"
  mkdir -p "$dir"
  local head
  head=$(git -C "$wt" log --oneline -1 2>/dev/null || echo "NO COMMIT")
  local dirty
  dirty=$(git -C "$wt" status --porcelain 2>/dev/null | wc -l)
  # Written in one move so a reader never sees a half-file.
  cat > "$dir/.$branch.done.tmp" <<EOF
branch=$branch
exit=$status
head=$head
uncommitted_files=$dirty
worktree=$wt
EOF
  mv "$dir/.$branch.done.tmp" "$dir/$branch.done"
}

# Wait for arms to finish and print each one's sentinel as it lands. Give it the
# branch names; it exits when all of them are done. Safe to run as a monitor:
# it watches files, so nothing it prints can be confused for a live process.
#
# Usage: arm_wait <branch> [branch...]
arm_wait() {
  local dir="${ARM_STATUS_DIR:-$root/.claude/arm-status}"
  local remaining=("$@")
  while [ ${#remaining[@]} -gt 0 ]; do
    local still=()
    local b
    for b in "${remaining[@]}"; do
      if [ -f "$dir/$b.done" ]; then
        echo "ARM FINISHED: $b"
        cat "$dir/$b.done"
      else
        still+=("$b")
      fi
    done
    remaining=("${still[@]}")
    [ ${#remaining[@]} -eq 0 ] && break
    sleep 20
  done
}
