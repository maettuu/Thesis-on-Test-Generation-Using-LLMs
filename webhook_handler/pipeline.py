import logging

from webhook_handler.core import (
    Config,
    templates
)
from webhook_handler.data_models import (
    LLM,
    PullRequestData,
    PullRequestPipelineData
)
from webhook_handler.services import (
    CSTBuilder,
    DockerService,
    GitHubApi,
    LLMHandler,
    PullRequestDiffContext,
    TestGenerator
)


logger = logging.getLogger(__name__)


def run(
        pr_data: PullRequestData,
        config: Config,
        mock_response: str = None,
        i_attempt: int = 0,
        post_comment: bool = False,
        model: LLM = LLM.GPT4o
):
    # 1. Setup GitHub Api
    gh_api = GitHubApi(config, pr_data)

    # 2. Check for linked GitHub Issues
    issue_statement = gh_api.get_linked_issue()
    if not issue_statement:
        logger.warning("No linked issue found")
        return {'status': 'success', 'message': 'Pull request opened, but no linked issue found'}, True

    # 3. Compute diffs & file contexts
    pr_diff_ctx = PullRequestDiffContext(pr_data.base_commit, pr_data.head_commit, gh_api)
    if not pr_diff_ctx.has_at_least_one_code_file:
        logger.warning("No modified source code files")
        return {'status': 'success', 'message': 'Pull request opened, linked issue found, but no modified source code files'}, True

    # 4. Slice golden code
    cst_builder = CSTBuilder(config.parse_language, pr_diff_ctx)
    code_sliced = cst_builder.slice_code_file()

    # 5. Build Docker image
    docker_service = DockerService(config.project_root.as_posix(), config.old_repo_state, pr_data)
    docker_service.build()

    # 6. Gather pipeline data
    pr_pipeline_data = PullRequestPipelineData(
        pr_data=pr_data,
        pr_diff_ctx=pr_diff_ctx,
        code_sliced=code_sliced,
        problem_statement=issue_statement
    )

    # 7. Setup Model Handler
    llm_handler = LLMHandler(config, pr_pipeline_data)

    # 8. Generation
    generator = TestGenerator(
        config,
        pr_pipeline_data,
        cst_builder,
        gh_api,
        llm_handler,
        docker_service,
        post_comment,
        i_attempt,
        config.prompt_combinations,
        templates.COMMENT_TEMPLATE_GENERATION,
        model,
        mock_response
    )

    return {'status': 'success', 'message': 'Execution completed successfully'}, generator.generate()
