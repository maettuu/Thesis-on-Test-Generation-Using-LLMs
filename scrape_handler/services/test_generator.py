import logging

from pathlib import Path

from scrape_handler.core.config import Config
from scrape_handler.core import (
    ExecutionError,
    git_diff,
    helpers
)
from scrape_handler.data_models.llm_enum import LLM
from scrape_handler.data_models.pr_file_diff import PullRequestFileDiff
from scrape_handler.data_models.pr_pipeline_data import PullRequestPipelineData
from scrape_handler.services.cst_builder import CSTBuilder
from scrape_handler.services.docker_service import DockerService
from scrape_handler.services.gh_api import GitHubApi
from scrape_handler.services.llm_handler import LLMHandler


logger = logging.getLogger(__name__)


class TestGenerator:
    """
    Runs a full pipeline to generate a test using a LLM and then verifying its correctness.
    """
    def __init__(
        self,
        config: Config,
        data: PullRequestPipelineData,
        gh_api: GitHubApi,
        llm_handler: LLMHandler,
        docker_service: DockerService,
        post_comment: bool,
        i_attempt: int,
        prompt_combinations: dict,
        comment_template: str,
        model: LLM,
        mock_response: str = None,
    ):
        self._config                = config
        self._pr_data               = data.pr_data
        self._pr_diff_ctx           = data.pr_diff_ctx
        self._gh_api                = gh_api
        self._llm_handler           = llm_handler
        self._docker_service        = docker_service
        self._post_comment          = post_comment
        self._mock_response         = mock_response
        self._i_attempt             = i_attempt
        self._prompt_combinations   = prompt_combinations
        self._comment_template      = comment_template
        self._model                 = model

    def generate(self) -> bool:
        """
        Runs the pipeline to generate a fail-to-pass test.
        """

        logger.marker("=============== Test Generation Started ===============")
        tmp_repo_dir = self._config.cloned_repo_dir
        if not Path(tmp_repo_dir).exists():
            self._gh_api.clone_repo(tmp_repo_dir)
        else:
            logger.info(f"Temporary repository '{self._pr_data.repo}' already cloned – skipped")
        try:
            test_filename, test_file_content, test_file_content_sliced = helpers.get_contents_of_test_file_to_inject(
                self._config.parse_language,
                self._pr_data.base_commit,
                self._pr_diff_ctx.golden_code_patch,
                tmp_repo_dir
            )
            test_filename = test_filename.replace(tmp_repo_dir + '/', '')
        except:
            logger.critical(f'Failed to determine test file for injection')
            raise ExecutionError(f'Failed to determine test file for injection')
        try:
            available_packages = helpers.extract_packages(self._pr_data.base_commit, tmp_repo_dir)
        except:
            logger.warning(f'Failed to determine available packages')
            available_packages = ""
        try:
            available_relative_imports = helpers.extract_relative_imports(self._pr_data.base_commit, tmp_repo_dir)
        except:
            logger.warning(f'Failed to determine available relative imports')
            available_relative_imports = ""

        include_golden_code = self._prompt_combinations["include_golden_code"][self._i_attempt]
        sliced = self._prompt_combinations["sliced"][self._i_attempt]
        include_pr_desc = self._prompt_combinations["include_pr_desc"][self._i_attempt]
        include_predicted_test_file = self._prompt_combinations["include_predicted_test_file"][self._i_attempt]
        prompt = self._llm_handler.build_prompt(
            include_golden_code,
            sliced,
            include_pr_desc,
            include_predicted_test_file,
            test_filename,
            test_file_content_sliced,
            available_packages,
            available_relative_imports
        )

        if len(prompt) >= 1048576:  # gpt4o limit
            logger.critical("Prompt exceeds limits, skipping...")
            raise ExecutionError("Prompt is too long.")

        generation_dir = Path(self._config.output_dir, "generation")
        (generation_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

        if self._mock_response is None:
            logger.info("Querying LLM...")
            response = self._llm_handler.query_model(prompt, model=self._model, temperature=0.0)
            if not response:
                logger.critical("Failed to query model")
                raise ExecutionError('Failed to query model')

            logger.success("LLM response received")
            (generation_dir / "raw_model_response.txt").write_text(response, encoding="utf-8")
            new_test = self._llm_handler.postprocess_response(response)
        else:
            new_test = self._mock_response

        (generation_dir / "generated_test.txt").write_text(new_test, encoding="utf-8")
        new_test = new_test.replace('src/', '')  # temporary replacement to run in lib-legacy

        cts_builder = CSTBuilder(self._config.parse_language)

        if test_file_content:
            new_test_file_content = cts_builder.append_function(
                test_file_content,
                new_test
            )
        else:
            new_test_file_content = new_test

        model_test_patch = git_diff.unified_diff(
            test_file_content,
            new_test_file_content,
            fromfile=test_filename,
            tofile=test_filename
        ) + "\n\n"

        test_file_diff = PullRequestFileDiff(test_filename, test_file_content, new_test_file_content)

        test_to_run = cts_builder.extract_changed_tests(test_file_diff)

        ################### Run test in pre-PR codebase ##################
        test_passed_before, stdout_before = self._docker_service.run_test_in_container(
            model_test_patch,
            test_to_run,
            test_file_diff.name
        )
        (generation_dir / "before.txt").write_text(stdout_before, encoding="utf-8")
        new_test_file = f"#{test_filename}\n{new_test_file_content}" if test_file_content else f"#{test_filename}\n{new_test}"
        (generation_dir / "new_test_file_content.js").write_text(new_test_file, encoding="utf-8")

        if test_passed_before:
            logger.fail("No Fail-to-Pass test generated")
            logger.marker("=============== Test Generation Finished ===============")
            return False

        ################### Run test in post-PR codebase ##################
        golden_code_patch = self._pr_diff_ctx.golden_code_patch
        test_passed_after, stdout_after = self._docker_service.run_test_in_container(
            model_test_patch,
            test_to_run,
            test_file_diff.name,
            golden_code_patch=golden_code_patch
        )
        (generation_dir / "after.txt").write_text(stdout_after, encoding="utf-8")

        if not test_passed_before and test_passed_after:
            logger.success("Fail-to-Pass test generated")
            comment = self._comment_template % (
                (generation_dir / "generated_test.txt").read_text(encoding="utf-8"),
                test_filename
            )
            if self._post_comment:
                # status_code, response_data = self.gh_api.add_comment_to_pr(comment)
                # if status_code == 201:
                #     logger.success("Comment added successfully")
                # else:
                #     logger.fail(f"Failed to add comment: {status_code}", response_data)
                pass
            else:
                logger.success("Suggested test for PR:\n\n%s" % comment)
            logger.marker("=============== Test Generation Finished ===============")
            return True
        else:
            logger.fail("No Fail-to-Pass test generated")
            logger.marker("=============== Test Generation Finished ===============")
            return False
