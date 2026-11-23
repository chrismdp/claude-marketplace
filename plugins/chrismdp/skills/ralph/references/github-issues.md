# Ralph GitHub issues mode

For a repo whose `.ralph` file contains `queue: github-issues`. Apply these translations wherever the main skill refers to a ticket file, status or notes. An open issue with no workflow label is `todo`.

| File mode | GitHub mode |
|---|---|
| `status: todo` | open issue, no workflow label |
| `status: doing` | open + `doing` label |
| `status: qa` | open + `qa` label |
| `status: blocked` | open + `blocked` label |
| `status: proposed` | open + `proposed` label |
| `status: done` | closed as completed |
| `status: superseded` | closed as not-planned, `superseded` label |

- Claim: `gh issue edit N --add-label doing`, then comment with the selection reason.
- `## Notes` or `## Questions`: an issue comment.
- Scan: `gh issue list --state open --json number,title,labels`; skip `qa`, `blocked`, `proposed`; an open `doing` issue is the recovery case.
- Precedence search: `gh issue list --state open --search '<terms>'`; open closed issues only to trace what shipped.
- File a ticket: `gh issue create` with the body described in `ticket-files.md`; `-l proposed` only for its narrow use.

## Behaviour specific to issues

- **Pass every body with `--body-file`, never an inline `--body`.** A double-quoted `--body` executes backticks, so quoted code silently vanishes while `gh` reports success. Write the body to a scratchpad file with a quoted heredoc (`<<'EOF'`). Repair with `gh issue comment --edit-last --body-file`.
- **Comment as you go**: a claim comment, decisions and gotchas as they happen, and a completion comment naming what you verified (tests or commands) and the commit SHA.
- **Commits reference the issue**: `Closes #N` when the commit completes the work, then drop the `doing` label after pushing. `Refs #N` when the slice ends at `qa` or the commit is partial.
- **At the qa gate**: swap `doing` for `qa`, post the `## QA` steps as a comment, leave it open, commit with `Refs #N`. Only the human closes a `qa` issue or reopens it as todo.
- **When blocked**: swap the label to `blocked` and comment with the exact missing input. No separate ticket commit.
