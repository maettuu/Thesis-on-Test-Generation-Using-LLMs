from dataclasses import dataclass

from webhook_handler.core import git_diff


@dataclass
class PullRequestFileDiff:
    """
    Wraps the before/after contents of one PR‑changed file.
    """
    name: str
    before: str
    after: str

    @property
    def is_test_file(self) -> bool:
        """
        Determines whether this PR changed file is test file or not

        Returns:
            bool: True if this PR changed file is test file, False otherwise
        """

        is_in_test_folder = False
        parts = self.name.split('/')

        # at least one folder in the dir path starts with test
        for part in parts[:-1]:
            if part.startswith('test'):
                is_in_test_folder = True
                break

        if is_in_test_folder and 'spec' in parts[-1] and parts[-1].endswith("js"):
            return True
        return False

    @property
    def is_code_file(self) -> bool:
        """
        Determines whether this PR changed code file or not

        Returns:
            bool: True if this PR changed code file is code file, False otherwise
        """

        is_in_src_folder = False
        parts = self.name.split('/')

        # at least one folder in the dir path starts with src
        for part in parts[:-1]:
            if part.startswith('src'):
                is_in_src_folder = True
                break

        if is_in_src_folder and parts[-1].endswith(".js"):
            return True
        return False

    def unified_code_diff(self) -> str:
        """
        Computes diff between before and after code files including function context.

        Returns:
            str: diff between before and after code files
        """

        return git_diff.unified_diff_with_function_context(
            self.before,
            self.after,
            f_name=self.name
        )

    def unified_test_diff(self) -> str:
        """
        Computes diff between before and after test files excluding function context.

        Returns:
            str: diff between before and after test files
        """

        return git_diff.unified_diff(
            self.before,
            self.after,
            fromfile=self.name,
            tofile=self.name
        )
