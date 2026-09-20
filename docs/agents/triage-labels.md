# Triage Labels

The skills speak in terms of five canonical triage roles. In this repo a "label" is a bare jn tag on the `@todo` entry (`jn tag N @ready-for-agent -@needs-triage`).

| Label in mattpocock/skills | Tag in jn           | Meaning                                  |
| -------------------------- | ------------------- | ---------------------------------------- |
| `needs-triage`             | `@needs-triage`     | Maintainer needs to evaluate this issue  |
| `needs-info`               | `@needs-info`       | Waiting on reporter for more information |
| `ready-for-agent`          | `@ready-for-agent`  | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `@ready-for-human`  | Requires human implementation            |
| `wontfix`                  | `@wontfix`          | Will not be actioned; also add `@done`   |

When a skill mentions a role, apply the corresponding tag and remove the previous triage tag. Query the queue with `jn ls @todo @needs-triage`.
