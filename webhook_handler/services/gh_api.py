import requests
import time
import re
import subprocess
import logging

from webhook_handler.core.config import Config
from webhook_handler.data_models.pr_data import PullRequestData


logger = logging.getLogger(__name__)


class GitHubApi:
    """
    Used to interact with GitHub API.
    """
    def __init__(self, config: Config, pr_data: PullRequestData):
        self._config = config
        self._pr_data = pr_data
        self._api_url = "https://api.github.com/repos"

    def fetch_pr_files(self) -> dict:
        """
        Fetches all files of a pull request.

        Returns:
            dict: All raw files
        """

        url = f"{self._api_url}/{self._pr_data.owner}/{self._pr_data.repo}/pulls/{self._pr_data.number}/files"
        response = requests.get(url, headers=self._config.headers)
        if response.status_code == 403 and "X-RateLimit-Reset" in response.headers:
            reset_time = int(response.headers["X-RateLimit-Reset"])
            wait_time = reset_time - int(time.time()) + 1
            logger.warning(f"Rate limit exceeded. Waiting for {wait_time} seconds...")
            time.sleep(max(wait_time, 1))
            return self.fetch_pr_files()

        response.raise_for_status()
        return response.json()

    def fetch_file_version(self, commit: str, file_name: str) -> str:
        """
        Fetches the version of a file at a specific commit.

        Parameters:
            commit (str): Commit hash
            file_name (str): File name

        Returns:
            str: File contents
        """

        url = f"https://raw.githubusercontent.com/{self._pr_data.owner}/{self._pr_data.repo}/{commit}/{file_name}"
        response = requests.get(url, headers=self._config.headers)
        if response.status_code == 200:
            return response.text
        return ""

    def add_comment_to_pr(self, comment) -> [int, dict]:
        """
        Adds a comment to the pull request.

        Parameters:
            comment (str): Comment to add

        Returns:
            int: Status code
            dict: The response data
        """

        url = f"{self._api_url}/{self._pr_data.owner}/{self._pr_data.repo}/issues/{self._pr_data.number}/comments"
        headers = {
            "Authorization": f"Bearer {self._config.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        data = {"body": comment}
        response = requests.post(url, json=data, headers=headers)
        return response.status_code, response.json()

    def clone_repo(self, tmp_repo_dir: str) -> None:
        """
        Clones a GitHub repository.

        Parameters:
            tmp_repo_dir (str): The directory to clone to

        Returns:
            None
        """

        logger.info(f"Cloning repository https://github.com/{self._pr_data.owner}/{self._pr_data.repo}.git")
        _ = subprocess.run(
            ["git", "clone", f"https://github.com/{self._pr_data.owner}/{self._pr_data.repo}.git",
             tmp_repo_dir],
            capture_output=True, check=True)
        logger.success(f"Cloning successful")

    def get_linked_issue(self) -> str:
        """
        Checks and fetches a linked issue.

        Returns:
            str: The linked issue title and description
        """

        issue_pattern = r'\b(?:Closes|Fixes|Resolves)\s+#(\d+)\b|\(?\b(?:bug|issue)\b\s+(\d+)\)?'
        issue_description = f"{self._pr_data.title} {self._pr_data.description}"
        matches = re.findall(issue_pattern, issue_description, re.IGNORECASE)

        for match in matches:
            issue_nr_str = match[0] or match[1]
            if not issue_nr_str: continue

            issue_nr = int(issue_nr_str)
            linked_issue_description = self._get_github_issue(issue_nr)
            if linked_issue_description:
                return linked_issue_description

            linked_issue_description = self._get_bugzilla_issue(issue_nr)
            if linked_issue_description:
                return linked_issue_description

        return ""

    def _get_github_issue(self, number: int) -> str | None:
        """
        Fetches a GitHub issue.

        Parameters:
            number (int): The number of the issue

        Returns:
            str (optional): The GitHub issue title and description
        """

        url = f"{self._api_url}/{self._pr_data.owner}/{self._pr_data.repo}/issues/{number}"
        response = requests.get(url, headers=self._config.headers)
        if response.status_code == 200:
            issue_data = response.json()
            if not "pull_request" in issue_data:
                logger.success(f"Linked GitHub issue #{number} fetched successfully")
                return "\n".join(value for value in (issue_data["title"], issue_data["body"]) if value)

        logger.warning("No GitHub issue found")
        return None

    @staticmethod
    def _get_bugzilla_issue(number: int) -> str | None:
        """
        Fetches a Bugzilla issue.

        Parameters:
            number (int): The number of the issue

        Returns:
            str (optional): The Bugzilla issue title and description
        """

        response = requests.get(f"https://bugzilla.mozilla.org/rest/bug/{number}")
        if response.status_code == 200:
            bug_data = response.json()
            if "bugs" in bug_data and bug_data["bugs"]:
                bug = bug_data["bugs"][0]
                logger.success(f"Linked Bugzilla issue #{number} fetched successfully")
                return "\n".join(value for value in (bug.get("summary", ""), bug.get("description", "")) if value)

        logger.warning(f"No Bugzilla issue found")
        return None
