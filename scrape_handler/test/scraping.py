import os
import requests
import time
import re
import json

from dotenv import load_dotenv
from pathlib import Path


load_dotenv()

OWNER = 'mozilla'
REPO = 'pdf.js'
HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
}
API_URL = "https://api.github.com/repos"

def fetch_github_data(url: str) -> dict:
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 403 and "X-RateLimit-Reset" in response.headers:
        print("[*] Sleeping...")
        reset_time = int(response.headers["X-RateLimit-Reset"])
        wait_time = reset_time - int(time.time()) + 1
        time.sleep(max(wait_time, 1))
        return fetch_github_data(url)
    response.raise_for_status()
    return response.json()

def fetch_pr_list(curr_page: int) -> dict:
    list_url = (
        f"{API_URL}/{OWNER}/{REPO}/pulls"
        f"?state=all&sort=created&direction=desc"
        f"&per_page=100&page={curr_page}"
    )
    return fetch_github_data(list_url)

def fetch_pr_files(pr_number: int) -> dict:
    url = f"{API_URL}/{OWNER}/{REPO}/pulls/{pr_number}/files"
    return fetch_github_data(url)

def get_full_statement(pr_title: str, pr_description: str) -> str:
    has_linked, issue, title, description = check_if_has_linked_issue(pr_title, pr_description)
    return "\n".join(value for value in (title, description) if value)

def check_if_has_linked_issue(pr_title: str, pr_description: str):
    issue_pattern = r'\b(?:Closes|Fixes|Resolves)\s+#(\d+)\b|\(?\b(?:bug|issue)\b\s+(\d+)\)?'
    matches = re.findall(issue_pattern, f"{pr_title} {pr_description}", re.IGNORECASE)
    for match in matches:
        match_str = match[0] or match[1]
        if not match_str:
            continue
        match_int = int(match_str)
        issue_or_pr, title, description = is_issue_or_pr(match_int)
        if issue_or_pr == "Issue":
            return True, match_int, title, description
    return False, None, None, None

def is_issue_or_pr(pr_number: int):
    url = f"{API_URL}/{OWNER}/{REPO}/issues/{pr_number}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        issue_data = response.json()
        if "pull_request" in issue_data:
            return "PR", None, None
        else:
            return "Issue", issue_data["title"], issue_data["body"]
    else:
        return is_bugzilla_issue(pr_number)

def is_bugzilla_issue(pr_number: int):
    bugzilla_url = f"https://bugzilla.mozilla.org/rest/bug/{pr_number}"
    response = requests.get(bugzilla_url)
    if response.status_code == 200:
        bug_data = response.json()
        if "bugs" in bug_data and bug_data["bugs"]:
            bug = bug_data["bugs"][0]
            return "Issue", bug.get("summary"), bug.get("description", "")
        else:
            return None, None, None
    else:
        return None, None, None

def is_test_file(filename) -> bool:
    is_in_test_folder = False
    parts = filename.split('/')

    # We want the file to be in a dir where at least one folder in the dir path starts with test
    for part in parts[:-1]:
        if part.startswith('test'):
            is_in_test_folder = True
            break

    if is_in_test_folder and 'spec' in parts[-1] and parts[-1].endswith("js"):
        return True
    return False

def is_code_file(filename) -> bool:
    return filename.endswith(".js")

def process_pr(curr_pr: dict) -> bool:
    pr_number = curr_pr["number"]
    print(f"[*] Processing PR #{pr_number}...")

    if not (curr_pr["state"] == "open" or (curr_pr["state"] == "closed" and curr_pr["merged_at"] is not None)):
        print(f"[!] PR #{pr_number} was closed but not merged\n")
        return False

    if not get_full_statement(curr_pr["title"], curr_pr["body"]):
        print(f"[!] No linked issue for PR #{pr_number}\n")
        return False

    files = fetch_pr_files(pr_number)
    has_js_code = False
    has_test_code = False
    for f in files:
        if "patch" in f:
            if is_test_file(f["filename"]):
                has_test_code = True
            elif is_code_file(f["filename"]):
                has_js_code = True

    current_payload = {
        "action": "opened",
        "number": pr_number,
        "pull_request": curr_pr,
        "repository": {"owner": {"login": OWNER}, "name": REPO}
    }

    if has_js_code:
        if has_test_code:
            valid_payloads_amp.append(current_payload)
        else:
            valid_payloads.append(current_payload)
        print(f"[+] Success for PR #{pr_number}\n")
        return True
    else:
        print(f"[!] No .js changes in PR #{pr_number}\n")
        return False



TARGET = 5
OUTPUT_DIR = Path("test", "scrape_mocks")

valid_payloads = []
valid_payloads_amp = []
page = 1

while len(valid_payloads) < TARGET:
    pr_list = fetch_pr_list(page)
    if not pr_list:
        break

    for pr in pr_list:
        if process_pr(pr) and len(valid_payloads) >= TARGET:
            break

    page += 1

print(f"[*] Found {len(valid_payloads)} valid payloads")
print(f"[*] Found {len(valid_payloads_amp)} valid payloads with test files\n")

for payload in valid_payloads:
    number = payload["pull_request"]["number"]
    filename = f"pdf_js_{number}.json"
    path = OUTPUT_DIR / "code_only" / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)
    print(f"[+] Saved PR #{number} to {path}")

print()
for payload in valid_payloads_amp:
    number = payload["pull_request"]["number"]
    filename = f"pdf_js_{number}.json"
    path = OUTPUT_DIR / "code_test" / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)
    print(f"[+] Saved PR #{number} to {path}")