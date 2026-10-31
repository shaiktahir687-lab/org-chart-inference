# AI-assisted development loop

This take-home is intentionally designed so AI can accelerate iteration without being trusted as the source of truth.

## Workflow used for this version

1. **Use an LLM for design exploration:** brainstorm title variants, likely hierarchy patterns, edge cases, and evaluation metrics. Keep the generated logic in ordinary Python so reviewers can inspect it.
2. **Make every hypothesis testable:** generate known reporting lines alongside the flat profiles, but keep the labels in a separate file. Add small unit tests for known title/hierarchy cases.
3. **Ask AI for focused code review:** review title-parser gaps, ambiguous roles, missing department behavior, and potential ways the algorithm could leak labels. Apply only changes that can be verified.
4. **Use the benchmark as the gate:** run the same company-level validation/test split after changes. Do not accept a model or prompt change simply because its explanation sounds plausible.
5. **Inspect false positives:** use `reports/test_false_positive_audit.csv` to review accepted edges that disagree with the generated truth. If a pattern repeats, add a test or update the feature/scoring logic and rerun the full evaluation.
6. **Keep an abstention path:** an LLM may suggest a normalized title or candidate relation, but should not force a manager edge when evidence is weak or multiple candidates are similarly plausible.

## Example prompts for the next iteration

**Title normalization review**

> Review the title strings in this synthetic dataset and propose a structured schema for function, seniority, management scope, and team hint. Do not infer reporting lines. Return ambiguous examples separately, and avoid mapping unknown titles to a confident category.

**False-positive review**

> Inspect this sampled set of false-positive manager edges and group them by failure mode. For each group, suggest a minimal feature or test that could reduce the error without using the ground-truth manager field at inference time. Do not change code yet.

**Regression-test generation**

> Given the current parser and these failing title cases, propose unit tests that capture the intended behavior. Include abbreviations, missing fields, and ambiguous job titles. Do not weaken existing tests to make the new tests pass.

## Runtime trade-off

The submitted baseline does not call an external LLM for every employee. At this dataset size, per-record calls would add cost, latency, and nondeterminism. A future version could use a cached LLM step for previously unseen or ambiguous title normalization, record the model/prompt version, and evaluate any resulting gain against the same held-out labels. The graph-edge decision would still be governed by evidence and evaluation rather than generated prose.
