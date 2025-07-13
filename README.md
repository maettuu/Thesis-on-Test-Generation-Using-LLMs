# gh-bot-js

A GitHub bot that generates regression-style “fail-to-pass” tests for the repository [pdf.js](github.com/mozilla/pdf.js) by analyzing Pull Request diffs and invoking an LLM to produce test code.

---

## Table of Contents

- [Purpose](#purpose)
- [Prerequisites](#prerequisites)
- [Local Setup](#local-setup)
- [Server Setup](#server-setup)
- [Webhook Setup](#webhook-setup)
- [Build Independently](#build-independently)
- [Webhook Explained](#webhook-explained)
- [Key Components](#key-components)
- [Adding a New Test Payload](#adding-a-new-test-payload)
- [Models Used](#models-used)

---

## Purpose

This bot automatically generates regression-style “fail-to-pass” tests for the JavaScript codebases [pdf.js](github.com/mozilla/pdf.js) by:

1. Slicing the changed code context on each Pull Request.  
2. Prompting an LLM (via the `LLMHandler`) to generate new tests.  
3. Posting the generated test code as review comments on the PR.

---

## Prerequisites

- **Python ≥ 3.11**  
- **Git**  
- **Docker & Docker Engine** 
- **GitHub Token** with repo read/write permissions  
- **API Keys** for `openai` and `groq`

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
   git clone --branch gh-bot-js --single-branch https://github.com/your-org/gh-bot.git ~/gh-bot-js
   cd gh-bot-js
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

## Server Setup
1. **Connect to your server (e.g., using SSH)**
   ```bash
   ssh -i ~/.ssh/<PUBLIC_KEY> <USER>@<SERVER_IP>
   ```
2. **(Optional) Install `DeadSnakes` to manage multiple `Python` versions**
   ```bash
   sudo apt update && sudo apt install software-properties-common
   sudo add-apt-repository ppa:deadsnakes/ppa
   ```
3. **Install `Python3.12` and `nginx`**
   ```bash
   sudo apt install python3.12 python3.12-venv python3.12-dev
   sudo apt install nginx
   ```
4. **Clone the repo**  
   ```bash
   git clone --branch gh-bot-js --single-branch https://github.com/your-org/gh-bot.git ~/gh-bot-js
   cd gh-bot-js
   ```
   *Hint:* To always pull from the same branch, configure git upstream as follows:
    ```bash
    git branch --set-upstream-to=origin/gh-bot-js gh-bot-js
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
   python3.12 -m venv .gh-bot-js-venv
   source .gh-bot-js-venv/bin/activate
   pip install -r requirements.txt
   python manage.py migrate
   deactivate
   ```
7. **Configure `nginx`**

   Create a configuration file:
   ```bash
   sudo nano /etc/nginx/sites-available/django_github_bot.conf
   ```
   Paste the following contents:
   ```text
   server {
     listen 80;
     server_name <SERVER_IP>;

     location /webhook-js/ {
       proxy_pass http://127.0.0.1:8000;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
     }

     location /healthz-js/ {
       proxy_pass http://127.0.0.1:8000/healthz-js/;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
     }
   }
   ```
   *Hint:* If you already have proxies configured you can use that configuration file and simply add the new locations. \
   Next, enable the proxy and restart `nginx`:
   ```bash
   sudo ln -s /etc/nginx/sites-available/django_github_bot /etc/nginx/sites-enabled/
   sudo systemctl restart nginx
   ```
   Requests to `http://<SERVER_IP>/webhook-js/` are now served on `http://127.0.0.1:8000` on your server.
   We can now bind a `systemd` service to port `8000` using `Gunicorn` to connect the `Django` bot.


8. **Configure `systemd` service**

   Create a new service file:
   ```bash
   sudo nano /etc/systemd/system/django_github_bot_js.service
   ```
   Paste the following contents:
   ```text
   [Unit]
   Description=Django GitHub-Bot Javascript
   After=network.target

   [Service]
   User=<USER>
   Group=<GROUP>
   WorkingDirectory=<PATH/TO/gh-bot-js/>
   EnvironmentFile=<PATH/TO/gh-bot-js/.env>
   ExecStart=<PATH/TO/gh-bot-js/.gh-bot-js-venv/bin/gunicorn> \
     --workers 3 \
     --timeout 1800 \
     --bind 0.0.0.0:8000 \
     --capture-output  \
     github_bot.wsgi
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
   Reload the daemon, enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable django_github_bot_js
   sudo systemctl start django_github_bot_js
   ```
   If not done already open the following firewall ports:
   ```bash
   sudo ufw allow OpenSSH
   sudo ufw allow 80/tcp
   sudo ufw enable
   ```
   Any requests are now successfully forwarded and processed. \
   *Hint:* Remember to restart your service whenever you `git pull` any changes to
   have your `Gunicorn` workers run the updated code.
   ```bash
   sudo systemctl restart django_github_bot_js
   ```
   *Hint:* You can follow the logs of your service as follows:
   ```bash
   sudo journalctl -u django_github_bot_js --follow
   ```
   *Hint:* Test your setup as follows:
   ```bash
   curl -i http://<SERVER_IP>/webhook-js/
   curl -i http://<SERVER_IP>/healthz-js/
   ```
9. **Disconnect from your server**
   ```bash
   exit
   ```
---

## Webhook Setup

1. **Add webhook to repository**  
   1. In GitHub, open the target repository.
   2. Open the tab **Settings**.
   3. In the left sidebar, select **Webhooks**.
   4. Click **Add webhhook**.

2. **Configure webhook**  

| Field                | Value                            |
|----------------------|----------------------------------|
| **Payload URL**      | `http://<SERVER_IP>/webhook-js/` |
| **Content type**     | `application/json`               |
| **Secret**           | `<WEBHOOK_SECRET>`               |
| **SSL verification** | _Keep enabled_                   |

3. **Configure triggers**  
   1. Select **Let me select individual events.**
   2. Tick only **Pull requests**, leave everything else unchecked.

4. **Save and verify**
   1. Keep the checkbox **Active** ticked.
   2. Click **Add webhook**.
   3. The setup is completed. In the webhooks list you will now find the entry: \
   `http://<SERVER_IP>/webhook-js/` _(pull_request)_

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

### Stop & Restart the Container

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
  2. Fetch linked issue.
  3. Clone the repo.
  4. Slice golden code around diffs.
  5. Fetch file for test injection.
  6. Build a Docker container.
  7. Execute `TestGenerator` → LLM.
  8. Post review comments containing generated test.

---

## Key Components

- **Django App (`github_bot/`)**  
  - Exposes `POST /webhook-js/` for GitHub PR events, verifies signatures, and dispatches to the pipeline.

- **Webhook (`webhook.py)**
  - Entry point for any request sent to the server.

- **Pipeline (`pipeline.py`)**  
  - Coordinates every step in the flow.

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

1. **Mock Payload**  
   Place your PR JSON under:  
   ```
   webhook_handler/test/test_mocks/<repo>_<pr_id>.json
   ```
   If you have a mock response add it as `.txt`:
   ```
   webhook_handler/test/test_mocks/<repo>_<pr_id>_response.txt
   ```
2. **Test Case**  
   In `webhook_handler/test/javascript_test_generation.py`:

   ```python
   class TestGeneration<Repo><PR_ID>(TestCase):
    def setUp(self):
        self.payload = _get_payload("test_mocks/<repo>_<pr_id>.json")
        # if you have a mock response load it as follows
        mock_response = _get_mock_content("test_mocks/<repo>_<pr_id>_response.txt")
        self.config = Config()
        self.pipeline = Pipeline(self.payload, self.config, mock_response=mock_response)

    def tearDown(self):
        del self.payload
        del self.config
        del self.pipeline

    def test_generation_<repo>_<pr_id>(self):
        generation_completed = self.pipeline.execute_pipeline()
        self.assertTrue(generation_completed)
   ```

3. **Run**  
   ```bash
   python manage.py test webhook_handler.test.javascript_test_generation:TestGeneration<Repo><PR_ID>
   ```

---

## Models Used

- **OpenAI from openai:** GPT-4o, o4-mini
- **Groq from groq:** llama-3.3-70b-versatile, deepseek-r1-distill-llama-70b

_With this setup, every Pull Request triggers automated, AI-driven regression tests—helping catch regressions early and reducing manual QA overhead._
