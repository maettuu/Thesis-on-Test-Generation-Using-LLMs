import requests

from webhook_handler.data_models.pr_file_diff import PullRequestFileDiff
from webhook_handler.services.gh_api import GitHubApi


class PullRequestDiffContext:
    """
    Holds all the PullRequestFileDiffs for one PR and provides common operations.
    """
    def __init__(self, base_commit: str, head_commit: str, gh_api: GitHubApi):
        raw_files = gh_api.fetch_pr_files()
        self._pr_file_diffs = []
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

    @property
    def golden_pdf_patch(self) -> str:
        for pr_file_diff in self._pr_file_diffs:
            filename = pr_file_diff.name.split("/")[-1]
            if filename == "test_manifest.json":
                return pr_file_diff.unified_code_diff() + "\n\n"

        return ""

    def get_issue_pdf(self, candidate: str) -> [str, str]:
        """
        Returns the name and content of the linked pdf if available.

        Parameters:
            candidate (str): The name of the candidate file

        Returns:
            str: The name of the pdf file, or empty if not available
            str: The content of the pdf file, or empty if not available
        """

        for pr_file_diff in self._pr_file_diffs:
            filename = pr_file_diff.name.split("/")[-1]
            if candidate in filename:
                if filename.endswith(".pdf"):
                    return filename, pr_file_diff.after
                elif filename.endswith(".link"):
                    url = pr_file_diff.after
                    response = requests.get(url, stream=True)
                    if response.status_code == 200:
                        return filename.replace(".link", ""), response.content

        return "", ""
