# Project UI — user journeys (draft)

Design spike for the project-focused web UI (#54). The UI only reads and writes the jn graph; it does not talk to agents directly.

Context: many projects, each with epics or sub-components. Some are engineering projects, some are research (ideas, experiments, results, non-code artifacts). Agent swarms and humans microjournal into the same graph. Entries often reply to other entries or tickets. Triage uses the tags `@needs-triage`, `@ready-for-agent` and `@ready-for-human`; active work is tagged `@in-progress`.

Tenet constraint: none of the tags above become special. Triage states, sprint scope and research kinds come from config filters or views in `~/.jn`.

## Intake and triage

1. **File a ticket** (given). Create a `@needs-triage` entry under a project or epic in a few keystrokes, with an optional `#N` reference to the note or ticket that prompted it.
2. **Triage pass.** Go through `@needs-triage` for one project or for all of them. For each entry: move it to ready-for-agent, ready-for-human or won't-do; set the parent epic; add `@blocked_by`; leave a triage note as a reply. Retagging should work on several entries at once.
3. **Promote a note to a ticket.** A journal entry (an agent log line, a meeting note) surfaces a bug or idea. Create a ticket linked back to it without retyping the context.
4. **Meeting capture.** Log meeting notes against a project, then spin off action items as tickets that reference the note.

## Backlog

5. **Review a project backlog** (given). Open work grouped by epic, then by triage state. Show each item's age and when it last changed.
6. **Groom.** Move tasks to a different epic, split a ticket into subtasks, close duplicates with a reference to the survivor, and spot stale tickets that nobody has touched in N days.
7. **Project landing page.** Epics with done/total, counts by triage state, recent activity, and current blockers.

## Swarm sprint monitoring

8. **Sprint board** (given). For a project or epic, show done, in progress, ready and blocked. For each in-progress item, show which `@agent` session is working on it.
9. **Catch up since I last looked.** A feed of new entries on a project since a timestamp, covering decisions, assets, results and closures, with a read/unread position.
10. **Drill into an in-flight ticket.** The ticket's thread of replies and log entries in time order, its latest status, and its attached files.
11. **Find stuck work.** `@in-progress` items with no activity for N hours, and agent sessions that have gone quiet.
12. **Human queue.** `@ready-for-human` items across projects: what the agents have handed back to me.

## Dependencies

13. **Blocker map** (given). The `@blocked_by` graph for a project: what is blocked, by what, and how deep the chain goes.
14. **Impact check.** Before closing, deprioritizing or dropping something, see what depends on it and what would unblock if it closed.
15. **Cross-project blockers.** Work in one project that is waiting on another project.

## Research and knowledge

16. **Idea to result.** Follow an idea through its experiments to their results and the decision taken, as a thread or tree rather than a list of tasks.
17. **Compare experiments.** Put sibling result entries side by side, or at least one after another.
18. **Find a past decision or fact.** "Why did we pick X?": full-text search plus tags, across projects, landing on the entry and its thread.
19. **Asset index.** Every artifact (file, doc link, dataset) logged for a project or epic, with the entry that created it.

## Reporting

20. **Weekly status.** For a project over a date range: shipped work, decisions, results, and open risks or blockers, in a form I can copy or paste.
21. **Timeline.** Activity per day for a project, to see momentum or when it stalled.

## Navigation (applies to all of the above)

22. **Follow references.** `#N` links, parents, replies and back-references (what points at this entry), with a breadcrumb.
23. **Switch project or db quickly.** Jump between projects and between `[dbs]` without losing my place.

## Open questions

- **What does "mine" mean for a human?** `@agent` only identifies agents. Is there an `@owner` or assignee convention?
    - human generated tickets just don't have an @agent tag.
- **Sprint scope.** What defines a sprint: an epic, a tag (`@sprint=…`), or a date range?
    - usually a parent ticket
- **Research entry kinds.** Are `@decision`, `@result`, `@experiment` and `@asset` used today, or is free prose the norm? This decides whether journeys 16–19 can rely on tags or need text search.
    - @decision and @experiment (for launching an experiment) are in use. Tags can be relied on - we can always re-tag the database with a flash-lite agent.
- **Is "reply" just `@parent`?** Or does a reply sometimes use a `#N` reference in the text? The answer changes what a thread view has to follow.
    - I've seen @re=#1234 for a reply although that may not be canonical. agents do what they do.
- **Scale.** Thousands of entries per db: is that the size of one project or the whole db? This sets whether the landing page and catch-up feed need paging.
    - size of the whole db. a single project may have 4-30 open tickets. All projects in 1 db is an important feature for this design.


Other things:
- I might have ~8 active projects with half of them being worked on in a given day, so the cross-project component is important; these are focused around a single component.
- It's easy to build a giant clunky JIRA clone, elegence and simplicity and lack of friction are paramount to making something usable

## What the answers imply

- **"Mine" for a human is `-@agent`.** No new tag is needed.
- **A sprint is a parent ticket.** So the sprint board, the epic view and the project view are one screen: "this entry's subtree, grouped by state".
- **Research kinds are tags.** `@decision` and `@experiment` become filters in that same screen, not a separate research mode.
- **A reply is any pointer.** That covers `@parent`, `@re=#N` and a `#N` in the text. The thread view therefore follows *every* back-reference generically, with no reply tag hardcoded, which fits the tenets.
- **Scale.** A project is 4–30 open tickets, so per-project views render everything with no paging. The thousands of entries only matter for search and the cross-project home.
- **The state columns are an ordered tag list in config,** for example `states = ["@needs-triage", "@ready-for-agent", "@ready-for-human", "@in-progress", "@done"]`. None of those tags is special in code.

## Proposed shape: three screens

1. **Home (all projects).** One compact row per active project: state counts, last activity, and a stale marker. Above them sits the human queue (`@ready-for-human` plus `@needs-triage`). Covers 7, 9, 11, 12, 15, 21 and 23.
2. **Subtree.** Any entry as the root: a project, an epic or a sprint ticket. On the left, the tickets grouped by state, with blockers inline. On the right, the journal feed for the subtree, filterable by tag (`@decision`, `@experiment`). Covers 2, 5, 6, 8, 13, 16, 19 and 20.
3. **Entry.** The body, what it points to, and everything that points at it in time order (the thread). Covers 10, 14, 17 and 22.

Everywhere: one capture box (prefilled with the current root as `@parent`) and one search field. Covers 1, 3, 4 and 18.
