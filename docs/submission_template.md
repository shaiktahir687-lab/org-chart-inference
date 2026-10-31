Subject: Org Chart Inference — Take-Home Submission

Hi Firmable team,

Thanks for sharing the take-home. I've built a small org-chart inference app and included the synthetic data generator, inference code, evaluation, and design notes.

- Live app: [ADD DEPLOYED APP URL]
- Git repository: [ADD GITHUB REPOSITORY URL]

The dataset generator creates 500 synthetic companies and more than 69,000 employee profiles with noisy titles and department fields. Ground-truth manager IDs are stored separately from the inference input. I use company-level validation/test splits to select a confidence threshold, report precision/recall/coverage, and leave a manager unresolved when the evidence is ambiguous.

On the current held-out synthetic test set, the selected threshold achieved 97.49% precision at 46.53% edge coverage. I chose that trade-off deliberately: for org charts used in sales workflows, an unsupported reporting line can be more harmful than a missing line. The README explains the scoring approach, limitations of synthetic data, and how to reproduce the evaluation.

To run locally, install `requirements.txt` and run `streamlit run app.py`. The repository also includes `python build.py` to regenerate the benchmark and evaluation.

Best,
Tahir
