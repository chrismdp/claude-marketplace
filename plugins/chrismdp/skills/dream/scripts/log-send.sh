#!/bin/bash
# log-send.sh — append a dream send to the JSONL state log so future runs
# can read what threads were already surfaced.
#
# State lives in the user's vault (NOT in the skill folder) so it's never
# committed with the shared skill. Override with DREAM_STATE_DIR if your
# state directory is elsewhere.
#
# Two modes:
#   Text dream (legacy):
#     log-send.sh <lens_label> <message_file>
#     Stores: {date, lens, chars, message}
#
#   HTML dream (current):
#     log-send.sh <lens_label> <html_file> --format <label> --summary <summary_file>
#     Stores: {date, lens, format, chars, html_path, summary}
#     The summary file is short plain text — thread titles, key people, questions.
#     It's what recent-dreams.sh prints, NOT the raw HTML.

set -uo pipefail

LENS="${1:-unknown}"
MAIN_FILE="${2:-}"
shift 2 2>/dev/null || true

FORMAT=""
SUMMARY_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --format) FORMAT="$2"; shift 2 ;;
    --summary) SUMMARY_FILE="$2"; shift 2 ;;
    *) shift ;;
  esac
done

STATE_DIR="${DREAM_STATE_DIR:-${VAULT_DIR:-$HOME/vault}/.dream-state}"
mkdir -p "$STATE_DIR"
LOG="$STATE_DIR/dreams.jsonl"

if [ -z "$MAIN_FILE" ] || [ ! -f "$MAIN_FILE" ]; then
  echo "log-send.sh: main file required" >&2
  exit 1
fi

DATE=$(date '+%Y-%m-%d %H:%M')
CHARS=$(wc -c < "$MAIN_FILE" | tr -d ' ')

python3 - "$DATE" "$LENS" "$CHARS" "$MAIN_FILE" "$FORMAT" "$SUMMARY_FILE" "$LOG" <<'PY'
import json, sys, os
date, lens, chars, main_file, fmt, summary_file, log = sys.argv[1:]

entry = {"date": date, "lens": lens, "chars": int(chars)}

if summary_file and os.path.isfile(summary_file):
    with open(summary_file) as f:
        entry["summary"] = f.read()
    entry["html_path"] = main_file
    if fmt:
        entry["format"] = fmt
else:
    with open(main_file) as f:
        entry["message"] = f.read()

with open(log, "a") as f:
    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
PY
