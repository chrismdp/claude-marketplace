#!/bin/bash
# Gather a week's worth of raw material for /dream to chew on.
# Outputs a single markdown blob to stdout for the agent to read.
#
# Inputs collected:
#   - New atomic concept notes (vault root *.md created in window, excluding
#     daily notes YYYY-MM-DD.md and system files)
#   - New entries in links/reference/ (saved articles, transcripts, PDFs)
#   - "### Wiki Ingest" sections from daily notes in the window
#   - Active projects (status doing or todo)
#
# Usage: collect.sh [--days N]    (default 7)

set -uo pipefail

DAYS=7
while [ $# -gt 0 ]; do
  case "$1" in
    --days) DAYS="$2"; shift 2 ;;
    *) echo "ERROR: unknown flag: $1" >&2; exit 1 ;;
  esac
done

VAULT="${VAULT_DIR:-$HOME/vault}"
cd "$VAULT" || exit 1

# Window: today and back DAYS days
SINCE_DATE=$(date -d "$DAYS days ago" +%Y-%m-%d)
TODAY=$(date +%Y-%m-%d)

echo "# Dream input: thoughts from $SINCE_DATE to $TODAY"
echo
echo "Window: last $DAYS days"
echo "Generated: $(date '+%Y-%m-%d %H:%M')"
echo

# --- New atomic concept notes in vault root ---
echo "## New concept notes ($DAYS days)"
echo
COUNT=0
while IFS= read -r f; do
  base=$(basename "$f")
  # Skip daily notes (YYYY-MM-DD.md) and known system files
  if [[ "$base" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\.md$ ]]; then continue; fi
  case "$base" in
    Inbox.md|REMINDERS.md|CLAUDE.md|MEMORY.md|TODO.md) continue ;;
    *-W[0-9][0-9].md) continue ;;          # weekly notes YYYY-Wnn.md
    *-Q[1-4].md) continue ;;               # quarterly notes
    *-[0-9][0-9].md) continue ;;           # monthly notes YYYY-MM.md
  esac
  COUNT=$((COUNT + 1))
  title="${base%.md}"
  # Print a brief: title + first 30 lines of body (after frontmatter if any)
  echo "### [[$title]]"
  echo
  echo "Path: \`$f\` · Modified: $(date -r "$f" '+%Y-%m-%d')"
  echo
  python3 - "$f" <<'PY'
import sys, re
path = sys.argv[1]
try:
    with open(path) as fh:
        text = fh.read()
except Exception:
    sys.exit(0)
# Strip leading YAML frontmatter
if text.startswith('---\n'):
    end = text.find('\n---\n', 4)
    if end > 0:
        text = text[end + 5:]
# First 40 non-empty lines of body, max 1500 chars
lines = [ln for ln in text.splitlines()]
out = []
chars = 0
for ln in lines[:80]:
    out.append(ln)
    chars += len(ln) + 1
    if chars > 1500:
        out.append("... (truncated)")
        break
print("\n".join(out).strip())
PY
  echo
  echo "---"
  echo
done < <(find "$VAULT" -maxdepth 1 -name "*.md" -newermt "$SINCE_DATE" -type f 2>/dev/null | sort)
echo "_Total new concept notes: ${COUNT}_"
echo

# --- New entries in links/reference/ ---
echo "## New saved sources in links/reference/ ($DAYS days)"
echo
LCOUNT=0
while IFS= read -r f; do
  LCOUNT=$((LCOUNT + 1))
  base=$(basename "$f" .md)
  echo "### [[$base]]"
  echo
  echo "Path: \`$f\` · Modified: $(date -r "$f" '+%Y-%m-%d')"
  # Print just the frontmatter + first 6 lines of body — these are large files
  python3 - "$f" <<'PY'
import sys
path = sys.argv[1]
try:
    with open(path) as fh:
        text = fh.read()
except Exception:
    sys.exit(0)
out_lines = []
in_fm = False
fm_done = False
body_lines = 0
for i, ln in enumerate(text.splitlines()):
    if i == 0 and ln.strip() == '---':
        in_fm = True
        out_lines.append(ln)
        continue
    if in_fm and not fm_done:
        out_lines.append(ln)
        if ln.strip() == '---':
            fm_done = True
        continue
    if fm_done:
        out_lines.append(ln)
        body_lines += 1
        if body_lines >= 8:
            out_lines.append("... (body truncated — full source on disk)")
            break
print("\n".join(out_lines))
PY
  echo
  echo "---"
  echo
done < <(find "$VAULT/links/reference" -maxdepth 1 -name "*.md" -newermt "$SINCE_DATE" -type f 2>/dev/null | sort)
echo "_Total new saved sources: ${LCOUNT}_"
echo

# --- Wiki Ingest sections from daily notes ---
echo "## Wiki Ingest sections from daily notes ($DAYS days)"
echo
WCOUNT=0
for offset in $(seq 0 "$DAYS"); do
  d=$(date -d "$offset days ago" +%Y-%m-%d)
  daily="$VAULT/$d.md"
  [ ! -f "$daily" ] && continue
  # Extract any "### Wiki Ingest" sections (until next ### or ## header)
  EXTRACT=$(python3 - "$daily" <<'PY'
import sys, re
path = sys.argv[1]
try:
    with open(path) as fh:
        text = fh.read()
except Exception:
    sys.exit(0)
# Find all "### Wiki Ingest" sections — they may have a timestamp suffix
blocks = re.findall(r'(### Wiki Ingest[^\n]*\n.*?)(?=\n###|\n##|\Z)', text, re.DOTALL)
for b in blocks:
    print(b.strip())
    print()
PY
)
  if [ -n "$EXTRACT" ]; then
    WCOUNT=$((WCOUNT + 1))
    echo "### From [[$d]]"
    echo
    echo "$EXTRACT"
    echo "---"
    echo
  fi
done
echo "_Daily notes with Wiki Ingest: ${WCOUNT}_"
echo

# --- Active projects (status doing/todo only, skip done/someday) ---
echo "## Active projects (status: doing or todo)"
echo
ACOUNT=0
while IFS= read -r pf; do
  slug=$(basename "$(dirname "$pf")")
  status=$(python3 - "$pf" <<'PY'
import sys, re
try:
    with open(sys.argv[1]) as fh:
        text = fh.read()
except Exception:
    sys.exit(0)
if not text.startswith('---'):
    sys.exit(0)
end = text.find('\n---\n', 4)
if end < 0:
    sys.exit(0)
fm = text[4:end]
m = re.search(r'^status:\s*(\S+)', fm, re.MULTILINE)
if m:
    print(m.group(1).strip())
PY
)
  if [ "$status" = "doing" ] || [ "$status" = "todo" ]; then
    ACOUNT=$((ACOUNT + 1))
    echo "- [[$slug]] (status: $status)"
  fi
done < <(find "$VAULT/projects" -maxdepth 2 -name "PROJECT.md" -type f 2>/dev/null)
echo
echo "_Active projects: ${ACOUNT}_"
