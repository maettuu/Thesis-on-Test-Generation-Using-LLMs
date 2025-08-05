# experiment/results

This branch contains all artifacts and outputs from the experiments conducted to compare the **pre-PR** and **post-PR** test executions across both approaches with and without **PDF**-fetching feature.

---

## Table of Contents

- [Structure](#structure)
- [Result Content](#result-content)
- [Analysis](#analysis)
- [Plotting](#plotting)
- [Branch Purpose](#branch-purpose)

---

## Structure

```
  experiment/results/
  ├── diagrams/                                     # Contains the workflow (activity) diagrams
  ├── plots/                                        # Contains generated bar plots
  ├── results_with_pdf_context/
  │   ├── mozilla__pdf.js-<pr_number>_<timestamp>/  # One directory for each payload
  │   │   └── i<attempt>_<model>/                   # One subdirectory for each attempt and model
  │   │       └── generation/
  │   │           ├── after.txt                     # Output of test execution on post-PR codebase
  │   │           ├── before.txt                    # Output of test execution on pre-PR codebase
  │   │           ├── new_test_file_content.js      # New test file including the generated test
  │   │           ├── prompt.txt                    # Prompt used to query LLM
  │   │           └── raw_model_response.txt        # Raw response from the LLM
  │   ├── analysis.txt                              # Failure type overview
  │   ├── results.csv                               # All attempts and their success
  │   ├── stats.json                                # Summary of failure classifications
  │   └── tests.json                                # Summary of generated tests
  ├── results_without_pdf_context/                  # Same structure but for approach without PDF context
  │   └── ...
  ├── analysis.py                                   # Python script to programmatically analyze result directories
  ├── plotting.py                                   # Python script to plot bar charts
  └── README.md                                     # This README.md
```

---

## Result Content

- **results_with_pdf_context/**  
  Contains all results when executing the pipeline using PDF context.

- **tests.results_without_pdf_context/**  
  Contains all results when executing the pipeline without PDF context.

- **mozilla__pdf.js-\<pr_number\>_\<timestamp\>/**  
  Contains all results for one payload.

- **i\<attempt\>_\<model\>/**  
  Contains all results for a given model and attempt

---

## Analysis

1. Ensure you have Python 3.12 installed.  
2. From this branch's root:
   ```bash
   python analysis.py
   ```
3. Review the generated `analysis.txt` for a summary of the failure types.

---

## Plotting

1. Ensure you install the requirements.
   ```bash
   pip install -r requirements.txt
   ```
2. Update the method calls in `plotting.py` to create the charts of your choosing.
3. From this branch's root:
   ```bash
   python plotting.py
   ```
4. Review the generated charts in `plots/` for a visual illustration of the data.

---

## Branch Purpose

This branch is dedicated solely to storing and analyzing experimental outcomes as well as generating bar charts to evaluate the impact of the pull requests. No source code changes are present here, only experimental data and analysis artifacts.
