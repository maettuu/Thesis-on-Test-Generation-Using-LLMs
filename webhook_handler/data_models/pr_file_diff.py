from dataclasses import dataclass

from webhook_handler.core import git_tools


@dataclass
class PullRequestFileDiff:
    """Wraps the before/after contents of one PR‑changed file."""
    name: str
    before: str
    after: str

    @property
    def is_test_file(self) -> bool:
        is_in_test_folder = False
        parts = self.name.split('/')

        # We want the file to be in a dir where at least one folder in the dir path starts with test
        for part in parts[:-1]:
            if part.startswith('test'):
                is_in_test_folder = True
                break

        if is_in_test_folder and 'spec' in parts[-1] and parts[-1].endswith("js"):
            return True
        return False

    @property
    def is_code_file(self) -> bool:
        return self.name.endswith(".js") and not self.is_test_file

    def unified_code_diff(self) -> str:
        return git_tools.unified_diff_with_function_context(
            self.before,
            self.after,
            fname=self.name
        )

    def unified_test_diff(self) -> str:
        return git_tools.unified_diff(
            self.before,
            self.after,
            fromfile=self.name,
            tofile=self.name
        )