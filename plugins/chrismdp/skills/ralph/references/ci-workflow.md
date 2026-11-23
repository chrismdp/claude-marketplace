# CI workflow

## Before claiming

```bash
gh run list --branch "$(git branch --show-current)" --limit 1 \
  --json status,conclusion,databaseId,name
```

- **`success`**: pick the next ticket.
- **`in_progress` or `queued`**: wait with `gh run watch <id> --exit-status`. Never start a ticket on an untested base.
- **`failure` or `cancelled`**: fixing it is this run's task. Read `gh run view <id> --log-failed`, fix, run the failing check locally, commit, push, and watch the new run to green. Never claim new work while CI is red or a fix is in flight. After two failed attempts, set the relevant ticket `blocked` with a note for Chris.
- **No runs at all**: if the repo has no CI configured (no `.github/workflows/`, no deploy config), local verification is the bar; proceed. If it has workflows but no run appears, CI has not passed (a workflow file GitHub cannot parse runs nothing), so find out why before claiming.

## After every push

```bash
RUN_ID=$(gh run list --branch "$(git branch --show-current)" \
  --limit 1 --json databaseId --jq '.[0].databaseId')
gh run watch "$RUN_ID" --exit-status
```

**A doc-only push may trigger no run.** Repos often `paths-ignore` docs and markdown, so a commit touching only a ticket file starts nothing. Confirm it reached the remote with `git ls-remote origin <branch>` and exit rather than waiting.

**On red:**

1. Run `git status` first. A dirty tree usually means the commit was partial, and `git diff origin/main` may be exactly what CI is missing. If so, commit it, push, re-watch.
2. Otherwise read `gh run view "$RUN_ID" --log-failed`, fix locally, and run the same command CI ran before trusting the fix.
3. Commit as a new commit (no `--amend`). Before pushing, the tree must be clean; decide whether any remaining work belongs in this commit.
4. Push and watch again.
5. If you cannot fix it this run, add `## Notes` to the ticket, set `blocked`, commit, push, exit. Never leave a red build unexplained.

If `gh run watch` misbehaves, poll `gh run view "$RUN_ID" --json status,conclusion` with a bound of about 20 minutes; a typical change taking longer means something Chris needs to see.

## Cross-repo releases

When one repo depends on another's tagged release, follow the order in the repo's `CLAUDE.md` (usually: tag and release the dependency, wait for its release workflow, then push the dependent). Watch both runs, and do not push the second until the first is green.
