import logging
import docker

from django.http import JsonResponse
from pathlib import Path
from docker.errors import ImageNotFound

from webhook_handler.core import (
    Config,
    configure_logger,
    ExecutionError,
    helpers,
    templates,
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


class Pipeline:
    """
    In charge of executing pipeline and attempts.
    """
    def __init__(self, payload: dict, config: Config, post_comment: bool = False, mock_response: str = None):
        self._pr_data = PullRequestData.from_payload(payload)
        self._execution_id = f"pdf_js_{self._pr_data.number}"
        self._config = config
        self._post_comment = post_comment
        self._mock_response = mock_response
        self._generation_completed = False
        self._setup()

    def _setup(self):
        """
        Sets up class variables and logger.
        """

        self.executed_tests = Path(self._config.bot_log_dir, "executed_tests.txt")
        self.executed_tests.touch(exist_ok=True)
        if not Path(self._config.bot_log_dir, 'results.csv').exists():
            Path(self._config.bot_log_dir, 'results.csv').write_text(
                "{:<9},{:<30},{:<9},{:<45}\n".format("prNumber", "model", "iAttempt", "stop"),
                encoding="utf-8"
            )
        self._config.setup_pr_log_dir(self._pr_data.id)
        configure_logger(self._config.pr_log_dir, self._execution_id)
        self.logger = logging.getLogger()

    def _teardown(self):
        """
        Cleans state of directory after completion.
        """

        helpers.remove_dir(Path(self._config.cloned_repo_dir), log_success=True)
        image_tag = self._pr_data.image_tag
        try:
            client = docker.from_env()
            client.images.remove(image=f"{image_tag}:latest", force=True)
            self.logger.success(f"Removed Docker image '{image_tag}'")
        except ImageNotFound:
            self.logger.error(f"Tried to remove image '{image_tag}', but it was not found")
        except Exception as e:
            self.logger.error(f"Failed to remove Docker image '{image_tag}': {e}")
        with self.executed_tests.open("a", encoding='utf-8') as f:
            f.write(f"{self._execution_id}\n")

    def is_valid_pr(self) -> [JsonResponse, bool]:
        """
        PR must have linked issue and source code changes.

        Returns:
            JsonResponse: Message to deliver to client
            bool: True if PR is valid, False otherwise
        """
        gh_api = GitHubApi(self._config, self._pr_data)
        issue_statement = gh_api.get_linked_issue()
        if not issue_statement:
            self.logger.warning("No linked issue found")
            return JsonResponse({'status': 'success', 'message': 'No linked issue found'}, status=200), False

        pr_diff_ctx = PullRequestDiffContext(self._pr_data.base_commit, self._pr_data.head_commit, gh_api)
        if not pr_diff_ctx.fulfills_requirements:
            self.logger.warning("Must modify source code files only")
            return JsonResponse({'status': 'success', 'message': 'Must modify source code files only'}, status=200), False

        return JsonResponse({'status': 'accepted', 'message': 'Payload is being processed...'}, status=202), True


    def execute_pipeline(self, execute_mini: bool = False, return_result: bool = False) -> bool | None:
        """
        Execute whole pipeline with 5 attempts per model (optional o4-mini execution).

        Parameters:
            execute_mini (bool, optional): If True, executes additional attempt with mini model
            return_result (bool, optional): If True, returns result

        Returns:
            bool (optional): True if the generation was successful, False otherwise
        """

        self.logger.marker(f"=============== Running Payload #{self._pr_data.number} ===============")
        for model in [LLM.GPT4o, LLM.LLAMA, LLM.DEEPSEEK]:
            i_attempt = 0
            while i_attempt < len(self._config.prompt_combinations["include_golden_code"]) and not self._generation_completed:
                self._config.setup_output_dir(i_attempt, model)
                self.logger.marker("Starting combination %d with model %s" % (i_attempt + 1, model))
                try:
                    self._generation_completed = self._execute_attempt(model=model, i_attempt=i_attempt)
                    self.logger.success(f"Combination %d with model %s finished successfully" % (i_attempt + 1, model))
                    self._record_result(self._pr_data.number, model, i_attempt + 1, self._generation_completed)
                except ExecutionError as e:
                    self._record_result(self._pr_data.number, model, i_attempt + 1, str(e))
                except Exception as e:
                    self.logger.critical("Failed with unexpected error:\n%s" % e)
                    self._record_result(self._pr_data.number, model, i_attempt + 1, "unexpected error")

                i_attempt += 1

            if self._generation_completed:
                gen_test = Path(self._config.output_dir, "generation", "generated_test.txt").read_text(encoding="utf-8")
                new_filename = f"{self._execution_id}_{self._config.output_dir.name}.txt"
                Path(self._config.gen_test_dir, new_filename).write_text(gen_test, encoding="utf-8")
                self.logger.success(f"Test file copied to {self._config.gen_test_dir}/{new_filename}")
                break

        if not self._generation_completed and execute_mini:
            model = LLM.GPTo4_MINI
            self._config.setup_output_dir(0, model)
            self.logger.marker("Starting with model o4-mini")
            try:
                self._generation_completed = self._execute_attempt(
                    model=model,
                    i_attempt=0
                )
                self.logger.success("o4-mini finished successfully")
                self._record_result(self._pr_data.number, model, 1, self._generation_completed)
            except ExecutionError as e:
                self._record_result(self._pr_data.number, model, 1, str(e))
            except Exception as e:
                self.logger.critical("Failed with unexpected error:\n%s" % e)
                self._record_result(self._pr_data.number, model, 1, "unexpected error")

            if self._generation_completed:
                gen_test = Path(self._config.output_dir, "generation", "generated_test.txt").read_text(encoding="utf-8")
                new_filename = f"{self._execution_id}_{self._config.output_dir.name}.txt"
                Path(self._config.gen_test_dir, new_filename).write_text(gen_test, encoding="utf-8")
                self.logger.success(f"Test file copied to {self._config.gen_test_dir}/{new_filename}")

        self.logger.marker(f"=============== Finished Payload #{self._pr_data.number} ===============")
        self._teardown()
        if return_result: return self._generation_completed

    def _execute_attempt(
            self,
            mock_response: str = None,
            i_attempt: int = 0,
            model: LLM = LLM.GPT4o
    ) -> bool:
        """
        Executes a single attempt.

        Parameters:
            mock_response (str): Mock response for LLM to prevent new query
            i_attempt (int): Number of current attempt
            model (LLM): Model to use

        Returns:
            bool: True if generation was successful, False otherwise
        """

        # 1. Setup GitHub Api
        gh_api = GitHubApi(self._config, self._pr_data)

        # 2. Fetch linked Issue
        issue_statement = gh_api.get_linked_issue()

        # 3. Compute diffs & file contexts
        pr_diff_ctx = PullRequestDiffContext(self._pr_data.base_commit, self._pr_data.head_commit, gh_api)

        # 4. Slice golden code
        cst_builder = CSTBuilder(self._config.parse_language, pr_diff_ctx)
        code_sliced = cst_builder.slice_code_file()

        # 5. Build Docker image
        docker_service = DockerService(self._config.project_root.as_posix(), self._config.old_repo_state, self._pr_data)
        docker_service.build()

        # 6. Gather pipeline data
        pr_pipeline_data = PullRequestPipelineData(
            pr_data=self._pr_data,
            pr_diff_ctx=pr_diff_ctx,
            code_sliced=code_sliced,
            problem_statement=issue_statement
        )

        # 7. Setup Model Handler
        llm_handler = LLMHandler(self._config, pr_pipeline_data)

        # 8. Setup Generator
        generator = TestGenerator(
            self._config,
            pr_pipeline_data,
            cst_builder,
            gh_api,
            llm_handler,
            docker_service,
            self._post_comment,
            i_attempt,
            self._config.prompt_combinations,
            templates.COMMENT_TEMPLATE_GENERATION,
            model,
            mock_response
        )

        # 9. Execute
        return generator.generate()

    def _record_result(self, number: str, model: LLM, i_attempt: int, stop: bool | str):
        """
        Writes result to csv.

        Parameters:
            number (str): The number of the PR
            model (LLM): The model
            i_attempt (int): The attempt number
            stop (bool, str): The stop flag or an error string
        """

        with open(Path(self._config.bot_log_dir, 'results.csv'), 'a') as f:
            f.write(
                "{:<9},{:<30},{:<9},{:<45}\n".format(number, model, i_attempt, stop)
            )
