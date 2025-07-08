from dataclasses import dataclass


@dataclass
class PullRequestPipelineData:
    """
    Holds all data about a PR, its diffs together with the sliced code.
    """
    pr_data: any
    pr_diff_ctx: any
    code_sliced: list[str]
    problem_statement: str
    pdf_name: str

    def __post_init__(self):
        # ensure instance types
        from webhook_handler.data_models.pr_data import PullRequestData
        assert isinstance(self.pr_data, PullRequestData)
        from webhook_handler.services.pr_diff_context import PullRequestDiffContext
        assert isinstance(self.pr_diff_ctx, PullRequestDiffContext)
