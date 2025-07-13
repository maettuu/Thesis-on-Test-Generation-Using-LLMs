import os
import requests
import time
import re
import json

from dotenv import load_dotenv
from pathlib import Path


load_dotenv()


############### Global Variables ################
SCRAPE_TARGET = 500
OUTPUT_DIR = Path("test", "scrape_mocks")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "code_only").mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "code_test").mkdir(parents=True, exist_ok=True)

API_URL = "https://api.github.com/repos"
OWNER = 'mozilla'
REPO = 'pdf.js'
HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
}


def _fetch_github_data(url: str) -> dict:
    """
    Fetches data from GitHub API.

    Parameters:
        url (str): GitHub URL.

    Returns:
        dict: Data.
    """

    response = requests.get(url, headers=HEADERS)
    if response.status_code == 403 and "X-RateLimit-Reset" in response.headers:
        print("[*] Sleeping...")
        reset_time = int(response.headers["X-RateLimit-Reset"])
        wait_time = reset_time - int(time.time()) + 1
        time.sleep(max(wait_time, 1))
        return _fetch_github_data(url)
    response.raise_for_status()
    return response.json()


def _fetch_pr_list(curr_page: int) -> dict:
    """
    Fetches list of PRs on current page.

    Parameters:
        curr_page (int): Current page number.

    Returns:
        dict: PR list.
    """

    list_url = (
        f"{API_URL}/{OWNER}/{REPO}/pulls"
        f"?state=all&sort=created&direction=desc"
        f"&per_page=100&page={curr_page}"
    )
    return _fetch_github_data(list_url)


def _fetch_pr_files(pr_number: int) -> dict:
    """
    Fetches PR files.

    Parameters:
        pr_number (int): PR number.

    Returns:
        dict: All files modified in that PR.
    """

    url = f"{API_URL}/{OWNER}/{REPO}/pulls/{pr_number}/files"
    return _fetch_github_data(url)


def _get_linked_data(pr_title: str, pr_description: str) -> str:
    """
    Checks and fetches a linked issue.

    Parameters:
        pr_title (str): Title of the PR.
        pr_description (str): Description of the PR.

    Returns:
        str: The linked issue title and description
    """

    issue_pattern = r'\b(?:Closes|Fixes|Resolves)\s+#(\d+)\b|\(?\b(?:bug|issue)\b\s+(\d+)\)?'
    issue_description = f"{pr_title} {pr_description}"
    matches = re.findall(issue_pattern, issue_description, re.IGNORECASE)

    for match in matches:
        issue_nr_str = match[0] or match[1]
        if not issue_nr_str: continue

        issue_nr = int(issue_nr_str)
        linked_issue_description = _get_github_issue(issue_nr)
        if linked_issue_description:
            return linked_issue_description

        linked_issue_description = _get_bugzilla_issue(issue_nr)
        if linked_issue_description:
            return linked_issue_description

    return ""


def _get_github_issue(number: int) -> str | None:
    """
    Fetches a GitHub issue.

    Parameters:
        number (int): The number of the issue

    Returns:
        str | None: The GitHub issue title and description
    """

    url = f"{API_URL}/{OWNER}/{REPO}/issues/{number}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        issue_data = response.json()
        if not "pull_request" in issue_data:
            return "\n".join(value for value in (issue_data["title"], issue_data["body"]) if value)

    return None


def _get_bugzilla_issue(number: int) -> str | None:
    """
    Fetches a Bugzilla issue.

    Parameters:
        number (int): The number of the issue

    Returns:
        str | None: The Bugzilla issue title and description
    """

    response = requests.get(f"https://bugzilla.mozilla.org/rest/bug/{number}")
    if response.status_code == 200:
        bug_data = response.json()
        if "bugs" in bug_data and bug_data["bugs"]:
            bug = bug_data["bugs"][0]
            return "\n".join(value for value in (bug.get("summary", ""), bug.get("description", "")) if value)

    return None


def _is_test_file(filename) -> bool:
    """
    Determines whether the given file is a test file or not

    Parameters:
        filename (str): The name of the file

    Returns:
        bool: True if it is a test file, False otherwise
    """

    is_in_test_folder = False
    parts = filename.split('/')

    # at least one folder in the dir path starts with test
    for part in parts[:-1]:
        if part.startswith('test'):
            is_in_test_folder = True
            break

    if is_in_test_folder and 'spec' in parts[-1] and parts[-1].endswith("js"):
        return True
    return False


def _is_src_code_file(filename) -> bool:
    """
    Determines whether the given file is a source code file or not

    Parameters:
        filename (str): The name of the file

    Returns:
        bool: True if it is a source code file, False otherwise
    """

    is_in_src_folder = False
    parts = filename.split('/')

    # at least one folder in the dir path starts with src
    for part in parts[:-1]:
        if part.startswith('src'):
            is_in_src_folder = True
            break

    if is_in_src_folder and parts[-1].endswith(".js"):
        return True
    return False


def _save_pr(payload) -> None:
    """
    Saves PR data in the 'code_only' directory.

    Parameters:
        payload (dict): PR data.
    """

    pr_number = payload["pull_request"]["number"]
    filename = f"pdf_js_{pr_number}.json"
    path = OUTPUT_DIR / "code_only" / filename
    if not path.exists():
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4)
        print(f"[+] Saved PR #{pr_number} to {path}\n")
    else:
        print(f"[!] PR #{pr_number} at {path} already exists\n")


def _save_pr_amp(payload) -> None:
    """
    Saves PR data in the 'code_test' directory.

    Parameters:
        payload (dict): PR data.
    """

    pr_number = payload["pull_request"]["number"]
    filename = f"pdf_js_{pr_number}.json"
    path = OUTPUT_DIR / "code_test" / filename
    if not path.exists():
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4)
        print(f"[+] Saved PR #{pr_number} to {path}\n")
    else:
        print(f"[!] PR #{pr_number} at {path} already exists\n")


def _process_pr(curr_pr: dict) -> bool:
    """
    Processes PR fetched from the GitHub PR list.

    Parameters:
        curr_pr (dict): PR data.

    Returns:
        bool: True if PR fulfills requirements, False otherwise.
    """

    global valid_payloads, valid_payloads_amp

    pr_number = curr_pr["number"]
    print(f"[*] Processing PR #{pr_number}...")

    # Requirement #1: PR must have action OPENED or MERGED (=CLOSED and MERGED_AT)
    if not (curr_pr["state"] == "open" or (curr_pr["state"] == "closed" and curr_pr["merged_at"] is not None)):
        print(f"[!] PR #{pr_number} was closed but not merged\n")
        return False

    # Requirement #2: PR must have linked issue
    if not _get_linked_data(curr_pr["title"], curr_pr["body"]):
        print(f"[!] No linked issue for PR #{pr_number}\n")
        return False

    files = _fetch_pr_files(pr_number)
    file_types = []
    for f in files:
        if "patch" in f:
            if _is_test_file(f["filename"]):
                file_types.append("test")
            elif _is_src_code_file(f["filename"]):
                file_types.append("src")
            elif f["filename"].endswith(".js"):
                file_types.append("non-src")
            else:
                file_types.append("other")
        else:
            file_types.append("unchanged")

    # Requirement #3: All .js files modified in PR must be source code files
    if "non-src" in file_types:
        print(f"[!] Non-source code files in PR #{pr_number}\n")
        return False

    current_payload = {
        "action": "opened",
        "number": pr_number,
        "pull_request": curr_pr,
        "repository": {"owner": {"login": OWNER}, "name": REPO}
    }

    # Requirement #4: PR must modify at least one .js file
    if "src" in file_types:
        if "test" in file_types:
            valid_payloads_amp += 1
            _save_pr_amp(current_payload)
        else:
            valid_payloads += 1
            _save_pr(current_payload)
        return True
    else:
        print(f"[!] No .js changes in source code in PR #{pr_number}\n")
        return False


################## Main Logic ###################
valid_payloads = 0
valid_payloads_amp = 0
page = 1

while valid_payloads < SCRAPE_TARGET:
    pr_list = _fetch_pr_list(page)
    if not pr_list:
        break

    for pr in pr_list:
        if _process_pr(pr) and valid_payloads >= SCRAPE_TARGET:
            break

    page += 1

print(f"[+] Found {valid_payloads} valid payloads")
print(f"[+] Found {valid_payloads_amp} valid payloads with test files\n")