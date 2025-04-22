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


class TestAmplifier:
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
        model_test_amplification: str = None,
        iAttempt: int = 0,
        prompt_combinations: dict = None,
        comment_template: str = "",
        model: str = "gpt-4o",
    ):
        self.config                   = config
        self.logger                   = logger
        self.data                     = data
        self.gh_api                   = gh_api
        self.llm_handler              = llm_handler
        self.docker_service           = docker_service
        self.log_dir                  = log_dir
        self.post_comment             = post_comment
        self.model_test_amplification = model_test_amplification
        self.iAttempt                 = iAttempt
        self.prompt_combinations      = prompt_combinations
        self.comment_template         = comment_template
        self.model                    = model

    def amplify(self) -> tuple[bool, bool]:
        """Returns (amplification_succeeded, should_run_generation)"""
        if self.data.pr_diff_ctx.has_at_least_one_test_file:
            amplification_completed = False
            self.logger.info("=============== Test Amplification Started ===============")

            # 1) run developer tests
            tests_to_run = []
            for pr_file_diff in self.data.pr_diff_ctx.test_file_diffs:
                tests_to_run += helpers.extract_test_scope(self.config.parse_language, pr_file_diff)

            test_result_dev, stdout_dev, coverage_report_dev = self.docker_service.run_test_in_container(
                self.data.pr_diff_ctx.golden_test_patch,
                tests_to_run,
                golden_code_patch=self.data.pr_diff_ctx.golden_code_patch,
            )
            if test_result_dev == "FAIL":
                self.logger.info("Developer tests failed, skipping amplification...")
                return amplification_completed, False

            # 2) log outputs
            amplification_dir = Path(self.log_dir, "amplification")
            with open(Path(amplification_dir, "dev.txt"), "w", encoding="utf-8") as f:
                f.write(stdout_dev)
            with open(Path(amplification_dir, "coverage_report_dev.txt"), "w", encoding="utf-8") as f:
                f.write(coverage_report_dev)

            # 3) compute offsets
            code_after_arr, stderr = self.data.pr_diff_ctx.apply_code_patch()
            try:
                offsets = helpers.extract_offsets_from_stderr(stderr)
            except AssertionError as e:
                self.logger.info("Different offsets in a single file for %s, skipping" % self.data.pr_data.id)
                exit(0)

            # 4) decorate patch
            missed_lines_dev, decorated_patch_dev = git_tools.get_missed_lines_and_decorate_patch(
                self.data.pr_diff_ctx,
                code_after_arr,
                offsets,
                coverage_report_dev,
            )
            self.data.patch_labeled = decorated_patch_dev

            # 5) build amplification prompt
            prompt = self.llm_handler.build_prompt(
                include_issue_description=True,
                include_golden_code=self.prompt_combinations["include_golden_code"][self.iAttempt],
                sliced=self.prompt_combinations["sliced"][self.iAttempt],
                include_issue_comments=False,
                include_pr_desc=self.prompt_combinations["include_pr_desc"][self.iAttempt],
                include_golden_test_code=True,
                test_code_sliced=self.prompt_combinations["test_code_sliced"][self.iAttempt],
                include_uncovered_lines_by_dvlpr_test=True,
            )
            with open(Path(amplification_dir, "prompt.txt"), "w", encoding="utf-8") as f:
                f.write(prompt)

            if len(prompt) >= 1048576:  # gpt4o limit (can I get it from a config or sth?)
                self.logger.info("Prompt exceeds limits, skipping...")
                raise ValueError("")

            # 6) query or mock
            if self.model_test_amplification is None:
                response = self.llm_handler.query_model(prompt, model=self.model, T=0.0)
                with open(Path(amplification_dir, "raw_model_response.txt"), "w", encoding="utf-8") as f:
                    f.write(response)
                new_test = helpers.adjust_function_indentation(
                    response.replace('```javascript', '').replace('```', '')
                )
            else:
                self.logger.info("Using mocked model response for amplification")
                new_test = self.model_test_amplification

            with open(Path(amplification_dir, "generated_test.txt"), "w", encoding="utf-8") as f:
                f.write(new_test)

            # Inject test
            most_similar_changed_func_or_class, most_similar_file, success = helpers.get_best_file_to_inject_golden(
                self.data.pr_diff_ctx,
                new_test
            )
            if success:
                if not most_similar_changed_func_or_class:
                    # it may be the case that a global variable holding parameterization values
                    # for a test was changed (see astropy__astropy-12907)
                    # In this case, append to the end
                    insert_in_block = "NOBLOCK"
                    self.logger.info("Never goes in here anymore I think")
                elif most_similar_changed_func_or_class[0] == 'function':
                    insert_in_block = "NOBLOCK"
                else:
                    insert_in_block = most_similar_changed_func_or_class[1]
            else:
                # Grab the first test file and insert at the end
                most_similar_file = [xx for xx in self.data.pr_diff_ctx.test_before if
                                     "spec" in xx.split('/')[-1] and xx.endswith('.js')][0]
                insert_in_block = "NOBLOCK"

            most_similar_file_idx = self.data.pr_diff_ctx.test_names.index(most_similar_file)
            golden_test_content = self.data.pr_diff_ctx.test_before[most_similar_file_idx]
            golden_test_content_after = self.data.pr_diff_ctx.test_after[most_similar_file_idx]

            # Add the model test on top of the developer test to measure difference
            try:
                new_test_file_contents = helpers.append_function(
                    self.config.parse_language,
                    golden_test_content_after,
                    new_test,
                    insert_in_block=insert_in_block
                )
            except:
                self.logger.info("Generated code does not compile, skipping")
                return amplification_completed, False

            model_test_patch = ""
            tests_to_run = []
            for idx, pr_file_diff in enumerate(self.data.pr_diff_ctx.test_file_diffs):
                if idx == most_similar_file_idx:
                    model_test_patch += git_tools.unified_diff(pr_file_diff.before,
                                                               new_test_file_contents,
                                                               fromfile=pr_file_diff.name,
                                                               tofile=pr_file_diff.name,
                                                               context_lines=40) + "\n"

                    this_file_tests_to_run = helpers.extract_test_scope(
                        self.config.parse_language,
                        PullRequestFileDiff(pr_file_diff.before, new_test_file_contents, pr_file_diff.name)
                    )
                else:
                    model_test_patch += git_tools.unified_diff(pr_file_diff.before,
                                                               pr_file_diff.after,
                                                               fromfile=pr_file_diff.name,
                                                               tofile=pr_file_diff.name,
                                                               context_lines=40) + "\n"
                    # we write many context lines in the file because the edited
                    # function name must appear in order for TDD-Bench to run the test

                    this_file_tests_to_run = helpers.extract_test_scope(
                        self.config.parse_language,
                        pr_file_diff
                    )

                tests_to_run += this_file_tests_to_run

            # Run developer + AI tests
            test_result_dev_and_ai, stdout_dev_and_ai, coverage_report_dev_and_ai = (
                self.docker_service.run_test_in_container(
                    model_test_patch,
                    tests_to_run,
                    golden_code_patch=self.data.pr_diff_ctx.golden_code_patch
                )
            )
            # Extract missed lines
            missed_lines_dev_and_ai, decorated_patch_dev_and_ai = git_tools.get_missed_lines_and_decorate_patch(
                self.data.pr_diff_ctx,
                code_after_arr,
                offsets,
                coverage_report_dev_and_ai
            )

            with open(Path(amplification_dir, "dev_and_ai.txt"), "w", encoding="utf-8") as f:
                f.write(stdout_dev_and_ai)
            with open(Path(amplification_dir, "coverage_report_dev_and_ai.txt"), "w", encoding="utf-8") as f:
                f.write(test_result_dev_and_ai)

            # The lines modified by the developer code patch
            modified_lines = [l[1:].strip() for l in self.data.pr_diff_ctx.golden_code_patch.splitlines() if
                              l.startswith('+') and not l.startswith('+++')]
            n_modified = len(modified_lines)
            # The lines covered by AI only
            new_lines = set(missed_lines_dev) - set(missed_lines_dev_and_ai)
            coverage_dev = (n_modified - len(set(missed_lines_dev))) / n_modified
            coverage_dev_and_ai = (n_modified - len(set(missed_lines_dev_and_ai))) / n_modified
            self.logger.info("Coverage dev: %0.2f\nCoverage dev+AI: %0.2f\n" % (coverage_dev, coverage_dev_and_ai))

            if len(new_lines) > 0 and test_result_dev_and_ai == "PASS":
                self.logger.info(
                    "These lines were missed by the developer test by covered by the AI test:\n%s" % "\n".join(
                        new_lines))

                patch_for_comment_lines = []
                for (ldev, ldevai) in zip(decorated_patch_dev.splitlines(),
                                          decorated_patch_dev_and_ai.splitlines()):
                    if ldev != ldevai:
                        patch_for_comment_lines.append(
                            ldev.replace("###NOT COVERED###", "### ✅ Only covered by above test ✅"))
                    else:
                        patch_for_comment_lines.append(ldev)
                patch_for_comment = "\n".join(patch_for_comment_lines)

                # Add a comment to the PR
                comment = self.comment_template % (new_test,
                                                   # test_filename,
                                                   "",
                                                   patch_for_comment,
                                                   coverage_dev * 100,
                                                   coverage_dev_and_ai * 100)

                if self.post_comment:
                    status_code, response_data = self.gh_api.add_comment_to_pr(comment)
                else:
                    status_code, response_data = 201, ""
                    self.logger.info("Would add this comment:\n%s\n" % comment)

                if status_code == 201:
                    self.logger.info("Comment added successfully!")
                else:
                    self.logger.info(f"Failed to add comment: {status_code}", response_data)

                amplification_completed = True
            elif test_result_dev_and_ai == "FAIL":
                self.logger.info("The AI test failed")
                amplification_completed = False
            elif len(new_lines) == 0:
                self.logger.info("No new lines covered by AI")
                amplification_completed = False

            self.logger.info("=============== Test Amplification Finished ===============")
            return amplification_completed, True
        else:
            return True, True