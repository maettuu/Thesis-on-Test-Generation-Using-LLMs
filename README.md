# gh-bot-js-scrape

This codebase extends from the [gh-bot-js](https://github.com/kitsiosk/gh-bot/tree/gh-bot-js) branch to enable PR scraping and autonomous execution of the pipeline. 

---

## Table of Contents

- [Purpose](#purpose)
- [Prerequisites](#prerequisites)
- [Local Setup](#local-setup)
- [Batch Server Job](#batch-server-job)
- [Build Independently](#build-independently)
- [Key Components](#key-components)
- [Adding a New Test Payload](#adding-a-new-test-payload)
- [Models Used](#models-used)

---

## Purpose

This codebase automatically scrapes PR data from [pdf.js](https://github.com/mozilla/pdfjs) and generates regression-style “fail-to-pass” tests by:

1. Scraping PR data from GitHub.
2. Slicing the changed code context on each scrape payload.
3. Prompting an LLM (via the `LLMHandler`) to generate new tests.

This project lives in its own branch to run in the background and not interrupt the functionality of the actual bot.

---

## Prerequisites

- **Python ≥ 3.11**  
- **Git**  
- **Docker & Docker Engine** (for slicing service)  
- **GitHub Token** with repo read/write permissions  
- **API Keys** for `openai`, `hugging_face` & `groq`

To set up a GitHub Token follow these steps.
1. **Create new Token**
   1. In GitHub, open your profile settings.
   2. In the left sidebar, select **Developer Settings**.
   3. In the left sidebar, expand **Personal access tokens**.
   4. In the left sidebar, select **Tokens (classic)**.
   5. Click **Generate new token** and select **Generate new token (classic)**.
2. **Configure Token**
   1. Give your token a name.
   2. Set an expiration date.
3. **Configure Scope**
   1. Select only the scope **public_repo** under **repo**.
4. **Save and verify**
   1. Click **Generate token**.
   2. The setup is completed. In the tokens list you will now find the entry: `<NAME>` — *public_repo*

---

## Local Setup

1. **Clone the repo**  
   ```bash
   git clone --branch gh-bot-js-scrape --single-branch https://github.com/your-org/gh-bot.git ~/gh-bot-js-scrape
   cd gh-bot-js-scrape
   ```
   *Hint:* To always pull from the same branch, configure git upstream as follows:
    ```bash
    git branch --set-upstream-to=origin/gh-bot-js gh-bot-js
    ```
   Now you can run `git pull` to simply update the single branch. You can verify this configuration with:
   ```bash
    git branch -vv
    ```
2. **Environment file**  
   ```bash
   cp .env.example .env
   ```
   Populate all environment variables: `GITHUB_WEBHOOK_SECRET`, `GITHUB_TOKEN`, `OPENAI_API_KEY`, `GROQ_API_KEY`.


3. **Install dependencies**  
   ```bash
   python -m venv .gh-bot-js-venv
   source .gh-bot-js-venv/bin/activate
   pip install -r requirements.txt
   ```

---

## Batch Server Job

1. **Connect to your server (e.g., using SSH)**
   ```bash
   ssh -i ~/.ssh/<PUBLIC_KEY> <USER>@<SERVER_IP>
2. **(Optional) Install `DeadSnakes` to manage multiple `Python` versions**
   ```bash
   sudo apt update && sudo apt install software-properties-common
   sudo add-apt-repository ppa:deadsnakes/ppa
   ```
3. **Install `Python3.12` and `tmuxp`**
   ```bash
   sudo apt install python3.12 python3.12-venv python3.12-dev
   sudo apt install tmuxp
   ```
4. **Clone the repo**  
   ```bash
   git clone --branch gh-bot-js-scrape --single-branch https://github.com/your-org/gh-bot.git ~/gh-bot-js-scrape
   cd gh-bot-js-scrape
   ```
   *Hint:* To always pull from the same branch, configure git upstream as follows:
    ```bash
    git branch --set-upstream-to=origin/gh-bot-js-scrape gh-bot-js-scrape
    ```
   Now you can run `git pull` to simply update the single branch. You can verify this configuration with:
   ```bash
    git branch -vv
    ```
5. **Environment file**  
   ```bash
   cp .env.example .env
   ```
   Populate all environment variables: `GITHUB_WEBHOOK_SECRET`, `GITHUB_TOKEN`, `OPENAI_API_KEY`, `GROQ_API_KEY`.


6. **Install dependencies & migrate**  
   ```bash
   python3.12 -m venv .gh-bot-js-scrape-venv
   source .gh-bot-js-scrape-venv/bin/activate
   pip install -r requirements.txt
   ```
7. **Navigate to the `test/` directory**
   ```bash
   cd scrape_handler/test/
   ```
8. **Create a new `tmux` session**
   ```bash
   tmux new -s js_payload_tests
   ```
9. **Execute the batch job using `pytest`**
   ```bash
   pytest -s javascript_test_generation.py
   ```
   *Hint:* Use the `-s` flag to see the output dynamically. \
   *Hint:* Exit the session with `Ctrl + B, D`.


10. **Disconnect from your server**
   ```bash
   exit
   ```

---

## Build Independently

### Build Docker Image

Head of repository (latest commit)
```bash
   docker build -f dockerfiles/Dockerfile_pdf.js -t gh-bot_pdfjs_img .
```

Specific commit
```bash
   docker build -f dockerfiles/Dockerfile_pdf.js --build-arg commit_hash=<commit_hash> -t gh-bot_pdfjs_img .
```

### Run in Detached Mode

```bash
   docker run -dit --name gh-bot_pdfjs_ctn gh-bot_pdfjs_img bash
```

### Connect to Container with Bash

```bash
   docker exec -it gh-bot_pdfjs_ctn bash
```

### Start & Stop the Container

```bash
   docker stop gh-bot_pdfjs_ctn
   docker start -ai gh-bot_pdfjs_ctn
```

---

## Key Components

- **Scraping (`scraping.py`)**  
  - Iterates through all PRs and fetches the data for those fulfilling the following requirements:
    1. The PR's action must be OPENED or MERGED.
    2. The PR must have a linked issue.
    3. The PR must modify at least one `.js` file.
    4. For all `.js` files, the PR must only modify code within the `src/` directory

- **Pipeline (`pipeline.py`)**  
  - Coordinates every step in the flow:
    1. Parse PR metadata.
    2. Fetch linked issue.
    3. Clone the repo.
    4. Slice golden code around diffs.
    5. Fetch file for test injection.
    6. Build a Docker container.
    7. Execute `TestGenerator` → LLM.

- **Tests (`webhook_handler/test/`)**  
  - Mock PR payloads and assertions on generated test output.

### core/

- **`Config`**: Centralizes configuration (prompt templates, thresholds, environment settings).
- **`ExecutionError`**: Custom error to report interruptions in pipeline.
- **`git_diff`**: Encapsulates Git operations: generating and applying diffs.
- **`helpers`**: Extracts helpers methods to minimize duplicated code.
- **`templates`**: Contains templates for posting comments on the PR.
- **`test_injection`**: Deals with finding candidate test file for injecting the newly generated test.

### data_models/

- **`LLM`**: Enum to define available LLMs
- **`PipelineInputs`**: Defines compact schema for all data used in the pipeline.
- **`PullRequestData`**: Defines the schema for incoming GitHub Pull Request webhook payloads.
- **`PullRequestFileDiff`**: Defines the schema for files pre- and post-PR.

### services/
 
- **`CSTBuilder`**: In charge of all operations which rely on concrete syntax trees.  
- **`DockerService`**: Runs a target code environment for context extraction.  
- **`GitHubApi`**: Fetches PR data and posts back comments.  
- **`LLMHandler`**: Manages prompt templates and API calls.  
- **`PullRequestDiffContext`**:  Models the extracted code snippets (golden files + diffs) sent to the LLM.
- **`TestGenerator`**: Operating class to query the LLM and execute the test in the pre-PR and the post-PR codebase.

---

## Adding a New Test Payload

Place your PR JSON under:  
```
scrape_handler/test/scrape_mocks/code_only/<repo>_<pr_id>.json
```

The PR will now be included in the execution.

---

## Models Used

- **OpenAI from openai:** GPT-4o, o4-mini
- **Groq from groq:** llama-3.3-70b-versatile, deepseek-r1-distill-llama-70b

_With this setup, every Pull Request triggers automated, AI-driven regression tests—helping catch regressions early and reducing manual QA overhead._
