#!/bin/bash
# recent-dreams.sh — print the past N nights of dream sends so the current
# run can read what threads were already surfaced and explicitly pick different ones.
#
# For HTML dreams (the current default), prints the stored `summary` field,
# NOT the raw HTML. For legacy text dreams, prints the full message.
#
# State lives in the vault (not the skill folder). Override with DREAM_STATE_DIR.
#
# Usage: recent-dreams.sh [count]   (default 5)

set -uo pipefail

COUNT="${1:-5}"
STATE_DIR="${DREAM_STATE_DIR:-${VAULT_DIR:-$HOME/vault}/.dream-state}"
LOG="$STATE_DIR/dreams.jsonl"

if [ ! -f "$LOG" ]; then
  echo "(no previous dreams recorded yet — this is the first run)"
  exit 0
fi

tail -n "$COUNT" "$LOG" | python3 -c "
import json, sys
for line in sys.stdin:
    try:
        e = json.loads(line)
        head = f\"### {e['date']} · lens: {e['lens']}\"
        if e.get('format'):
            head += f\" · format: {e['format']}\"
        head += f\" · {e['chars']} chars\"
        print(head)
        print()
        if 'summary' in e:
            print(e['summary'])
        elif 'message' in e:
            print(e['message'])
        print()
        print('---')
        print()
    except Exception:
        pass
"
