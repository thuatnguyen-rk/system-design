# System design lab

Personal lab: learn system design and patterns by writing a design and running something measurable.

SRE lens — SLOs, failure modes, blast radius, observability, deploy/rollback, capacity/cost. Not an interview dump. Primitives first; composed systems later.

Markdown in this repo is English.

## Layout

| Path | Role |
| --- | --- |
| [catalog.md](catalog.md) | Learning order. The only numbering. |
| [_template/](_template/) | Copy this when starting a topic. |
| [primitives/](primitives/) | Building blocks (cache, queues, load balancing, …). |
| [patterns/](patterns/) | Operational and architectural patterns. |
| [systems/](systems/) | Designs composed from primitives. Start these later. |
| [code-patterns/](code-patterns/) | GoF-style code patterns. Separate track. |
| [shared/](shared/) | Reusable Compose fragments and diagrams. |

Each topic:

```
design.md     # you write this
notes.md      # scratch; durable conclusions move into design.md
lab/          # Docker Compose
diagrams/
```

Add `azure/` only when Compose cannot prove the point. Resource group `system-design` only.

## Start a topic

Work one topic at a time. Do not pre-create every catalog row.

1. Copy `_template/` to `primitives/<slug>/` (or `patterns/`, `systems/`, `code-patterns/`).
2. Set `name:` in `lab/compose.yaml` to the slug.
3. Link the folder from `catalog.md` and mark it in progress.
4. Fill `design.md` as you work. Do not pre-write the answer.
5. Publish lab ports on `127.0.0.1`. One Compose project per topic. `docker compose down -v` when done.
