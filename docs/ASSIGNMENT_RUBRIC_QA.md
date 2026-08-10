# Assignment and rubric boundary testing with Mistral

This toolkit includes a Mistral-based harness for finding underspecified assignment instructions, ambiguous rubric criteria, and gaps between instructions and grading. Mistral receives assignment instructions without the rubric and produces several simulated submissions from configurable student profiles. It then grades each simulation from the rubric and audits the resulting interpretation and grading evidence.

The method deliberately uses a lower-capability model as a boundary tester. A plausible misunderstanding can reveal prose that depends on instructor assumptions. Model behavior cannot predict an individual student, and a successful simulation cannot establish that instructions are accessible or complete.

## Run on macOS

1. Copy assignment instructions and a rubric into a private local working location. Text and Markdown work directly; export other formats to text first.
2. Edit `commands/test-assignment-rubric.config.jsonc`. Set `instructions_file`, `rubric_file`, and `expected_requirements`. Optional context files should contain only material students are expected to use.
3. Double-click `commands/test-assignment-rubric.command` and paste a Mistral API key at the hidden prompt. The key remains in process memory and is not stored.
4. Review `qa-report.md` under `out/assignment-rubric-qa/`. Prioritize ambiguities and grading differences that recur across trials.
5. Revise the authoritative assignment and rubric sources, rerun the harness, and complete human review.

For CLI operation, set `MISTRAL_API_KEY` only in the command process and run:

```sh
MISTRAL_API_KEY='…' .venv/bin/python scripts/mistral_assignment_qa.py \
  --config commands/test-assignment-rubric.config.jsonc
```

Shell history can retain inline values. A safer interactive CLI invocation omits the variable and lets the script request hidden input.

## Interpreting results

- `qa-results.json` preserves structured results for comparison or later analysis.
- `qa-report.md` presents simulated work, rubric grading, and specificity findings.
- `provenance.json` records model, source hashes, and configuration hash without recording the API key.
- Fixed seeds improve repeatability, although hosted model aliases and provider updates can change output.
- Free-tier rate limits can interrupt batches. The harness honors `Retry-After` when supplied and otherwise uses bounded exponential backoff configured by `retry_attempts` and `retry_base_seconds`.
- Simulated grades are diagnostic. Never use them as grades for students.

Run multiple profiles because each one probes a different failure mode. Add expected requirements that matter to the instructor even when the prose is currently unclear; the audit uses these to identify missing or weakly stated requirements.

## Data safety

Mistral API calls send every configured source to an external service. Use assignment instructions, rubrics, public examples, or invented test submissions. Do not send identifiable student work, grades, accommodation information, unpublished answer keys, confidential sources, or unrestricted Canvas exports. Generated reports remain under gitignored `out/` and are excluded from collaborator distributions.

The default endpoint and JSON mode follow Mistral’s official [Chat Completions API](https://docs.mistral.ai/api) and [structured-output documentation](https://docs.mistral.ai/studio-api/conversations/structured-output). Check institutional privacy requirements and Mistral’s current terms before sending course material.
