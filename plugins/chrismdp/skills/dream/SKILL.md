---
name: dream
description: "Pattern-noticing pass over recently captured thoughts. Reads new concept notes, saved articles, and daily-note Wiki Ingest sections; identifies patterns across multiple notes and surfaces tensions and open questions. Delivers as an interactive HTML file attached to Telegram — does NOT save a vault note (the user doesn't read them). Triggers on /dream, 'weekly dream', 'what did I think about this week', 'patterns from this week'."
argument-hint: "[--days N]"
allowed-tools: Read, Edit, Write, Glob, Grep, Skill, Bash(date *), Bash(~/.claude/skills/dream/scripts/collect.sh *), Bash(~/.claude/skills/dream/scripts/log-send.sh *), Bash(~/.claude/skills/dream/scripts/recent-dreams.sh *), Bash(~/.claude/skills/dream/scripts/pick-lens.sh *), Bash(~/.claude/skills/telegram/scripts/send-document.sh *), Bash(rg *), Bash(cat *), Bash(wc *), Bash(ls *), Bash(mkdir *)
---

# Dream

Resurface Chris's own recent thinking: the patterns, tensions and open questions already in his notes. It is a connector, not new analysis; a pattern that needs a frame he never used gets demoted. Run only when invoked (`/dream [--days N]`); scheduled runs are off at Chris's request.

## 1. Roll the lens and check recent dreams

```bash
~/.claude/skills/dream/scripts/pick-lens.sh
~/.claude/skills/dream/scripts/recent-dreams.sh 5
```

Roll the lens once. Its first line is the lens label (`$LENS_LABEL` below, for the caption and the log); the second is the lens instruction.

The lens is the angle of attack and overrides "find the dominant pattern". Read the last five dreams: do not lead with a thread they named, and do not reuse a recent `format:`.

## 2. Gather

```bash
~/.claude/skills/dream/scripts/collect.sh --days 30 > /tmp/dream-input.md
```

Use 30 days unless the lens says `window:3days` or `window:90days`, or Chris passed `--days`. The output holds new concept notes, new `links/reference/` entries, daily-note `### Wiki Ingest` sections and active projects. Read it through the lens, biased towards the quieter corner the lens picked rather than the loudest recent material. Look for recurring entities, notes that contradict or extend each other, and anything touching Chris's mission, client work or commercial commitments. One or two targeted vault searches can show how far back a thread goes ("the 4th note on X").

## 3. Compose the HTML

The dream is a self-contained HTML file sent to Telegram. Never write a vault note, a daily-note entry or a plain-text message instead.

Content:
- The lens, one italic line at the top.
- 2–4 threads, each ending in a question, never a decision or an action list.
- Each thread as 4–6 short atoms, one attributed sentence each, naming the people, conversations, dates and projects. No long prose with bracketed citations.
- Cross-thread bridges shown visually. Weight threads that touch the mission. Two real threads beat a padded four.

Format: pick one not used in the last five dreams. Options include constellation plus swipe carousels, timeline, quote wall, Sankey-style flow, tarot spread of three cards, 2D matrix, static force-graph, map, one hero diagram with annotations, and question-first cards. Use inline SVG freely (`viewBox`, `preserveAspectRatio="xMidYMid meet"`, modest aspect ratio, CSS-variable colours).

Mobile constraints, because Chris reads it on his phone in Telegram's in-app browser:
- No JavaScript: the browser strips `<script>` and `onclick`. Expand and collapse with `<details><summary>`; carousels with `scroll-snap-type: x mandatory`; jumps with `#anchor` links. If an interaction needs JS, make it static.
- No external assets (fonts, images, analytics); system font stack, monospace for metadata.
- No off-canvas panels, click-to-fetch detail or hover-only tooltips.
- No dead links: refer to vault notes as `<em>` text; link only real `https://` URLs.
- `<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">`, single column on narrow screens, tap targets at least 40px.
- Dark background, one consistent accent colour per thread, generous padding. File size 8–25 KB.

Write `/tmp/dream-YYYY-MM-DD.html` and a plain-text recap under 600 characters in `/tmp/dream-YYYY-MM-DD.summary.txt` (thread titles, key entities, the questions, the format). Never log the HTML itself.

## 4. Send and log

Richard owns Dream, so it always goes out through his bot. The caption is Markdown V1: single `*bold*`, no underscores or square brackets.

```bash
DATE=$(date +%Y-%m-%d)
CAPTION="🌙 *Dream — $DATE · $LENS_LABEL*

<one-line tease of the threads>

<one line on how to read the format>"
~/.claude/skills/telegram/scripts/send-document.sh /tmp/dream-$DATE.html --bot-var RICHARD_BOT_TOKEN --caption "$CAPTION"
~/.claude/skills/dream/scripts/log-send.sh "$LENS_LABEL" /tmp/dream-$DATE.html --format "<format used>" --summary /tmp/dream-$DATE.summary.txt
```

Always run `log-send.sh` with `--format` and `--summary`; the next dream's rotation depends on it.
