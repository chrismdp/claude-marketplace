#!/usr/bin/env bash
# Behaviour test for compress_logs.sh against a sandbox log directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
sandbox="$(mktemp -d)"
trap 'rm -rf "$sandbox"' EXIT
fail() { echo "FAIL: $1"; exit 1; }

echo '{"old":1}' > "$sandbox/20260801T000000-old.jsonl"
touch -d '3 days ago' "$sandbox/20260801T000000-old.jsonl"
echo '{"new":1}' > "$sandbox/20260909T000000-new.jsonl"
echo 'x' > "$sandbox/notes.txt"
touch -d '3 days ago' "$sandbox/notes.txt"

# Dry run changes nothing.
out="$(BENCH_LOGS="$sandbox" "$here/compress_logs.sh")"
[ -f "$sandbox/20260801T000000-old.jsonl" ] || fail "dry run compressed a file"
grep -q 'would compress  20260801T000000-old.jsonl' <<<"$out" || fail "dry run did not list the old log"
grep -q 'DRY RUN' <<<"$out" || fail "dry run did not say it was a dry run"

# --yes compresses only finished logs, keeps recent ones and non-log files.
BENCH_LOGS="$sandbox" "$here/compress_logs.sh" --yes >/dev/null
[ -f "$sandbox/20260801T000000-old.jsonl.gz" ] || fail "old log was not gzipped"
[ ! -f "$sandbox/20260801T000000-old.jsonl" ] || fail "old plain log still present"
[ "$(gzip -dc "$sandbox/20260801T000000-old.jsonl.gz")" = '{"old":1}' ] || fail "gzipped content differs"
[ -f "$sandbox/20260909T000000-new.jsonl" ] || fail "recent log was touched"
[ -f "$sandbox/notes.txt" ] || fail "non-log file was touched"

# A shorter age threshold catches the recent one too.
BENCH_LOGS="$sandbox" "$here/compress_logs.sh" --yes --min-age-hours 0 >/dev/null
[ -f "$sandbox/20260909T000000-new.jsonl.gz" ] || fail "min-age-hours 0 did not compress the recent log"

echo "PASS"
