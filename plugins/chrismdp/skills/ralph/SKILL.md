---
name: ralph
description: "Autonomous relay for code work, one ticket per loop: picks the next ticket, gets it done and verified, marks it, moves on. Queues: ticket folders (docs/tickets/, docs/changes/, doc/changes/, doc/tickets/), GitHub issues (a `.ralph` file with `queue: github-issues`), or a project session whose project has `code_repo`. Playbook for the project 'Today - Track and Improve LCARS'. Also loaded for authoring tickets. Triggers on /ralph, ticket writing in qualifying repos, and project sessions whose playbook is /ralph."
argument-hint: "[optional change-file slug]"
---

# Ralph

You are one engineer in a relay: take the next ticket, finish it, mark it, exit. **One ticket per run.**

## Which mechanics apply

- **You are a project session** (no shell; your tools include `dispatch_worker` and `land_worker`): read `@playbook/ralph/references/project-session.md` with `today_read` and follow it instead of the engineer steps below. You coordinate; the worker is the engineer.
- **A `.ralph` file with `queue: github-issues`**: read `references/github-issues.md` (and `references/ticket-files.md` when authoring an issue).
- **A ticket folder** (`docs/tickets/`, `docs/changes/`, `doc/tickets/`, `doc/changes/`): read `references/ticket-files.md`. Also read it before writing any ticket.

The reference owns formats and state transitions. A project `RALPH.md` or `AGENTS.md` overrides this skill.

## What belongs in the queue

Ralph is for repo-internal code changes that can land on main without Chris reviewing first: the answer to "would Chris be surprised if I shipped this without asking?" is no. Keep these out (use a vault project instead): client-facing or publishable output; strategic or cross-cutting work needing his judgement; changes spanning several repos; non-trivial changes to production with no rollback (prefer a PR he reviews).

`/delegate` owns the surface rule (who sees the output, copy is not a blocker, the artboard as entry condition). Inside a Ralph pass:

- A ticket with no human-visible surface whose acceptance you can prove from here is yours: build, verify, close on green. Never park it in `qa`.
- A ticket that needs a layout or UX decision Chris has not made, with no artboard, is not autonomous work; a change he has already decided is. Skip it; if most of the queue is like that, say so in one line. Do not build it and leave it in `qa`.
- Wording never parks a ticket or stops you to ask. List the strings you composed in the closing note.

## On start

1. If no queue exists, exit with one line.
2. Check CI on the branch (see **CI** below). A running build: wait for it. A red build: fixing it is this run's task.
3. Sweep spent delegation worktrees with `~/.claude/skills/delegate/scripts/sweep_worktrees.sh` (dry run, then `--yes`), under `/delegate`'s ownership rules. Do it now, while nothing of this session is live.
4. A `doing` ticket comes first (see **Recovery**).
5. Otherwise read every `todo` ticket; skip `blocked`, `proposed` and `qa`, and anything whose named dependency is not `done`. Apply **Decision precedence**, then pick the ticket that best unblocks downstream work and fits one run (alphabetical order only breaks ties). State the pick and a one-line reason before claiming.
6. An argument is a slug hint: pick that ticket if it is `todo` or `doing`.
7. Nothing pickable and CI green: print `No todo changes — nothing to do.` and exit.

## Decision precedence

A ticket records a decision at the time it was written. Before implementing, search the queue for later tickets, dated notes and QA outcomes on the same surface. Order: **Chris's current instruction > the newest explicit dated decision or ticket > older ticket prose.** A later ticket can supersede an older one whatever its status. If you cannot order a conflict confidently, ask (interactive) or block with a question (autonomous).

Whenever you edit a ticket, make its status describe its state now, in the same edit; never append a result that contradicts the status.

## Recovery (a `doing` ticket exists)

Do not assume the previous engineer got it right. Read the ticket's notes, the diff and the affected tests, then finish, fix or mark done as the evidence shows. If you cannot tell what the previous engineer intended, add a `## Notes` section explaining what you found, set `blocked`, commit, exit.

## Do the work

Claim the ticket (`todo` → `doing`) without a separate commit; the flip lands with the implementation.

Load `/delegate` before dispatching any worker. It owns routing, briefing, isolation, landing and verification. The worker's brief is the ticket itself (the file, or `gh issue view N --comments`); never write a parallel plan.md. You stay engineer of record.

Follow the repo's testing rules and the global testing rule: a failing test first for business logic; view-only changes need none. Fix the bug you were given, without restructuring around it. Note unrelated issues in `## Notes` or a new `todo` ticket rather than fixing them here.

Build the whole ticket in one run. Do not split for context size and do not propose a design doc first; a dozen files or a new subsystem is still one ticket. Split only when even that is impossible: write a ticket per part, mark the original `done` with a note, and exit.

## Verify

Every check the project defines must be green; never `--no-verify` or skip type checks. For UI changes, also check visually where you can (dev server and a browser screenshot).

**Security boundaries** (migrations and schema, RLS, auth, access policies, SECURITY DEFINER, membership or permission logic): run the four-boundary check and any repo security gate locally before marking done. Every new `public`-schema table gets RLS enabled and a policy (or anon and authenticated revoked). Postgres leaves RLS off by default, so a table with no RLS statement is exposed; never copy an RLS-off line from an older migration.

## Mark done

Set `status: done` and add `completed: YYYY-MM-DD`; a terse `## Notes` is optional.

Where the project defines a `qa` gate (its `CLAUDE.md` or `RALPH.md` says so), a slice with a user-observable surface ends at `qa`, with `completed:` and a `## QA` section of cold steps (do X, expect Y). Only the human moves `qa` to `done`. Purely internal slices, and slices whose only visible change is wording, go straight to `done`. `qa` is for a surface the agent cannot drive and did not build interactively.

## Commit, push, watch

One commit holds the implementation and the status flip:

```
<ticket title>

Closes <ticket path, e.g. doc/tickets/add-search.md>.

<one or two sentences on what changed and why>
```

Push (set upstream with `-u` if needed). If a hook fails, fix it and make a new commit; never `--amend` or `--no-verify`.

## CI

Before claiming, the branch's latest run must be green. After every push, watch your run to completion and never exit on red; a red build is most often a partial commit, so check `git status` first. Two failed fixes: set `blocked` with notes. Commands, doc-only pushes and release order: `references/ci-workflow.md`.

## When you need to ask

Ask when acceptance is unclear, Chris has a real decision to make, or you would be inventing product behaviour. Wording is not product behaviour.

- **Interactive** (Chris's prompt is in this turn): ask and wait; leave the ticket `doing`.
- **Autonomous** (`ralph.sh`, a project session, cron, no fresh user message): add a `## Questions` section Chris can answer cold, set `blocked`, commit the ticket alone, exit. If unsure which mode you are in, write to the file.

When stuck for any other reason (unfixable tests, repeated permission errors), do the same with `## Notes`.

## Bundled runner

`ralph.sh` runs one engineer session per ticket; see `~/.claude/skills/ralph/ralph.sh --help`.
