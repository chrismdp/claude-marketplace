#!/usr/bin/env bash
# Prepare a BLINDED comparison packet for two arms of the same ticket.
#
# Every grade in the bench ledger was written by the same agent that launched the
# arms, wrote both briefs, and had already formed a view about which model should
# win. That is the weakest link in the whole experiment: the three "the shadow
# beat the control" entries rest on the coordinator's own word, and on 2026-08-06
# a worker's confident comparison of two branches turned out to describe a
# different arm than the one it named. Grading is the step most improved by not
# knowing whose work you are looking at.
#
# This script does the part that must be deterministic — extract both diffs,
# shuffle them, and put the answer somewhere the grader cannot see — and stops.
# Dispatching the grader and reading its verdict stays a judgement call.
#
# Usage:
#   blind_grade.sh <base-ref> <branch-a> <branch-b> [out-dir]
#
# Then hand <out-dir>/PROMPT.md to a FRESH agent that has not seen either run,
# and only afterwards read <out-dir>/key.txt to unblind.
set -euo pipefail

base=${1:?usage: blind_grade.sh <base-ref> <branch-a> <branch-b> [out-dir]}
a=${2:?usage: blind_grade.sh <base-ref> <branch-a> <branch-b> [out-dir]}
b=${3:?usage: blind_grade.sh <base-ref> <branch-a> <branch-b> [out-dir]}
root=$(git rev-parse --show-toplevel)
out=${4:-$root/.claude/blind-grade/$(date +%Y%m%dT%H%M%S)}
mkdir -p "$out"

# Coin flip, so the coordinator cannot infer the mapping from the argument order
# it typed. Arm 1 is not "the first one I passed" half the time.
if [ $((RANDOM % 2)) -eq 0 ]; then arm1=$a; arm2=$b; else arm1=$b; arm2=$a; fi

arms=("$arm1" "$arm2")
for n in 1 2; do
  # A plain diff carries file paths and content but no branch name or commit
  # message, so it is already close to anonymous — the identity leaks that remain
  # are in the content, which is what the warning below is for.
  git -C "$root" diff "$base".."${arms[n-1]}" > "$out/arm$n.diff"
done

printf 'arm1=%s\narm2=%s\nbase=%s\n' "$arm1" "$arm2" "$base" > "$out/key.txt"

# The two files that would unblind the packet instantly, and which the worker
# rules forbid an arm from touching at all. If one shows up here, the run broke
# its boundary AND the comparison is compromised; say so loudly rather than
# quietly grading a contaminated packet.
if grep -lE 'model-delegation-experiment\.md|model-bench/runs\.jsonl' "$out"/arm[12].diff >/dev/null 2>&1; then
  echo "blind_grade: WARNING an arm touched the delegation log or bench ledger." >&2
  echo "blind_grade: that breaks worker_rules.md and identifies the arm. Investigate before grading." >&2
fi

cat > "$out/PROMPT.md" <<EOF
Two agents independently implemented the same ticket from the same starting
commit and the same brief. You are grading them blind: you are not told which
model wrote which, and you should not try to guess.

- \`$out/arm1.diff\`
- \`$out/arm2.diff\`

Read both diffs in full, against the ticket they were given.

Answer, in this order:
1. **Which would you merge, and why?** Name one. "Both are fine" is not an
   answer; if they are genuinely equivalent, say which you would merge on a
   coin-flip basis and what would have separated them.
2. **What would you have to fix first** in the one you picked?
3. **Did either weaken, delete, or narrow an existing test** to make its change
   pass? Quote it if so.
4. **Did either accept a false premise** in the brief rather than checking it
   against the code?
5. **Can you tell which is the more capable model?** If yes, say what gave it
   away. If no, say so plainly — that is a real and useful result.

Judge the diffs, not the commit hygiene. Do not run the test suite; assume both
report a green gate, because both did.
EOF

echo "blind_grade: packet at $out"
echo "blind_grade: hand $out/PROMPT.md to a fresh agent; key.txt holds the mapping."
