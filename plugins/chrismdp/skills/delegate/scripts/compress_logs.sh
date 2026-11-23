#!/usr/bin/env bash
# Gzip finished benchmark logs.
#
# pi_bench.py streams every model event to ~/vault/data/model-bench/logs/<stamp>-<label>.jsonl.
# A long arm writes gigabytes: on 2026-09-09 the directory held 35GB across 453 logs and the
# disk was full. The logs are evidence and stay, but a finished log is never appended to, so
# it can live gzipped. JSONL compresses about ten to one, and `gzip -dc` reads it back.
#
# A log is finished when nothing has written to it for --min-age-hours (default 24) and no
# process holds it open. The mtime check is the same "is it live" proxy the worktree sweep uses;
# the open-file check guards an arm that stalled rather than ended (see arm-safety.md).
#
# Usage:
#   compress_logs.sh                    # dry run, show what would go
#   compress_logs.sh --yes              # do it
#   compress_logs.sh --yes --min-age-hours 2
set -euo pipefail

dry=1
min_age_hours=24
logs="${BENCH_LOGS:-$HOME/vault/data/model-bench/logs}"

while [ $# -gt 0 ]; do
  case "$1" in
    --yes) dry=0; shift ;;
    --min-age-hours) min_age_hours="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[ -d "$logs" ] || { echo "no log directory at $logs" >&2; exit 1; }

if command -v pigz >/dev/null 2>&1; then zip=(pigz); else zip=(gzip); fi

compressed=0
skipped_open=0
before=0
after=0
while IFS= read -r -d '' f; do
  name="$(basename "$f")"
  if command -v fuser >/dev/null 2>&1 && fuser -s "$f" 2>/dev/null; then
    echo "skip (open)  $name"
    skipped_open=$((skipped_open + 1))
    continue
  fi
  size=$(stat -c %s "$f")
  before=$((before + size))
  if [ "$dry" -eq 1 ]; then
    echo "would compress  $name  ($((size / 1024 / 1024))MB)"
  else
    "${zip[@]}" "$f" && echo "compressed  $name"
    after=$((after + $(stat -c %s "$f.gz")))
  fi
  compressed=$((compressed + 1))
done < <(find "$logs" -maxdepth 1 -type f -name '*.jsonl' -mmin "+$((min_age_hours * 60))" -print0 | sort -z)

echo
echo "logs compressed: $compressed   skipped as still open: $skipped_open"
if [ "$dry" -eq 0 ]; then
  echo "size before: $((before / 1024 / 1024))MB   after: $((after / 1024 / 1024))MB"
else
  echo "size: $((before / 1024 / 1024))MB"
  echo "DRY RUN — re-run with --yes to act."
fi
exit 0
