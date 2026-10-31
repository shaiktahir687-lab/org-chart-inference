# Org Chart Inference

## Live Demo

**Live Application:**
https://org-chart-inference-lkm4i4h7shomnv9yxnutcu.streamlit.app/

**GitHub Repository:**
https://github.com/shaiktahir687-lab/org-chart-inference 

A small, reproducible org-chart inference platform built around one principle: **an unsupported reporting line is worse than an unresolved employee**.

The project includes a synthetic benchmark (500 companies, at least 100 employees per company), a conservative inference engine, a held-out company-level evaluation, and a Streamlit app for exploring the inferred hierarchy.

## What is in the repository?

- `app.py` — Streamlit explorer with company search, department views, confidence/margin controls, inferred reporting lines, and an unresolved queue.
- `generate_data.py` — deterministic generator for company and employee profiles plus a separate ground-truth manager table.
- `inference.py` — inference features and pair scoring. It reads only the flat employee profiles; it never reads `ground_truth.csv`.
- `evaluate.py` — confidence-threshold sweep, company-level holdout, precision/recall/coverage, and false-positive audit file.
- `build.py` — one command to regenerate the dataset, rebuild candidate edges, and run evaluation.
- `data/employees.csv` — flat input profiles; no manager IDs.
- `data/ground_truth.csv` — synthetic labels for evaluation only; not used by the app/inference code.
- `data/inferred_edges.csv` — precomputed proposal scores so the hosted app starts quickly.
- `reports/` — validation threshold sweep and test evaluation output.

## Run locally

Python 3.10+ is recommended.

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

The app opens in your browser. Choose a company, adjust the confidence and candidate-margin thresholds, explore the hierarchy, inspect proposed lines, and download a company's inferred reporting lines as CSV.

## Rebuild everything

```bash
python build.py
```

By default, this generates 500 companies with 100–180 employees each. To generate a larger benchmark:

```bash
python build.py --companies 600 --min-employees 100 --max-employees 220 --seed 20261029
```

To keep the existing flat profiles and just refresh inference/evaluation:

```bash
python build.py --skip-generate
```

## Deploy on Streamlit Community Cloud

1. Open [Streamlit Community Cloud](https://share.streamlit.io/) and sign in with your GitHub account.
2. Create a new app and select the repository, branch, and `app.py` as the entry point.
3. Keep `requirements.txt` in the repository root. The precomputed `data/inferred_edges.csv` lets the app load without running inference on startup.
4. After deployment, open the public app URL in a private/incognito window and test several companies, department filtering, thresholds, and downloads.

If the dataset size becomes a problem for repository hosting, move generated data to object storage and load it from a configured URL; keep synthetic ground truth out of the app's runtime path.

## Inference approach

1. **Normalize features:** infer a function from titles first, then use department aliases when the title is too generic. Parse a coarse seniority level and any team hint embedded in the title suffix.
2. **Generate candidates:** only consider higher-seniority people in the same company and inferred function. C-suite roles can attach to a unique CEO; function heads can attach to an expected executive sponsor.
3. **Score evidence:** combine function agreement, department agreement, team-title agreement, title seniority gap, and whether the candidate plausibly sits on the next management layer.
4. **Abstain on ambiguity:** emit a line only if the score clears a threshold and is sufficiently higher than the second-best candidate. Otherwise leave the manager unresolved.
5. **Preserve traceability:** each proposed line carries the evidence score, gap to the runner-up, and a readable explanation. The UI allows the reviewer to raise or lower thresholds.

The displayed score is an **evidence score**, not a calibrated probability. The validation sweep chooses a threshold using company-level validation data, targeting at least 95% validation precision before maximizing edge coverage. The test-company result is reported separately and is not used to select the threshold.

## How the synthetic data is designed

- 500 unique synthetic companies across 14 industries and 7 regions; this fixed seed produced 69,293 employees, with at least 100 at every company.
- CEO and executive roles, functional heads, team managers, team leads, and individual contributors.
- Ten functions, varied job-title conventions, abbreviations, inconsistent department labels, missing titles/departments, and occasional noisy department values.
- Team labels are available only as part of job-title text (not as a clean feature column), so matching requires extracting them from titles.
- Employee IDs are randomized and profile rows are shuffled so ID sequence and row order do not reveal the hidden hierarchy.
- Ground-truth reporting lines are generated at the same time as the profiles but written to a separate file. This supports reproducible evaluation and prevents label leakage into inference.

Synthetic data is useful for validating the workflow but cannot prove performance on real organizations. Before real use, replace or augment the synthetic benchmark with a labelled sample from actual company records and re-check error patterns by industry, function, and seniority.

## Evaluation

Run `python build.py`, then inspect:

- `reports/validation_threshold_sweep.csv` — validation precision, recall, and edge coverage at each threshold.
- `reports/evaluation_summary.json` — chosen threshold and held-out test metrics.
- `reports/test_false_positive_audit.csv` — examples of accepted but incorrect edges for review.

On the generated seed-20261029 benchmark, the current validation-selected threshold is **0.93** with a **0.035** minimum candidate margin. On 100 held-out companies (13,627 employees), the current result is **97.49% edge precision**, **45.36% recall**, and **46.53% edge coverage**. This deliberately prioritizes precision over coverage: more than half of employees remain unresolved or outside the CEO-connected inferred graph. Treat these as reproducible synthetic benchmark results, not claims about real-company performance.

A reporting line is correct only when the predicted manager ID exactly matches the synthetic ground-truth manager ID. Precision answers “when the system makes a claim, how often is it right?” Recall answers “of all true reporting lines, how many did it recover?” Edge coverage is the proportion of ground-truth reporting lines that the system attempts to assign at the selected threshold.

## Limitations and next steps

- Title-only data cannot resolve every team assignment. The system deliberately leaves tied candidates unresolved.
- Confidence values are heuristic evidence scores; a real deployment should calibrate them on labelled production-like data.
- The first version does not make external LLM calls. This keeps evaluation deterministic, cost predictable, and the hosted demo usable without secrets. A next step would be an optional cached title-normalization adapter with model/version logging, while retaining the same ground-truth evaluation and abstention policy.
- Real-world title semantics vary by industry and company. A label-review workflow and periodic re-evaluation are required.
