import requests
import time
import re
import subprocess

from scrape_handler.core.config import Config
from scrape_handler.data_models.pr_data import PullRequestData


class GitHubApi:
    def __init__(self, config: Config, pr_data: PullRequestData, logger):
        self.config = config
        self.pr_data = pr_data
        self.logger = logger
        self.api_url = "https://api.github.com/repos"

    def fetch_pr_files(self) -> dict:
        url = f"{self.api_url}/{self.pr_data.owner}/{self.pr_data.repo}/pulls/{self.pr_data.number}/files"
        response = requests.get(url, headers=self.config.headers)
        if response.status_code == 403 and "X-RateLimit-Reset" in response.headers:
            reset_time = int(response.headers["X-RateLimit-Reset"])
            wait_time = reset_time - int(time.time()) + 1
            # logger.info(f"Rate limit exceeded. Waiting for {wait_time} seconds...")
            time.sleep(max(wait_time, 1))
            return self.fetch_pr_files()

        response.raise_for_status()
        return response.json()

    def fetch_file_version(self, commit: str, file_name: str) -> str:
        url = f"https://raw.githubusercontent.com/{self.pr_data.owner}/{self.pr_data.repo}/{commit}/{file_name}"
        response_after = requests.get(url, headers=self.config.headers)
        if response_after.status_code == 200:
            return response_after.text
        return ""

    def get_full_statement(self) -> str:
        has_linked, issue, title, description = self.check_if_has_linked_issue()
        return "\n".join(value for value in (title, description) if value)  # concatenate title and description

    def check_if_has_linked_issue(self):
        # Seach for "Closes #2" etc
        issue_pattern = r'\b(?:Closes|Fixes|Resolves)\s+#(\d+)\b|\(?\b(?:bug|issue)\b\s+(\d+)\)?'
        matches = re.findall(issue_pattern, f"{self.pr_data.title} {self.pr_data.description}", re.IGNORECASE)

        # Since PRs and Issues are treated the same by the GH API, we need to check if the
        # referenced entity is PR or GH Issue
        for match in matches:
            match_str = match[0] or match[1]
            if not match_str:
                continue
            match_int = int(match_str)  # match was originally string
            issue_or_pr, title, description = self.is_issue_or_pr(match_int)
            if issue_or_pr == "Issue":
                self.logger.info("Linked with issue #%d" % match_int)
                return True, match_int, title, description  # we don't support linking of >1 issues yet

        self.logger.info("No linked issue")
        return False, None, None, None

    def is_issue_or_pr(self, number):
        url = f"{self.api_url}/{self.pr_data.owner}/{self.pr_data.repo}/issues/{number}"
        response = requests.get(url, headers=self.config.headers)
        if response.status_code == 200:
            issue_data = response.json()
            if "pull_request" in issue_data:
                return "PR", None, None
            else:
                return "Issue", issue_data["title"], issue_data["body"]
        else:
            self.logger.info("[!] No GitHub issue found. Checking Bugzilla...")
            return self.is_bugzilla_issue(number)

    def is_bugzilla_issue(self, number: int):
        bugzilla_url = f"https://bugzilla.mozilla.org/rest/bug/{number}"
        response = requests.get(bugzilla_url)
        if response.status_code == 200:
            bug_data = response.json()
            if "bugs" in bug_data and bug_data["bugs"]:
                bug = bug_data["bugs"][0]
                return "Issue", bug.get("summary"), bug.get("description", "")
            else:
                self.logger.info(f"No bug found in Bugzilla with ID {number}")
                return None, None, None
        else:
            self.logger.info(f"Failed to fetch data for #{number}: {response.status_code}")
            return None, None, None

    def add_comment_to_pr(self, comment):
        """Add a comment to the PR"""
        url = f"{self.api_url}/{self.pr_data.owner}/{self.pr_data.repo}/issues/{self.pr_data.number}/comments"
        headers = {
            "Authorization": f"Bearer {self.config.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        data = {"body": comment}
        response = requests.post(url, json=data, headers=headers)
        return response.status_code, response.json()

    def clone_repo(self, tmp_repo_dir: str):
        self.logger.info(f"[*] Cloning repository https://github.com/{self.pr_data.owner}/{self.pr_data.repo}.git")
        res = subprocess.run(
            ["git", "clone", f"https://github.com/{self.pr_data.owner}/{self.pr_data.repo}.git",
             tmp_repo_dir],
            capture_output=True, check=True)
        self.logger.info(f"[+] Cloning successful.")