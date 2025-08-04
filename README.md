# Experiment Results

This branch contains all artifacts and outputs from the experiments conducted to compare the **pre-PR** and **post-PR** test executions across both approaches with and without **PDF**-fetching feature. The structure and contents are organized as follows:

---

## Structure

```
  experiment/results/
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
  └── README.md                                     # This README.md
```

---

## Contents

- **results_with_pdf_context/**  
  Contains all results when executing the pipeline using PDF context.

- **tests.results_without_pdf_context/**  
  Contains all results when executing the pipeline without PDF context.

- **mozilla__pdf.js-\<pr_number\>_\<timestamp\>/**  
  Contains all results for one payload.

- **i\<attempt\>_\<model\>/**  
  Contains all results for a given model and attempt

---

## Usage

1. Ensure you have Python 3.12 installed.  
2. From this branch’s root:
   ```bash
   python analysis.py
   ```
3. Review the generated `analysis.txt` for a summary of the failure types.

---

## Branch Purpose

This branch is dedicated solely to storing and analyzing experimental outcomes to evaluate the impact of the pull requests. No source code changes are present here, only experimental data and analysis artifacts.
