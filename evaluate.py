"""Evaluate proposed reporting lines against the held-out synthetic ground truth."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import pandas as pd


def company_split(company_ids, seed=20261029):
    ids = list(sorted(set(company_ids)))
    random.Random(seed).shuffle(ids)
    n = len(ids)
    n_train = int(n * 0.60)
    n_val = int(n * 0.20)
    return set(ids[:n_train]), set(ids[n_train:n_train + n_val]), set(ids[n_train + n_val:])


def score_predictions(proposals: pd.DataFrame, truth: pd.DataFrame, threshold: float, min_margin: float, company_ids=None):
    merged = proposals.merge(truth[["employee_id", "manager_id"]], on="employee_id", how="inner", validate="one_to_one")
    if company_ids is not None:
        merged = merged[merged["company_id"].isin(company_ids)].copy()
    proposed_id = merged["proposed_manager_id"].fillna("").astype(str)
    confidence = pd.to_numeric(merged["confidence"], errors="coerce").fillna(0)
    margin = pd.to_numeric(merged["candidate_margin"], errors="coerce").fillna(0)
    accepted = proposed_id.ne("") & confidence.ge(threshold) & margin.ge(min_margin)
    true_manager = merged["manager_id"].fillna("").astype(str)
    true_edge = true_manager.ne("")
    correct = accepted & proposed_id.eq(true_manager)
    predicted_count = int(accepted.sum())
    true_edges = int(true_edge.sum())
    correct_count = int(correct.sum())
    precision = correct_count / predicted_count if predicted_count else 0.0
    recall = correct_count / true_edges if true_edges else 0.0
    coverage = predicted_count / true_edges if true_edges else 0.0
    per_employee = merged["employee_id"].nunique()
    return {
        "threshold": float(threshold),
        "min_margin": float(min_margin),
        "employees_evaluated": int(per_employee),
        "ground_truth_edges": true_edges,
        "predicted_edges": predicted_count,
        "correct_edges": correct_count,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "edge_coverage": round(coverage, 4),
        "unresolved_employee_rate": round(1 - (predicted_count / per_employee if per_employee else 0), 4),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--proposals", default="data/inferred_edges.csv")
    parser.add_argument("--output-dir", default="reports")
    parser.add_argument("--min-margin", type=float, default=0.035)
    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    proposals = pd.read_csv(args.proposals, keep_default_na=False)
    truth = pd.read_csv(data_dir / "ground_truth.csv", keep_default_na=False)
    train_ids, val_ids, test_ids = company_split(proposals["company_id"].unique())

    thresholds = [0.55, 0.58, 0.60, 0.62, 0.64, 0.66, 0.68, 0.70, 0.72, 0.75, 0.78, 0.80, 0.83, 0.86, 0.90, 0.93, 0.96, 0.98]
    sweep_rows = [score_predictions(proposals, truth, t, args.min_margin, val_ids) for t in thresholds]
    sweep = pd.DataFrame(sweep_rows)
    sweep.to_csv(output_dir / "validation_threshold_sweep.csv", index=False)

    # Optimize for coverage only when validation precision is at least 95%.
    eligible = sweep[sweep["precision"] >= 0.95]
    if not eligible.empty:
        chosen = eligible.sort_values(["edge_coverage", "precision"], ascending=[False, False]).iloc[0]
        selection_rule = "Highest validation edge coverage among thresholds with precision >= 0.95"
    else:
        chosen = sweep.sort_values(["precision", "edge_coverage"], ascending=[False, False]).iloc[0]
        selection_rule = "No tested threshold reached 95% validation precision; selected the best precision/coverage row"
    chosen_threshold = float(chosen["threshold"])

    metrics = {
        "dataset": {
            "companies": int(proposals["company_id"].nunique()),
            "employees": int(len(proposals)),
            "train_companies": len(train_ids),
            "validation_companies": len(val_ids),
            "test_companies": len(test_ids),
            "split_seed": 20261029,
        },
        "threshold_selection": {
            "method": "Company-level holdout; tune confidence threshold on validation companies only",
            "selection_rule": selection_rule,
            "chosen_threshold": chosen_threshold,
            "minimum_candidate_margin": args.min_margin,
            "validation_metrics_at_chosen_threshold": score_predictions(proposals, truth, chosen_threshold, args.min_margin, val_ids),
        },
        "held_out_test_metrics": score_predictions(proposals, truth, chosen_threshold, args.min_margin, test_ids),
        "all_data_reference_metrics_not_used_for_selection": score_predictions(proposals, truth, chosen_threshold, args.min_margin),
    }
    with (output_dir / "evaluation_summary.json").open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    # Keep a small audit file to examine false positives on the held-out test companies.
    test = proposals[proposals["company_id"].isin(test_ids)].merge(truth[["employee_id", "manager_id"]], on="employee_id", how="left")
    accepted = test["proposed_manager_id"].fillna("").ne("") & pd.to_numeric(test["confidence"], errors="coerce").fillna(0).ge(chosen_threshold) & pd.to_numeric(test["candidate_margin"], errors="coerce").fillna(0).ge(args.min_margin)
    errors = test[accepted & test["proposed_manager_id"].fillna("").ne(test["manager_id"].fillna(""))]
    columns = [c for c in ["company_id", "employee_id", "name", "title", "inferred_manager_name", "proposed_manager_id", "confidence", "candidate_margin", "reason", "manager_id"] if c in errors.columns]
    errors[columns].head(300).to_csv(output_dir / "test_false_positive_audit.csv", index=False)

    print(json.dumps(metrics, indent=2))
    print(f"Wrote report files to {output_dir.resolve()}")


if __name__ == "__main__":
    main()
