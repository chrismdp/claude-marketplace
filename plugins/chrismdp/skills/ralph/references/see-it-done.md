# Ralph on a See It Done project

Read this before you pick, claim, write or tick a ticket in a See It Done project whose playbook is Ralph.

## Where the queue lives

The queue is the open tasks of that one project, read and changed through the See It Done connector (`read` with `what: "tasks"` and the `projectId`, `add_task`, `update_task`). The project's notes hold specs. Nothing about the queue lives in the repository.

- **A ticket** is an open task with no one assigned to it. A task assigned to the person is theirs to do: never build it, tick it or reassign it.
- **The spec** is the task's title, plus a note of the same subject when the title is not enough (`html-notes.md` for "Build HTML notes…"). Read every note in the project before picking, since a later note can overrule an older ticket (see **Decision precedence** in the skill).
- **Order** is the task list's order. Take the first ticket whose dependencies are met, unless another ticket unblocks more downstream work. Say which one you picked and why in one line.
- **Tickets carry no start date.** A start date would put the project in See It Done's work queue, and the scheduled worker there has no shell, so it cannot build anything.

## States

A task is only open or done, so the states of a ticket file map like this:

| Ticket file | See It Done |
|---|---|
| `todo` | open, nobody assigned |
| `doing` | open, with a dated line in the project's trail saying it was claimed and on which branch |
| `blocked` | open, with a decision raised for the person on that project, saying what is needed |
| `qa` | open, assigned to the person, with the cold steps to try in a note |
| `done` | ticked |

Tick a ticket only when its change is live and has been read back on the real account, not when the code is merged. The trail entry that ticks it names the commit.

## Who works it

Building needs the repository, a shell and the test lock. So this queue is worked by a Claude Code session with the repository checked out and the See It Done connector, following the rest of this skill and `/delegate`. A session with only connector tools (the scheduled See It Done worker, a phone chat) can read the queue, write a spec note or add a ticket. It does not claim one.

## Writing a ticket

Add one task, titled as the action that finishes it ("Build HTML notes shown in a sealed frame"). If it needs more than the title, write a note in the same project with **What**, **Why** and **Acceptance**, as in `ticket-files.md`. Leave out the start date and the assignee.
