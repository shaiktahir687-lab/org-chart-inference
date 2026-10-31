Hi Firmable team,

Thanks for sharing the take-home assignment. I've built a small org-chart inference application and included the synthetic data generator, inference engine, evaluation pipeline, and design documentation.

- **Live application:** https://org-chart-inference-lkm4i4h7shomnv9yxnutcu.streamlit.app/
- **Git repository:** https://github.com/shaiktahir687-lab/org-chart-inference

The dataset generator creates 500 synthetic companies with more than 69,000 employee profiles, including noisy job titles and department fields. Ground-truth manager IDs are stored separately from the inference input to prevent data leakage.

The inference engine uses company-level validation and test splits to select a confidence threshold and evaluates the results using precision, recall, and edge coverage. When the evidence is ambiguous, the system deliberately leaves the reporting line unresolved rather than making an unsupported prediction.

On the held-out test set of 100 companies (13,627 employees), the selected threshold of 0.93, with a minimum candidate margin of 0.035, achieved **97.49% edge precision and 46.53% edge coverage**.

I chose this trade-off deliberately: for org charts used in sales workflows, an unsupported reporting line can be more harmful than a missing line. The README explains the scoring approach, evaluation methodology, limitations of synthetic data, and steps to reproduce the results.

To run the application locally, install the dependencies using `pip install -r requirements.txt` and start it with `streamlit run app.py`. The repository also includes `python build.py` to regenerate the benchmark and run the evaluation.

Best,  
Tahir
