# gh-bot-js

A GitHub bot that generates regression-style “fail-to-pass” tests for JavaScript projects by analyzing Pull Request diffs and invoking an LLM to produce or amplify test code.

---

## Table of Contents

- [Purpose](#purpose)  
- [Prerequisites](#prerequisites)  
- [Setup](#setup)  
- [Build Independently](#build-independently)
- [Webhook Explained](#webhook-explained)  
- [Key Components](#key-components)  
- [Adding a New Test Payload](#adding-a-new-test-payload)  
- [Models Used](#models-used)  

---

## Purpose

This Bot automatically generates and amplifies regression-style “fail-to-pass” tests for JavaScript codebases (e.g., PDF.js) by:

1. Slicing the changed code context on each Pull Request.  
2. Prompting an LLM (via the `LLMHandler`) to generate new tests or extend existing ones.  
3. Posting the generated test code as review comments on the PR.

---

## Prerequisites

- **Python ≥ 3.11**  
- **Git**  
- **Docker & Docker Engine** (for slicing service)  
- **GitHub Token** with repo read/write permissions  
- **API Keys** for `openai`, `hugging_face` & `groq`

---

## Setup

1. **Clone the repo**  
   ```bash
   git clone --branch gh-bot-js --single-branch https://github.com/your-org/gh-bot.git
   cd gh-bot
   ```

2. **Environment file**  
   ```bash
   cp .env.example .env
   # Then populate:
   # GITHUB_TOKEN, GITHUB_WEBHOOK_SECRET,
   # OPENAI_API_KEY, HUG_API_KEY, GROQ_API_KEY
   ```

3. **Install dependencies & migrate**  
   ```bash
   python -m venv .gh-bot-js-venv
   source .gh-bot-js-venv/bin/activate
   pip install -r requirements.txt
   python manage.py migrate
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

## Webhook Explained

- **Endpoint:** `POST /webhook-js/`  
- **Signature:** Verifies `X-Hub-Signature-256` with `GITHUB_WEBHOOK_SECRET`.  
- **Events:** Listens to PR events (`opened`, `synchronize`, etc.).  
- **Flow:**  
  1. Parse PR metadata.  
  2. Fetch or clone the repo.  
  3. Slice golden code around diffs.  
  4. Call `TestGenerator` / `TestAmplifier` → LLM.  
  5. Post review comments containing test code.

---

## Key Components

- **Django App (`webhook_handler/`)**  
  - Exposes `POST /webhook-js/` for GitHub PR events, verifies signatures, and dispatches to the pipeline.

- **Pipeline (`pipeline.py`)**  
  - Coordinates diff slicing, LLM prompting, and test generation/amplification.

- **Tests (`webhook_handler/test/`)**  
  - Mock PR payloads and assertions on generated test output.

### core/

- **`Config`**: Centralizes configuration (prompt templates, thresholds, environment settings).
- **`git_tools`**: Encapsulates Git operations: cloning, checking out PR branch, applying diffs.
- **`helpers`**: Extracts helpers methods to minimize duplicated code.
- **`templates`**: Contains templates for posting comments on the PR.

### data_models/

- **`PullRequestData`**: Defines the schema for incoming GitHub Pull Request webhook payloads.
- **`PullRequestFileDiff`**: Defines the schema for files pre- and post-PR.
- **`PullRequestPipelineData`**: Defines compact schema for all data used in the pipeline.

### services/
 
- **`DockerService`**: Runs a target code environment (e.g., PDF.js container) for context extraction.  
- **`GoldenFileSlicer`**: Extracts minimal “golden” code around the changed lines.  
- **`GitHubApi`**: Fetches PR data and posts back comments.  
- **`LLMHandler`**: Manages prompt templates and API calls.  
- **`PullRequestDiffContext`**:  Models the extracted code snippets (golden files + diffs) sent to the LLM.
- **`TestGenerator`** & **`TestAmplifier`**: Generate new tests or expand existing ones.

---

## Adding a New Test Payload

1. **Mock Payload**  
   Place your PR JSON under:  
   ```
   webhook_handler/test/test_mocks/<repo>_<pr_id>.json
   ```

2. **Test Case**  
   In `webhook_handler/test/javascript_test_generation.py`:

   ```python
   class TestGeneration<Repo><PR_ID>(TestCase):
    def setUp(self):
        self.test_helper = TestHelper(payload_path="test_mocks/<repo>_<pr_id>.json", run_all_models=True)

    def test_generation_<repo>_<pr_id>(self):
        response = self.test_helper.run_payload()
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse
   ```

3. **Run**  
   ```bash
   python manage.py test webhook_handler.test.javascript_test_generation:YourTestClass
   ```

---

## Models Used

- **OpenAI from openai:** GPT-4o, o1, o3-mini
- **InferenceClient from huggingface_hub:** meta-llama/Llama-3.3-70B-Instruct
- **Groq from groq:** llama-3.3-70b-versatile, qwen-qwq-32b

_With this setup, every Pull Request triggers automated, AI-driven regression tests—helping catch regressions early and reducing manual QA overhead._
