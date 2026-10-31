"""Build the synthetic dataset, infer manager candidates, and run held-out evaluation."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

from generate_data import generate
from inference import infer_org_chart

ROOT = Path(__file__).parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--companies", type=int, default=500)
    parser.add_argument("--min-employees", type=int, default=100)
    parser.add_argument("--max-employees", type=int, default=180)
    parser.add_argument("--seed", type=int, default=20261029)
    parser.add_argument("--skip-generate", action="store_true", help="Reuse existing data/employees.csv")
    args = parser.parse_args()

    if not args.skip_generate:
        generate(
            seed=args.seed, n_companies=args.companies, min_employees=args.min_employees,
            max_employees=args.max_employees, out_dir=ROOT / "data",
        )
    employees_path = ROOT / "data" / "employees.csv"
    if not employees_path.exists():
        raise FileNotFoundError(f"{employees_path} not found. Run without --skip-generate.")

    employees = pd.read_csv(employees_path, keep_default_na=False)
    print("Inferring candidate managers from flat employee profiles…")
    inferred = infer_org_chart(employees, threshold=0.62, min_margin=0.035)
    inferred_path = ROOT / "data" / "inferred_edges.csv"
    inferred.to_csv(inferred_path, index=False)
    print(f"Wrote {len(inferred):,} employee inference rows to {inferred_path}")

    command = [sys.executable, str(ROOT / "evaluate.py"), "--data-dir", str(ROOT / "data"),
               "--proposals", str(inferred_path), "--output-dir", str(ROOT / "reports")]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
