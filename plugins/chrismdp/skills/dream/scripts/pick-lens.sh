#!/bin/bash
# pick-lens.sh — picks a random lens for tonight's dream so successive nightly
# runs don't keep surfacing the same threads. Output is a short instruction
# paragraph the dream skill incorporates at step 2 to force a fresh angle.
#
# Usage: pick-lens.sh   (line 1: the lens label, for logging; line 2: the lens instruction)

set -uo pipefail

VAULT="${VAULT_DIR:-$HOME/vault}"

# ----- lens roller -----
# 10 lenses, equal probability. RANDOM is seeded from time + pid so cron runs differ.
LENS_NUM=$((RANDOM % 10))

emit() {
  printf '%s\n%s\n' "$1" "$2"
}

pick_random_file() {
  # $1 = find expression, prints one random matching file
  find $1 2>/dev/null | shuf -n 1
}

# ---- lens 0: random concept note from the past month ----
if [ "$LENS_NUM" = "0" ]; then
  NOTE=$(find "$VAULT" -maxdepth 1 -name "*.md" -newermt "30 days ago" -type f \
    ! -name "20[0-9][0-9]-[0-9][0-9]-[0-9][0-9].md" \
    ! -name "Inbox.md" ! -name "REMINDERS.md" ! -name "CLAUDE.md" \
    ! -name "20[0-9][0-9]-W[0-9][0-9].md" ! -name "20[0-9][0-9]-Q[1-4].md" \
    2>/dev/null | shuf -n 1)
  TITLE=$(basename "$NOTE" .md)
  emit "recent-note:$TITLE" "Tonight's lens — random thread from the past month: open with the note [[$TITLE]] (created in the past 30 days). Look at the month's material *through that note* — what does it extend, what does it contradict, what does it leave unfinished?"
  exit 0
fi

# ---- lens 1: random article from links/reference in the past month ----
if [ "$LENS_NUM" = "1" ]; then
  REF=$(find "$VAULT/links/reference" -maxdepth 1 -name "*.md" -type f \
    -newermt "30 days ago" 2>/dev/null | shuf -n 1)
  if [ -n "$REF" ]; then
    TITLE=$(basename "$REF" .md)
    emit "article:$TITLE" "Tonight's lens — random article from the past month: re-surface the saved source [[$TITLE]] from links/reference. Read its frontmatter and key points, then ask: does it resonate with — or sit alongside — anything else from the past 30 days? Build the dream around the bridge, or surface it as a re-read if no bridge."
    exit 0
  fi
  # fall through if no eligible file
  LENS_NUM=4
fi

# ---- lens 2: mission filter ----
# Reads the user's mission from a vault note if present — falls back to a generic prompt.
if [ "$LENS_NUM" = "2" ]; then
  # The canonical mission note is "My Mission - ...". A bare -iname "*mission*"
  # substring-matches Permissions / Commission / Emissions and grabbed the wrong
  # note (2026-05-26: it picked the "Enterprise AI Bottleneck ... Permissions" note).
  # Prefer the "My Mission" note, then a title-leading "Mission", then word-boundary "mission".
  MISSION_FILE=$(find "$VAULT" -maxdepth 1 -iname "My Mission*.md" -type f 2>/dev/null | head -1)
  [ -z "$MISSION_FILE" ] && MISSION_FILE=$(find "$VAULT" -maxdepth 1 -iname "Mission *.md" -o -iname "Mission-*.md" -type f 2>/dev/null | head -1)
  [ -z "$MISSION_FILE" ] && MISSION_FILE=$(find "$VAULT" -maxdepth 1 -type f -iname "*.md" 2>/dev/null | grep -iE '(^|/| )mission( |-|\.)' | head -1)
  if [ -n "$MISSION_FILE" ]; then
    MISSION_TITLE=$(basename "$MISSION_FILE" .md)
    emit "mission-filter" "Tonight's lens — mission audit: read this week's input *only* through your mission as captured in [[$MISSION_TITLE]]. Where did the week's material strengthen the mission? Where did it conflict or cut against it? Where did it offer a position that is genuinely counter-mission?"
  else
    emit "mission-filter" "Tonight's lens — mission audit: stress-test this week's material against your stated mission or guiding theme. Where did the week strengthen it? Where did the week conflict with it? Surface the strongest pro and the strongest contra, and sit with the gap."
  fi
  exit 0
fi

# ---- lens 3: counter-current ----
if [ "$LENS_NUM" = "3" ]; then
  emit "counter-current" "Tonight's lens — find the contradiction: ignore the patterns that 'go with the grain'. Instead surface the single strongest *contradiction* this week — two notes that disagree, or a note that contradicts what you were saying a month ago. Live in the tension; do not resolve it."
  exit 0
fi

# ---- lens 4: random dictionary word (lateral) ----
if [ "$LENS_NUM" = "4" ]; then
  WORDS_FILE="$(dirname "$0")/words.txt"
  WORD=""
  if [ -f "$WORDS_FILE" ]; then
    WORD=$(shuf -n 1 "$WORDS_FILE")
  elif [ -f /usr/share/dict/words ]; then
    WORD=$(grep -E "^[a-z]{5,12}$" /usr/share/dict/words 2>/dev/null | shuf -n 1)
  fi
  WORD="${WORD:-threshold}"
  emit "lateral:$WORD" "Tonight's lens — lateral lens (random word): '$WORD'. View this week's material through this word as a metaphor or frame. What from the week looks different when seen through '$WORD'? Don't force it — if the word is genuinely irrelevant, name that and pick the most striking note instead. But try the lens first."
  exit 0
fi

# ---- lens 5: window jolt — narrow to past 3 days ----
if [ "$LENS_NUM" = "5" ]; then
  emit "window:3days" "Tonight's lens — short window jolt: re-run with **3 days** of input instead of 30. What's fresh from the past 72 hours that the wider month-view would have buried? Go narrow and recent."
  exit 0
fi

# ---- lens 6: window jolt — quarter-wide to 90 days ----
if [ "$LENS_NUM" = "6" ]; then
  emit "window:90days" "Tonight's lens — quarter-wide window: re-run with **90 days** of input. Look for slow-burn threads building across the quarter — things showing up in March/early April that the past month is still picking up. Bias hard towards notes from days 30-90 ago that the month view doesn't reach."
  exit 0
fi

# ---- lens 7: forgotten thread ----
if [ "$LENS_NUM" = "7" ]; then
  emit "forgotten-thread" "Tonight's lens — forgotten thread: find a topic you were writing about 2-4 weeks ago that has gone quiet, but that recent material touches. Surface the silence — what stopped? Was it resolved, abandoned, or just buried under more urgent threads?"
  exit 0
fi

# ---- lens 8: person-focused ----
if [ "$LENS_NUM" = "8" ]; then
  emit "person-focused" "Tonight's lens — one person: pick one person who appeared most in the past month's transcripts/notes (or pick at random from the month's person notes). Trace what their thinking *did to the vault* over the past 30 days. What did they push you to articulate that you hadn't already?"
  exit 0
fi

# ---- lens 9: open tension ----
if [ "$LENS_NUM" = "9" ]; then
  emit "open-tension" "Tonight's lens — sit with the tension: find the strongest unresolved tension in the past month's material and *do not resolve it*. The whole dream is one long sitting-with. Ask questions, hold the contradiction open, do not propose actions or syntheses."
  exit 0
fi

# fallback
emit "default" "Tonight's lens — default: surface 2-4 connection threads from the past month, prose form, with titled sections, ending each with a question rather than a decision."
