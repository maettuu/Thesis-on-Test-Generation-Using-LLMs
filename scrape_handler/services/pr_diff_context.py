from scrape_handler.core import git_tools
from scrape_handler.data_models.pr_data import PullRequestData
from scrape_handler.data_models.pr_file_diff import PullRequestFileDiff
from scrape_handler.services.gh_api import GitHubApi


class PullRequestDiffContext:
    """Holds all the PullRequestFileDiffs for one PR and provides common operations."""
    def __init__(self, pr_data: PullRequestData, gh_api: GitHubApi):
        # 1. fetch the list of file‐dicts
        raw_files = gh_api.fetch_pr_files()

        # 2. wrap each into PullRequestFileDiff (fetching before/after content)
        self.pr_file_diffs = []
        for raw_file in raw_files:
            file_name = raw_file["filename"]
            before = gh_api.fetch_file_version(pr_data.base_commit, file_name)
            after  = gh_api.fetch_file_version(pr_data.head_commit, file_name)
            if before != after:
                self.pr_file_diffs.append(PullRequestFileDiff(file_name, before, after))

    @property
    def code_file_diffs(self) -> list[PullRequestFileDiff]:
        return [pr_file_diff for pr_file_diff in self.pr_file_diffs if pr_file_diff.is_code_file]

    @property
    def test_file_diffs(self) -> list[PullRequestFileDiff]:
        return [pr_file_diff for pr_file_diff in self.pr_file_diffs if pr_file_diff.is_test_file]

    @property
    def has_at_least_one_code_file(self) -> bool:
        return len(self.code_file_diffs) > 0

    @property
    def has_at_least_one_test_file(self) -> bool:
        return len(self.test_file_diffs) > 0

    @property
    def code_names(self) -> list[str]:
        return [code_file_diff.name for code_file_diff in self.code_file_diffs]

    @property
    def code_before(self) -> list[str]:
        return [code_file_diff.before for code_file_diff in self.code_file_diffs]

    @property
    def code_after(self) -> list[str]:
        return [code_file_diff.after for code_file_diff in self.code_file_diffs]

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
        # join with double‑newline so each file’s context is clear
        return "\n\n".join(pr_file_diff.unified_code_diff() for pr_file_diff in self.code_file_diffs) + "\n\n"

    @property
    def golden_test_patch(self) -> str:
        return "\n\n".join(pr_file_diff.unified_test_diff() for pr_file_diff in self.test_file_diffs) + "\n\n"

    def apply_code_patch(self):
        return git_tools.apply_patch(self.code_before, self.golden_code_patch)
