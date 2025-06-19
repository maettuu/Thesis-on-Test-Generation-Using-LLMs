from scrape_handler.core import (
    Config,
    templates
)
from scrape_handler.data_models import PullRequestPipelineData
from scrape_handler.services import (
    DockerService,
    GoldenFileSlicer,
    GitHubApi,
    LLMHandler,
    PullRequestDiffContext,
    TestAmplifier,
    TestGenerator
)


def run(
        pr_data,
        config: Config,
        logger,
        log_dir,
        dockerfile=None,
        model_test_generation=None,
        model_test_amplification=None,
        iAttempt=0,
        post_comment=False,
        model="gpt-4o"
):
    # 1. Setup GitHub Api
    gh_api = GitHubApi(config, pr_data, logger)

    # 2. Check for linked GitHub Issues
    issue_statement = gh_api.get_full_statement()
    if not issue_statement:
        return {'status': 'success', 'message': 'Pull request opened, but no linked issue found'}, True

    # 3. Compute diffs & file contexts
    pr_diff_ctx = PullRequestDiffContext(pr_data, gh_api)
    if not pr_diff_ctx.has_at_least_one_code_file:  # if the PR changed only non-javascript files return
        logger.info("No .js code files (except maybe for test) were modified, skipping")
        return {'status': 'success', 'message': 'Pull request opened, linked issue found, but no .js file modified'}, True

    # 4. Slice golden code + tests
    file_slicer = GoldenFileSlicer(config, pr_diff_ctx)
    code_sliced, test_sliced = file_slicer.slice_all()

    # 5. Build Docker image
    docker_service = DockerService(config, pr_data, logger, dockerfile)
    docker_service.build()

    # 6. Gather pipeline data
    pr_pipeline_data = PullRequestPipelineData(
        pr_data=pr_data,
        pr_diff_ctx=pr_diff_ctx,
        code_sliced=code_sliced,
        test_sliced=test_sliced,
        problem_statement=issue_statement,
        hints_text=""
    )

    # 7. Setup Model Handler
    llm_handler = LLMHandler(config, pr_pipeline_data)

    # 8. Amplification & Generation
    amplifier = TestAmplifier(
        config,
        logger,
        pr_pipeline_data,
        gh_api,
        llm_handler,
        docker_service,
        log_dir,
        post_comment,
        model_test_amplification,
        iAttempt,
        config.prompt_combinations_ampl,
        templates.COMMENT_TEMPLATE_AMPLIFICATION,
        model
    )
    generator = TestGenerator(
        config,
        logger,
        pr_pipeline_data,
        gh_api,
        llm_handler,
        docker_service,
        log_dir,
        post_comment,
        model_test_generation,
        iAttempt,
        config.prompt_combinations_gen,
        templates.COMMENT_TEMPLATE_GENERATION,
        model
    )

    # ampl_ok, go_to_gen = amplifier.amplify()
    # gen_ok = generator.generate(go_to_gen)

    # 9. Whether to stop or try again with different prompt inputs
    # stop = (pr_diff_ctx.has_at_least_one_test_file and ampl_ok) or (not pr_diff_ctx.has_at_least_one_test_file and gen_ok)
    # return JsonResponse({'status': 'success', 'message': 'Execution completed successfully'}, status=200), stop

    return {'status': 'success', 'message': 'Execution completed successfully'}, generator.generate(True)
