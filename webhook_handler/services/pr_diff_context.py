import logging
import requests

from webhook_handler.data_models.pr_file_diff import PullRequestFileDiff
from webhook_handler.services.gh_api import GitHubApi


logger = logging.getLogger(__name__)


class PullRequestDiffContext:
    """
    Holds all the PullRequestFileDiffs for one PR and provides common operations.
    """
    def __init__(self, base_commit: str, head_commit: str, gh_api: GitHubApi):
        self._gh_api = gh_api
        self._pr_file_diffs = []
        raw_files = gh_api.fetch_pr_files()
        for raw_file in raw_files:
            file_name = raw_file["filename"]
            before = gh_api.fetch_file_version(base_commit, file_name)
            after  = gh_api.fetch_file_version(head_commit, file_name)
            if before != after:
                self._pr_file_diffs.append(PullRequestFileDiff(file_name, before, after))

    @property
    def source_code_file_diffs(self) -> list[PullRequestFileDiff]:
        return [pr_file_diff for pr_file_diff in self._pr_file_diffs if pr_file_diff.is_source_code_file]

    @property
    def non_source_code_file_diffs(self) -> list[PullRequestFileDiff]:
        return [pr_file_diff for pr_file_diff in self._pr_file_diffs if pr_file_diff.is_non_source_code_file]

    @property
    def test_file_diffs(self) -> list[PullRequestFileDiff]:
        return [pr_file_diff for pr_file_diff in self._pr_file_diffs if pr_file_diff.is_test_file]

    @property
    def has_at_least_one_source_code_file(self) -> bool:
        return len(self.source_code_file_diffs) > 0

    @property
    def has_at_least_one_test_file(self) -> bool:
        return len(self.test_file_diffs) > 0

    @property
    def fulfills_requirements(self) -> bool:
        return (self.has_at_least_one_source_code_file
                and not self.has_at_least_one_test_file
                and len(self.non_source_code_file_diffs) == 0)

    @property
    def code_names(self) -> list[str]:
        return [code_file_diff.name for code_file_diff in self.source_code_file_diffs]

    @property
    def code_before(self) -> list[str]:
        return [code_file_diff.before for code_file_diff in self.source_code_file_diffs]

    @property
    def code_after(self) -> list[str]:
        return [code_file_diff.after for code_file_diff in self.source_code_file_diffs]

    @property
    def test_names(self) -> list[str]:
        return [test_file_diff.name for test_file_diff in self.test_file_diffs]

    @property
    def test_before(self) -> list[str]:
        return [test_file_diff.before for test_file_diff in self.test_file_diffs]

    @property
    def test_after(self) -> list[str]:
        return [test_file_diff.after for test_file_diff in self.test_file_diffs]

    @property
    def golden_code_patch(self) -> str:
        return "\n\n".join(pr_file_diff.unified_code_diff() for pr_file_diff in self.source_code_file_diffs) + "\n\n"

    @property
    def golden_test_patch(self) -> str:
        return "\n\n".join(pr_file_diff.unified_test_diff() for pr_file_diff in self.test_file_diffs) + "\n\n"

    def get_issue_pdf(self, candidate: str, head_commit: str) -> [str, bytes]:
        """
        Returns the name and content of the linked pdf if available.

        Parameters:
            candidate (str): The name of the candidate file
            head_commit (str): The commit hash of the head

        Returns:
            str: The name of the pdf file, or empty if not available
            bytes: The content of the pdf file, or empty if not available
        """

        for pr_file_diff in self._pr_file_diffs:
            filename = pr_file_diff.name.split("/")[-1]
            if candidate in filename:
                if filename.endswith(".pdf"):
                    content = self._gh_api.fetch_file_version(head_commit, pr_file_diff.name, get_bytes=True)
                    if content:
                        logger.success("PDF file %s fetched successfully", filename)
                        return filename, content
                    logger.warning("Failed to fetch PDF file %s", filename)
                elif filename.endswith(".link"):
                    url = pr_file_diff.after.rstrip('\n')
                    pdf_filename = filename.replace(".link", "")
                    logger.info("Fetching PDF file %s", url)
                    response = requests.get(url, stream=True)
                    if response.status_code == 200:
                        logger.success("PDF file %s fetched successfully", pdf_filename)
                        return pdf_filename, response.content
                    logger.warning("Failed to fetch PDF file %s", pdf_filename)

        logger.warning("No PDF file available")
        return "", b""
