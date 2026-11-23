---
name: capture
description: Capture atomic thoughts into the Obsidian vault following Zettelkasten principles. Use when user says "capture this", "capture that thought", "make sure you've got that", "save this thought", or when extracting insights from discussions, articles, or meetings.
argument-hint: "[thought to capture]"
---

# Capture

Turns a thought into an atomic concept note, or extends an existing one. Called directly by Chris and by `/process-link`, `/process-transcript`, `/process-sessions`, `/sunday`, `/inbox` and agents processing routed transcripts. In those autonomous runs there is no one to ask: skip the confirmation prompts and decide.

## Step 1: Identify the thought

If Chris has not stated the thought, propose a one-line summary and confirm it. One concept per note.

## Step 2: Search

Search the vault and blog with several distinctive phrases (concept, phrase, named entity), and separately search `~/vault/projects -g PROJECT.md` for live work the thought touches.

## Step 3: Merge or create

Default to merging into the closest existing note. Merge when the thought is a new angle, supporting quote, contradicting source or example of the same concept, and the note's title and framing would still describe it. Append `## Update from [[source]] — YYYY-MM-DD`. If the source has its own name for the thing (a named event, idea or framework), add that name to the note's `aliases` so links to it resolve.

Create a new note only when the thought is a different unit: merging would change what the existing note is about, or the shapes differ (a framework vs a single observation). A named thing that is its own concept gets its own note. Link the new note from the closest existing one under `## Related Thoughts`. When it could go either way, merge.

Interactively, show the candidate: "This seems related to [[Existing Note]] — I'd update that. OK, or a new concept?" Chris's answer wins.

## Step 4: Note layout

```markdown
---
type: concept
first_mentioned: [[YYYY-MM-DD]]
source_person: [[Person Name]]   # when it came from a transcript, meeting or conversation
---

[The thought, short, original wording kept, attributed inline: "[[James Steiner]] observed that..."]

## Active Projects

- [[projects/SLUG/PROJECT|Project Name]] — how this thought informs the project

## Related Thoughts

- [[Related Concept]] — why it relates

## References

- First captured from [[YYYY-MM-DD]] discussion
```

Never present someone else's idea as a free-floating concept. Omit `## Active Projects` when nothing matched.

## Step 5: Tie into active projects

From the project search, keep only projects whose frontmatter says `status: todo` or `doing`, excluding `projects/archive/`. Parse the frontmatter rather than grepping the file: decision trails contain stale `status:` lines. Interactively, list the matches and confirm; autonomously, link them all (a false link is cheap to remove; missed live work is not).

Link both ways: the `## Active Projects` entry above (use the full `projects/SLUG/PROJECT` path), and in each `PROJECT.md` a bullet under `## Related Captures` near the bottom of the body, created if missing:

```markdown
- [[YYYY-MM-DD]] — [[New Concept Note]] — one-line context
```

Never touch a project's frontmatter from this skill; status, assignee and next_action belong to project sessions and Chris.

## Step 6: Cross-link and report

When one source yields several notes, cross-link them under `## Related Thoughts` with a short reason each, and link related existing notes found in the search even if you did not merge.

Report: created or updated note, related notes, and active projects tied in (or "none").
