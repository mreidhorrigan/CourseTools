> **CourseTools edition.** This file is part of a complete public adaptation of Matt Horrigan's Tooling Handbook. Examples have been mapped to the Canvas Automation Toolkit, and private machine paths and unavailable project references have been removed.

# Resilient agentic subprocesses

How a fan-out of AI subagents survives one of them dying (a rate limit, a crash, a timeout)
without losing the work the others already finished. The rule in one line: a subprocess's
progress is durable the moment it is made, not when the whole run returns.

This is build and R&D-time discipline. The shipped tool still runs AI-free
([01-principles.md](01-principles.md)). This keeps the AI that *builds* and *researches* a tool
from throwing away a session's work.

## The problem

A multi-agent research run fanned out six topic agents, each followed by a fact-check pass, then
a final synthesis that wrote the deliverable. Partway through, the model provider's session limit
hit. Six agents failed at once, and so did the synthesis. From the outside the whole run looked
lost: no report, no notes, hours of research apparently gone.

The compute was not actually lost. A journal still held every completed agent's output, and a
resume recovered them. What was lost was legibility and trust. Nothing intermediate had been
written to disk, and the only step that produced a visible artifact was the last one. Gate all
value on a final step and any failure of that step reads as total failure.

Two faults, both structural:

1. Results lived in memory until a final synthesis, so a late failure erased the *appearance* of
   all the earlier work.
2. A terminal error (the session limit) was handled like any other crash, when it actually just
   needed the run to pause and resume after the reset.

## The principle: progress is a write-ahead log, not a return value

Treat each subagent like a database transaction. It is not "done" when it returns a value to the
orchestrator. It is done when its output is on disk under a stable key. The orchestrator's
in-memory array of results is a cache. The files are the system of record.

Everything below follows from that.

## The practices

### 1. Every subagent persists its own progress

Each subagent writes an append-only record of what it started, what it produced, and how it
ended: one line or one file per event, keyed by a stable id (the dimension name, the item id),
appended the instant the event happens. Append-only, so a crash mid-write cannot corrupt the
entries already there. This log is two things at once: the audit trail of the run, and the source
you recover from. It is the `provenance.json` discipline ([05-git-and-artifacts.md](05-git-and-artifacts.md))
applied to agents.

### 2. Materialise each result as it lands

Do not hold all results for a final pass. The moment an agent returns, write
`research/partials/<id>.json` (or `.md`). A failure at step N then costs step N, not steps 1
through N minus 1. The synthesis reads the partials off disk, so it runs over whatever exists,
and you can assemble a partial report by hand even if the synthesis never runs.

### 3. Make the run resumable: a journal plus idempotency

Key every step by (step, inputs) and record its result in a run journal. On restart, a completed
step returns its cached result and only failed or changed steps re-run. Same inputs, same key,
skip. This is what durable-execution engines do (Temporal, AWS Step Functions, the "durable
workflow" runtimes), and it is what the an AI CLI Workflow tool does with `resumeFromRunId`: a
same-session resume replays the unchanged prefix from cache and re-runs only from the first failed
or edited call.

In the case study this is exactly what saved the work. The resumed run returned the finished
agents from cache in seconds and re-ran only the four that had failed, plus the synthesis.

### 4. Decouple the deliverable from the last step

Emit value continuously, not once at the end. The synthesis consumes the materialised partials,
so it is replaceable and re-runnable, and if it never runs the partials are still a usable result.
Never let a single terminal step be the only writer of value.

### 5. A dead subagent is a null, not a throw

Collect results with failure tolerated. One agent's rate limit must not abort the batch. Filter
the nulls, record which ids failed and why, then proceed with the survivors. Then say what was
dropped, out loud. Silence is not success, and a quietly-truncated run reads as a complete one.

### 6. Classify the error: terminal or transient

Not all failures want the same response.

- **Transient** (a timeout, a 5xx, a flaky fetch): retry with backoff.
- **Terminal for the window** (a session or quota limit): retrying now only burns more against a
  wall. Persist, stop, and schedule the resume for after the reset.

Encode the difference so the harness pauses on a limit instead of hammering it.

### 7. Budget and backpressure before the fan-out

Trip the limit less often in the first place. Cap concurrency, stagger launches, and check the
remaining budget before spawning. Prefer a pipeline (each item flows through every stage and
persists as it goes) over a barrier that holds the whole set until the end. An interruption then
leaves a partial set already on disk rather than nothing. Scale the width of a fan-out to the
budget, not to the task's theoretical maximum. Two concurrent fan-outs near a known limit is how
you re-hit it.

### 8. Make status observable

The run reports per-subagent state (queued, running, done, failed) to the screen and to the
journal. The trap in the case study was a finished-looking run whose value lived in one failed
final step. When you can see at a glance which agents survived, a limit hit is an inconvenience,
not a mystery.

## A minimal pattern

The shape, independent of language:

```
for id in work_items:
    if exists("partials/<id>.json"):        # idempotent: already done, skip
        continue
    append_journal(id, "start")
    result = run_subagent(id)               # may fail or return null
    if result is null:
        append_journal(id, "fail"); continue
    write("partials/<id>.json", result)     # materialise the instant it lands
    append_journal(id, "done")

synthesis = run_over(glob("partials/*.json"))   # reads disk, not memory
```

Re-running after any interruption is free for everything already in `partials/`. The journal tells
you what happened. The partials are the recovered work.

## How it composes

- **With [13-staged-pipelines-and-shared-config.md](13-staged-pipelines-and-shared-config.md).** A
  subagent fan-out is the AI analog of the stepwise driver. The `done_if` glob is the same
  idempotency check applied to `partials/<id>.json`, and "stop after any step, run the next" is the
  same re-entrancy. Run an AI fan-out the way you run a staged pipeline.
- **With [05-git-and-artifacts.md](05-git-and-artifacts.md).** The per-subagent log and the
  partials are provenance for R&D. Commit them so the next session does not re-pay for research
  that already completed.
- **With [01-principles.md](01-principles.md).** This serves the prime directive from the other
  side. The shipped tool stays AI-free; this discipline keeps the AI that builds it from wasting
  work.

The Definition of Done in [checklist.md](checklist.md) carries the line this chapter earns: a
fanned-out R&D run is resumable, and no subagent's result lives only in memory.
