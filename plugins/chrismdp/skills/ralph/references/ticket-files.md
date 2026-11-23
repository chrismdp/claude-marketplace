# Ralph ticket-file queues

Read before inspecting, claiming, updating or writing a file-based ticket.

## Format

Tickets are markdown files in the first ticket folder that exists (`docs/tickets/`, `docs/changes/`, `doc/tickets/`, `doc/changes/`):

```markdown
---
status: todo
title: Add search box to skills dashboard
created: 2026-04-06
---

# What

One paragraph on what the user should see when this is done.

# Why

Optional context: the request or rationale.

# Acceptance

- Concrete, observable criteria that must hold before done
```

Statuses (aliases in brackets):

- `todo` (`draft`, `pending`): ready to pick up.
- `doing` (`in-progress`): claimed, possibly by an engineer who did not finish.
- `qa`: only where the project's `CLAUDE.md` or `RALPH.md` defines a sign-off gate. Merged, CI green, self-verified, awaiting a human's live check. Never pick one; only the human moves it to `done`, or back to `todo` on a failed check. If three or more pile up, flag it to Chris and keep pulling `todo` work.
- `done` (`shipped`, `complete`).
- `blocked`: agreed work waiting on something concrete from Chris (a credential, a console step, an external reply). Name the missing input so he can unblock it cold.
- `proposed`: an idea Chris has not agreed to build. Skip it. It becomes `todo` when he says yes, or is deleted when he says no.

Write canonical values in new files; keep a file's existing vocabulary when editing it.

## Writing tickets

A ticket describes the problem and leaves implementation to the engineer who picks it up against current code.

- State what is broken, missing or wrong, and why it matters, briefly.
- Bugs: repro steps, expected versus actual, and a loose pointer to where it likely lives.
- Features: acceptance as observable behaviour.
- Leave out diffs, exact signatures, full tests and step-by-step patches. If you know the fix that precisely, do the work instead.
- Defer what is better decided at build time (dependency versions, model choices, fast-moving SDK details). State direction and constraints; name important unknowns.

**File only honest statuses, and not your own ideas.** The `proposed` pile has no consumer, so it only grows. A defect you have confirmed in the code is `todo`. Something Chris asked for is `todo` (or `blocked`, naming what is missing). Raise an unapproved idea in the session instead of filing it. Reserve `proposed` for a genuine build-or-remove decision of Chris's with work waiting on it, and close proposals left unread for weeks as not-planned.
