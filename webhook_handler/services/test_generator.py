from pathlib import Path

from webhook_handler.core.config import Config
from webhook_handler.core import (
    git_tools,
    helpers
)
from webhook_handler.data_models.pr_file_diff import PullRequestFileDiff
from webhook_handler.data_models.pr_pipeline_data import PullRequestPipelineData
from webhook_handler.services.docker_service import DockerService
from webhook_handler.services.gh_api import GitHubApi
from webhook_handler.services.llm_handler import LLMHandler


class TestGenerator:
    def __init__(
        self,
        config: Config,
        logger,
        data: PullRequestPipelineData,
        gh_api: GitHubApi,
        llm_handler: LLMHandler,
        docker_service: DockerService,
        log_dir: Path,
        post_comment: bool,
        model_test_generation: str = None,
        iAttempt: int = 0,
        prompt_combinations: dict = None,
        comment_template: str = "",
        model: str = "gpt-4o",
    ):
        self.config                = config
        self.logger                = logger
        self.pr_data               = data.pr_data
        self.pr_diff_ctx           = data.pr_diff_ctx
        self.gh_api                = gh_api
        self.llm_handler           = llm_handler
        self.docker_service        = docker_service
        self.log_dir               = log_dir
        self.post_comment          = post_comment
        self.model_test_generation = model_test_generation
        self.iAttempt              = iAttempt
        self.prompt_combinations   = prompt_combinations
        self.comment_template      = comment_template
        self.model                 = model

    def generate(self, go_to_gen: bool) -> bool:
        if not go_to_gen:
            self.logger.info("Test Generation aborted.")
            return False

        self.logger.info("=============== Test Generation Started ===============")
        generation_completed = False

        # Calculate temporal coupling to find where to inject the test
        tmp_repo_dir = "tmp_repo_dir"
        if not Path(tmp_repo_dir).exists():
            self.gh_api.clone_repo(tmp_repo_dir)
        else:
            self.logger.info(f"[+] Temporary repository '{self.pr_data.repo}' already cloned – skipped")
        try:
            test_filename, test_file_content, test_file_content_sliced = helpers.get_contents_of_test_file_to_inject(
                self.config.parse_language,
                self.pr_data.base_commit,
                self.pr_diff_ctx.golden_code_patch,
                self.pr_data.id,
                tmp_repo_dir
            )
            test_filename = test_filename.replace(tmp_repo_dir + '/', '')
        finally:
            helpers.remove_dir(Path(tmp_repo_dir))

        # Build prompt
        include_issue_description = True
        include_golden_code = self.prompt_combinations["include_golden_code"][self.iAttempt]
        sliced = self.prompt_combinations["sliced"][self.iAttempt]
        include_issue_comments = False
        include_pr_desc = self.prompt_combinations["include_pr_desc"][self.iAttempt]
        include_predicted_test_file = self.prompt_combinations["include_predicted_test_file"][self.iAttempt]
        prompt = self.llm_handler.build_prompt(
            include_issue_description=include_issue_description,
            include_golden_code=include_golden_code,
            sliced=sliced,
            include_issue_comments=include_issue_comments,
            include_pr_desc=include_pr_desc,
            include_predicted_test_file=include_predicted_test_file,
            test_file_content=test_file_content_sliced
        )

        if len(prompt) >= 1048576:  # gpt4o limit
            self.logger.info("Prompt exceeds limits, skipping...")
            raise ValueError("")

        generation_dir = Path(self.log_dir, "generation")
        with open(Path(generation_dir, "prompt.txt"), "w", encoding="utf-8") as f:
            f.write(prompt)

        if self.model_test_generation is None:  # if not mock, query model
            # Query model
            # model = "o1-2024-12-17"
            T = 0.0
            response = self.llm_handler.query_model(prompt, model=self.model, T=T)

            new_test = helpers.adjust_function_indentation(
                response.removeprefix('```javascript').replace('```', '').lstrip('\n')
            )  # TODO: Required for Javascript?

            with open(Path(generation_dir, "raw_model_response.txt"), "w", encoding="utf-8") as f:
                f.write(response)
        else:
            new_test = self.model_test_generation

        with open(Path(generation_dir, "generated_test.txt"), "w", encoding="utf-8") as f:
            f.write(new_test)

        # Append generated test to existing test file
        if test_file_content:
            new_test_file_content = helpers.append_function(
                self.config.parse_language,
                test_file_content,
                new_test,
                insert_in_block="NOBLOCK"
            )
        else:
            new_test_file_content = new_test

        # Construct test patch
        model_test_patch = git_tools.unified_diff(
            test_file_content,
            new_test_file_content,
            fromfile=test_filename,
            tofile=test_filename
        ) + "\n"

        test_file_diff = PullRequestFileDiff(test_filename, test_file_content, new_test_file_content)

        test_to_run = helpers.extract_test_descriptions(
            self.config.parse_language,
            test_file_diff
        )

        #### Run test in pre-PR codebase
        test_result_before, stdout_before, coverage_report_before = self.docker_service.run_test_in_container(
            model_test_patch,
            test_to_run,
            test_file_diff
        )
        with open(Path(generation_dir, "before.txt"), "w", encoding="utf-8") as f:
            f.write(stdout_before)
        with open(Path(generation_dir, "coverage_report_before.txt"), "w", encoding="utf-8") as f:
            f.write(coverage_report_before)
        with open(Path(generation_dir, "new_test_file_content.js"), "w", encoding="utf-8") as f:
            if test_file_content:
                f.write("#%s\n%s" % (test_filename, new_test_file_content))
            else:
                f.write("#%s\n%s" % (test_filename, new_test))

        #### Run test in post-PR codebase
        golden_code_patch = self.pr_diff_ctx.golden_code_patch
        test_result_after, stdout_after, coverage_report_after = self.docker_service.run_test_in_container(
            model_test_patch,
            test_to_run,
            test_file_diff,
            golden_code_patch=golden_code_patch
        )
        with open(Path(generation_dir, "after.txt"), "w", encoding="utf-8") as f:
            f.write(stdout_after)
        with open(Path(generation_dir, "coverage_report_after.txt"), "w", encoding="utf-8") as f:
            f.write(coverage_report_after)

        isFail2Pass = (test_result_before == "FAIL") and (test_result_after == "PASS")

        code_after_arr, stderr = self.pr_diff_ctx.apply_code_patch()
        try:
            offsets = helpers.extract_offsets_from_stderr(stderr)
        except AssertionError as e:
            self.logger.info("Different offsets in a single file for %s, skipping" % self.pr_data.id)
            exit(0)

        if isFail2Pass:
            missed_lines, decorated_patch = git_tools.get_missed_lines_and_decorate_patch(
                self.pr_diff_ctx,
                code_after_arr,
                offsets,
                coverage_report_after
            )

            decorated_patch_new_lines = []
            for ln in decorated_patch.splitlines():
                if "###NOT COVERED###" in ln:
                    new_line = ln.replace("###NOT COVERED###", "")
                elif ln.startswith("+") and not ln.startswith("+++"):
                    new_line = ln + "# ✅ Covered by above test"
                else:
                    new_line = ln
                decorated_patch_new_lines.append(new_line)
            decorated_patch_new = "\n".join(decorated_patch_new_lines)

            # Calculate patch coverage
            modified_lines = [
                l[1:].strip() for l in golden_code_patch.splitlines() if
                l.startswith('+') and not l.startswith('+++')
            ]
            n_modified = len(modified_lines)
            patch_coverage = (n_modified - len(missed_lines)) / n_modified

            # Add comment to the PR
            comment = self.comment_template % (new_test,
                                               test_filename,
                                               decorated_patch_new,
                                               patch_coverage * 100)
            # If the task was amplification, we don't post a comment upon successful
            # generation, we just run it to benchmark our pipeline
            if self.post_comment and not self.pr_diff_ctx.has_at_least_one_test_file:
                status_code, response_data = self.gh_api.add_comment_to_pr(comment)
            else:
                status_code, response_data = 201, ""
                self.logger.info("Debugging: would add this comment to PR:\n%s\n" % comment)

            if status_code == 201:
                self.logger.info("Comment added successfully!")
            else:
                self.logger.info(f"Failed to add comment: {status_code}", response_data)

            generation_completed = True
        elif not isFail2Pass:
            self.logger.info("No Fail-to-Pass test generated")
            generation_completed = False

        self.logger.info("=============== Test Generation Finished ===============")
        return generation_completed
