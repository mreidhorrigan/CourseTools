> **CourseTools edition.** This file is part of a complete public adaptation of Matt Horrigan's Tooling Handbook. Examples have been mapped to the Canvas Automation Toolkit, and private machine paths and unavailable project references have been removed.

# MCP tools that survive weak models

How to design and harden an MCP server's tools so a weak or free tool-calling model
(a local Ollama model, or a free-tier cloud model reached through a bridge) can drive it
reliably, and what to do when it still can't. This extends
[07-mcp-and-apis.md](07-mcp-and-apis.md): that chapter says when to add an MCP for
drive-time work. This one covers what happens once the driver is not a frontier model.

## The problem

CANVAS_AUTOMATION carries `canvas-mcp`, a custom MCP server exposing
composition tools (`render_als`, `render_progression`, and others) that take deeply
nested JSON specs. It had been driven successfully by Claude. The test was whether
Mistral's devstral, reached free through a LiteLLM bridge, could drive it too.

The first attempt was not a composition failure. It was a tool-calling failure, and not
even on the custom MCP: asked to read two files with an AI CLI's built-in `Read` tool,
devstral emitted one tool call whose argument string was two JSON objects concatenated
together, `{"file_path": "a.md"}{"file_path": "b.md"}`. That fails to parse. an AI CLI
returned a clear `InputValidationError` naming the exact problem. Devstral then repeated
the identical malformed call, byte for byte, in response to that error. Not a retry with a
correction: the same broken string, again and again, 176 times before the run was killed.

The same quirk reappeared twice more once the custom MCP was wired in and driven with
multi-call tasks, each time as two tool calls' arguments concatenated into one. But this
time devstral corrected itself on the very next attempt, without any change to the
interface or the prompt. Same failure, same model, same session shape: once it looped for
176 turns, twice it self-corrected after one.

That inconsistency is the finding. The failure mode is a stable property of the model's
decoding, not of a specific tool or a specific prompt. Whether it resolves gracefully is
not stable at all. A fix that only makes correction *more likely* (a clearer error, a
better example) is worth having, but it cannot be the only fix, because sometimes the
model will not correct itself no matter how clear the error is.

## The principle

Treat a weak model's tool-calling failures as a decoding problem the interface has to
absorb, not a reasoning problem you can prompt away. That means two layers, not one:

1. **Make the interface hard to call wrong and easy to self-correct from.** Validate
   early, name the exact location of a mistake, and show a working example to copy. This
   raises the odds of the graceful case.
2. **Assume the graceful case will not always happen, and add a backstop that does not
   depend on the model noticing its own mistake.** A circuit breaker outside the model's
   control, at the tool-call layer.

Layer one helps often. Layer two is what makes the difference between a one-turn
correction and a run that grinds for 176 identical calls before someone kills it by hand.

## The practices

### 1. Validate at the top, and name the exact location

A weak model fixing a large nested spec needs a path to the one bad field, not a bare
exception three calls deep. `canvas_automation.core.spec.score_from_spec` walks
tracks, clips, and notes, and wraps any failure with the exact location:
`track[0] ("bass") > clip[0] ("intro") > note[1]: note is missing required field
"start"`. The model can act on that in one turn. A raw `KeyError: 'start'` with no path
back to which of nine notes caused it cannot.

### 2. Reject a guessed default; make conflicting fields an error

`resolve_pitch` originally accepted a note that gave more than one pitch spec (`key` and
`ratio` together) and silently preferred one by precedence order. That is a trap for a
model that pastes and half-edits a note: the wrong field wins with no signal that
anything was wrong. It now rejects any note giving more than one of
`key` / `ratio` / `edo` / `frequency`, by name, in the error. Silent precedence hides a
mistake from a model that does not reason well about defaults; an explicit rejection
teaches it in one turn.

### 3. Flag a likely-unintended result in the tool's own output, not just in prose

A call can succeed, return an accurate summary, and still be silently wrong against what
the user actually asked for. Asked to write a dense just-intonation piece, devstral hand
built a multi-track `render_als` call using plain `key` integers for every one of 156
notes. That is valid input; the tool rendered it correctly. But plain `key` with no
`ratio` / `edo` / `frequency` / nonzero `cents` is exactly 12-TET, no tuning at all, and
the result already said so in a field the model never checked: `"tuned_notes": 0`.
Devstral told the user the tuning was applied anyway.

The fix was not a better prompt. It was making the tool's own return value say the
quiet part out loud: whenever a render has zero tuned notes, the result now carries a
`tuning_warning` field spelling out the mismatch and instructing the model not to report
tuning as applied unless `tuned_notes` is greater than 0, and the docstring states the
plain-key-means-12-TET fact up front rather than leaving it to be inferred from the
schema. Re-tested with the same kind of request: the model built real just-intonation
notes and reported a tuned-note count that matched the file exactly. A model can be
trusted to read a field placed in front of it far more than to think to go look for one.

The general form: if a tool can succeed while missing the point of the request in a way
you can detect programmatically, detect it and say so in the result, not only in
documentation the model reads once before deciding what to build.

**Caveat, found the same day on a second, unrelated field:** a warning in the result is
necessary but not sufficient. Asked, generically, to compose a drum pattern in a
particular meter and explain how the meter was represented, devstral produced a clip
whose declared length (a field it set itself) disagreed with where its own notes actually
ended by a factor of three, and separately used plain `key` throughout a percussion part.
The tool's result carried both a `length_warning` and a `tuning_warning`, worded plainly,
present verbatim in what the model received. Its answer to the user repeated the original,
wrong numbers and did not mention either warning. The same class of prompt that included
an explicit instruction to check a field ("report the tuned_notes count") got the model to
read and act on it every time; a generic prompt with no such instruction got it ignored
every time, even with two separate warnings present at once. A result field changes what a
model *could* notice. It does not make a weak model go looking. Where the stakes justify
it, pair the field with an explicit ask to check it, in the calling prompt or the system
prompt, on top of putting it in the result. Neither layer alone was enough here.

### 4. Put one small, complete example directly in the docstring

`render_als`'s docstring now carries a minimal two-note, one-track, one-clip example
next to the abstract schema. A weak model edits a working example far more reliably than
it assembles a nested structure from prose alone: extending a shape that already works is
a smaller edit than constructing one from a description, and a smaller edit is a smaller
surface for a malformed-JSON slip.

### 5. Tell the model what to do with an error, not just what the error is

The same docstring adds one line: if the call errors, fix the one field named and resend
the whole spec, don't repeat the call unchanged. Treat this as a nudge, not a guarantee.
Separate research into system-prompt-level retry-limiting found weak, inconsistent
evidence that a weak model reliably follows a "stop after N attempts" instruction. Devstral
proved that here directly: it had the exact error in front of it and repeated the identical
broken call anyway. Write the instruction because it costs nothing and helps sometimes.
Do not build the actual safety net out of it.

### 6. Expect the same failure on any tool, not just the one you are hardening

The concatenated-JSON quirk hit an AI CLI's built-in `Read` tool first, then the custom
MCP twice. It is a property of the model's tool-calling, not of one server's schema. Don't
spend the harden-the-docstring effort once per tool and call it solved; assume it can
recur anywhere a weak model can make two tool calls in a row.

### 7. Add a tool-agnostic circuit breaker, outside the model's control

Because layer one only raises the odds, add a backstop that trips independent of whether
the model would have corrected itself: a `PreToolUse` hook that hashes each tool call
(name plus arguments), and blocks the third identical repeat within a short window, plus a
per-tool hard cap for loops that vary the input but still never terminate. This also
catches identical *malformed* calls, since the host still constructs a tool-call record
with the raw unparsed string when JSON fails to parse, so a byte-identical broken retry
hashes the same as a byte-identical valid one. `writing-experiments/claude-model-toolkit/
hooks/repeated-call-circuit-breaker.py` is wired into every profile's sandbox by default,
matching every tool (`"matcher": "*"`), not just one server's tools.

### 8. Pair one complex tool with several small ones

`canvas-mcp` exposes `describe_pitch` and `preview_scale` alongside the far more
complex `render_als`. A model can resolve one pitch or preview one scale to sanity-check a
piece before attempting the large nested call that assembles many of them. Smaller calls
fail less often, and a failure in a small call is a smaller thing to retry correctly.

### 9. Test against the model you intend to support, not against your own reading of the schema

A schema and a docstring that read clearly to a person may still be the shape a small
model serializes wrong. The only way to find that out is to drive the actual tool with the
actual model and read the transcript: which tool, how many calls, what the arguments
actually were, byte for byte. Every practice above came from doing exactly that, not from
reasoning about the schema in the abstract.

## A minimal pattern

The hook, independent of language:

```
on PreToolUse(session_id, tool_name, tool_input):
    sig = hash(tool_name, canonical_json(tool_input))
    history = load_state(session_id, tool_name)   # last N call signatures, plus a total
    if history.count(sig) >= 2:                   # this would be the 3rd identical call
        deny("this exact call is looping; stop and report instead of retrying")
    if history.total > HARD_CAP:
        deny("too many calls to this tool this session; stop and report")
    append(history, sig); save_state(session_id, tool_name, history)
    allow()
```

State is per (session, tool), so one looping tool cannot exhaust the budget of another,
and a fresh session starts with a clean slate.

## How it composes

- **With [07-mcp-and-apis.md](07-mcp-and-apis.md).** That chapter decides whether an MCP
  belongs in the project at all. This one hardens it once it is there and the driver may
  not be a frontier model.
- **With [14-resilient-agentic-subprocesses.md](14-resilient-agentic-subprocesses.md).**
  Same spirit at a different layer: don't gate all value on a step that might not
  self-correct, and don't let a single failure mode read as total failure. There it is a
  fan-out of subagents; here it is a single tool call.
- **With [01-principles.md](01-principles.md).** The MCP is still a drive-time
  convenience, not a runtime dependency of the shipped tool. Hardening it for a weak
  driver is R&D-time work, done so the AI that drives the tool doesn't waste a session
  grinding on a call it will never get right unassisted.

The Definition of Done in [checklist.md](checklist.md) gets one more line from this
chapter: if an MCP is meant to be driven by anything less than a frontier model, its
tools name the exact location of a bad field, and a circuit breaker sits in front of them
that does not depend on the model noticing its own mistake.
