# Design notes

## Why conservative inference?

Org-chart inference is a graph prediction problem where false edges can be more damaging than missing edges. A wrong edge may mislead sales teams about economic buyers or reporting chains. The first version therefore separates candidate generation from edge acceptance and supports abstention.

## Data model

`employees.csv` contains observable profile fields only. `ground_truth.csv` stores labels separately and is read only by `evaluate.py`. The synthetic generator creates the two files in one deterministic process, which makes evaluation repeatable without leaking `manager_id` into inference.

## Candidate scoring

Candidates must be in the same company, have a higher inferred seniority, and share an inferred function. Scores rise when department labels agree, team hints extracted from title suffixes match, the seniority gap fits a direct-report relationship, and the candidate appears to occupy a plausible manager layer. C-suite and functional-head edges use explicit title-derived role relationships.

A score is not a probability. Two cutoffs are used:

- Minimum evidence score: prevents weak matches from becoming edges.
- Minimum margin over the second-best candidate: prevents a tie between plausible managers from being resolved arbitrarily.

The UI exposes both controls to make the precision/coverage trade-off visible.

## Validation design

Companies, not employees, are split into train/validation/test partitions so that employees from one synthetic company cannot leak across partitions. This initial heuristic has no fitted parameters, but the validation partition is used to choose the acceptance threshold. The test partition is held out for the final report.

## AI-native extension point

An LLM can help normalize unfamiliar or abbreviated titles into structured fields (function, seniority, management scope, team hints). That output should be cached and versioned, treated as a feature rather than ground truth, and evaluated against the same held-out labels. The graph layer should still apply candidate constraints, confidence checks, and abstention; a fluent LLM answer is not evidence that a reporting edge is correct.
