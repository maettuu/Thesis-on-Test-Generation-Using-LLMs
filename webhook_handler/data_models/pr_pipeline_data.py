from dataclasses import dataclass


@dataclass
class PullRequestPipelineData:
    """Holds all data about a PR, its diffs together with the sliced code."""
    pr_data: any
    pr_diff_ctx: any
    code_sliced: list[str]
    test_sliced: list[str]
    problem_statement: str
    hints_text: str
    predicted_test_sliced: list[str] = None
    patch_labeled: str = None

    def __post_init__(self):
        # ensure description is never None
        if self.hints_text is None:
            self.hints_text = ""
        # ensure instance types
        from webhook_handler.data_models.pr_data import PullRequestData
        assert isinstance(self.pr_data, PullRequestData)
        from webhook_handler.services.pr_diff_context import PullRequestDiffContext
        assert isinstance(self.pr_diff_ctx, PullRequestDiffContext)
