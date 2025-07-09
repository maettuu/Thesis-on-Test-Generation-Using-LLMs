import logging
import docker

from pathlib import Path
from docker.errors import ImageNotFound

from webhook_handler.core import (
    Config,
    configure_logger,
    ExecutionError,
    helpers,
    templates,
    test_injection
)
from webhook_handler.data_models import (
    LLM,
    PullRequestData,
    PipelineInputs
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
        self._environment_prepared = False
        self._setup_log_paths()

        # lazy init
        self._gh_api = None
        self._issue_statement = None
        self._pdf_candidate = None
        self._pr_diff_ctx = None
        self._pipeline_inputs = None
        self._cst_builder = None
        self._llm_handler = None
        self._docker_service = None

    def _setup_log_paths(self) -> None:
        """
        Sets up log directories, files and the logger itself.
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
        helpers.remove_dir(Path(self._config.cloned_repo_dir))

    def _teardown(self) -> None:
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

        self._gh_api = None
        self._issue_statement = None
        self._pdf_candidate = None
        self._pr_diff_ctx = None
        self._pipeline_inputs = None
        self._cst_builder = None
        self._llm_handler = None
        self._docker_service = None
        self._environment_prepared = False

    def is_valid_pr(self) -> [str, bool]:
        """
        PR must have linked issue and source code changes.

        Returns:
            str: Message to deliver to client
            bool: True if PR is valid, False otherwise
        """

        self.logger.marker("================ Preparing Environment ===============")
        self._gh_api = GitHubApi(self._config, self._pr_data)
        self._issue_statement, self._pdf_candidate = self._gh_api.get_linked_data()
        if not self._issue_statement:
            helpers.remove_dir(self._config.pr_log_dir)
            self._gh_api = None
            self._issue_statement = None
            self._pdf_candidate = None
            return 'No linked issue found', False

        self._pr_diff_ctx = PullRequestDiffContext(self._pr_data.base_commit, self._pr_data.head_commit, self._gh_api)
        if not self._pr_diff_ctx.fulfills_requirements:
            helpers.remove_dir(self._config.pr_log_dir)
            self._gh_api = None
            self._issue_statement = None
            self._pdf_candidate = None
            self._pr_diff_ctx = None
            return 'Must modify source code files only', False

        return 'Payload is being processed...', True

    def execute_pipeline(self, execute_mini: bool = False) -> bool:
        """
        Execute whole pipeline with 5 attempts per model (optional o4-mini execution).

        Parameters:
            execute_mini (bool, optional): If True, executes additional attempt with mini model

        Returns:
            bool: True if the generation was successful, False otherwise
        """

        self.logger.marker(f"=============== Running Payload #{self._pr_data.number} ===============")
        for model in [LLM.GPT4o, LLM.LLAMA, LLM.DEEPSEEK]:
            i_attempt = 0
            while i_attempt < len(self._config.prompt_combinations["include_golden_code"]) and not self._generation_completed:
                self._config.setup_output_dir(i_attempt, model)
                try:
                    self._generation_completed = self._execute_attempt(model=model, i_attempt=i_attempt)
                    self.logger.success(f"Attempt %d with model %s finished successfully" % (i_attempt + 1, model))
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
        return self._generation_completed

    def _execute_attempt(
            self,
            model: LLM,
            i_attempt: int
    ) -> bool:
        """
        Executes a single attempt.

        Parameters:
            model (LLM): Model to use
            i_attempt (int): Number of current attempt

        Returns:
            bool: True if generation was successful, False otherwise
        """

        if self._environment_prepared:
            self.logger.info("Environment ready – preparation skipped")
        else:
            self._prepare_environment()
            self._environment_prepared = True

        generator = TestGenerator(
            self._config,
            self._pipeline_inputs,
            self._mock_response,
            self._post_comment,
            templates.COMMENT_TEMPLATE,
            self._gh_api,
            self._cst_builder,
            self._docker_service,
            self._llm_handler,
            i_attempt,
            model,
        )

        return generator.generate()

    def _prepare_environment(self) -> None:
        """
        Prepares all services and data used in each attempt. Only has to execute once to cut down on API calls.
        """

        # 1. Setup GitHub API
        if self._gh_api is None:
            self.logger.marker("================ Preparing Environment ===============")
            self._gh_api = GitHubApi(self._config, self._pr_data)

        # 2. Fetch linked issue
        if self._issue_statement is None: self._issue_statement, self._pdf_candidate = self._gh_api.get_linked_data()

        # 3. Compute diffs & file contexts
        if self._pr_diff_ctx is None: self._pr_diff_ctx = PullRequestDiffContext(
            self._pr_data.base_commit,
            self._pr_data.head_commit,
            self._gh_api
        )

        # 4. Retrieve PDF
        pdf_name, pdf_content = self._pr_diff_ctx.get_issue_pdf(self._pdf_candidate, self._pr_data.head_commit)

        # 5. Slice golden code
        self._cst_builder = CSTBuilder(self._config.parse_language, self._pr_diff_ctx)
        code_sliced = self._cst_builder.slice_code_file()

        # 6. Clone repository locally
        if not Path(self._config.cloned_repo_dir).exists():
            self._gh_api.clone_repo(self._config.cloned_repo_dir)
        else:
            self.logger.info(f"Temporary repository '{self._pr_data.repo}' already cloned – skipped")

        # 7. Fetch test file for injection
        try:
            test_filename, test_file_content, test_file_content_sliced = test_injection.get_candidate_test_file(
                self._config.parse_language,
                self._pr_data.base_commit,
                self._pr_diff_ctx.golden_code_patch,
                self._config.cloned_repo_dir
            )
        except:
            self.logger.critical("Failed to determine test file for injection")
            raise ExecutionError("Failed to determine test file for injection")

        # 8. Fetch packages and imports
        try:
            available_packages = helpers.extract_packages(self._pr_data.base_commit, self._config.cloned_repo_dir)
        except:
            self.logger.warning("Failed to determine available packages")
            available_packages = ""
        try:
            available_relative_imports = helpers.extract_relative_imports(self._pr_data.base_commit,
                                                                          self._config.cloned_repo_dir)
        except:
            self.logger.warning("Failed to determine available relative imports")
            available_relative_imports = ""

        # 7. Build docker image
        self._docker_service = DockerService(
            self._config.project_root.as_posix(),
            self._config.old_repo_state,
            self._pr_data,
            pdf_name,
            pdf_content
        )
        self._docker_service.build()

        # 8. Gather pipeline data
        self._pipeline_inputs = PipelineInputs(
            pr_data=self._pr_data,
            pr_diff_ctx=self._pr_diff_ctx,
            code_sliced=code_sliced,
            problem_statement=self._issue_statement,
            pdf_name=pdf_name,
            test_filename=test_filename,
            test_file_content=test_file_content,
            test_file_content_sliced=test_file_content_sliced,
            available_packages=available_packages,
            available_relative_imports=available_relative_imports
        )

        # 9. Setup model handler
        self._llm_handler = LLMHandler(self._config, self._pipeline_inputs)

        self.logger.marker("================ Preparation Completed ===============")

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
