import os
import json
import docker
import logging

from django.test import TestCase
from pathlib import Path
from docker.errors import ImageNotFound

from webhook_handler.core import (
    Config,
    configure_logger,
    ExecutionError,
    helpers
)
from webhook_handler.pipeline import run
from webhook_handler.data_models import LLM
from webhook_handler.data_models import PullRequestData


logger = logging.getLogger(__name__)


class RunHelper:
    def __init__(
            self,
            payload_path: str,
            config: Config,
            execution_id: str,
            mock_response_path: str = None,
            run_all_models: bool = False
    ):
        self.payload = self._get_payload(payload_path)
        self.config = config
        self.execution_id = execution_id
        self.mock_response = self._get_file_content(mock_response_path)
        self.run_all_models = run_all_models
        self.pr_data = None

    @staticmethod
    def _get_payload(rel_path: str) -> dict:
        abs_path = os.path.join(os.path.dirname(__file__), rel_path)
        with open(abs_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload

    @staticmethod
    def _get_file_content(rel_path: str) -> str | None:
        if not rel_path:
            return None
        abs_path = os.path.join(os.path.dirname(__file__), rel_path)
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content

    def record_result(self, number, model, i_attempt, stop):
        with open(Path(self.config.bot_log_dir, 'results.csv'), 'a') as f:
            f.write(
                "{:<9},{:<30},{:<9},{:<45}\n".format(number, model, i_attempt, stop)
            )

    def run_payload(self):
        stop = False
        self.pr_data = PullRequestData.from_payload(self.payload)
        self.config.setup_pr_log_dir(self.pr_data.id)
        configure_logger(self.config.pr_log_dir, self.execution_id)
        logger.marker(f"=============== Running Payload #{self.pr_data.number} ===============")
        if not Path(self.config.bot_log_dir, 'results.csv').exists():
            Path(self.config.bot_log_dir, 'results.csv').write_text(
                "{:<9},{:<30},{:<9},{:<45}\n".format("prNumber", "model", "iAttempt", "stop"),
                encoding="utf-8"
            )

        models = [LLM.GPT4o, LLM.LLAMA, LLM.DEEPSEEK]
        response = None
        for model in models:
            i_attempt = 0
            while i_attempt < len(self.config.prompt_combinations["include_golden_code"]) and (not stop or self.run_all_models):
                self.config.setup_output_dir(i_attempt, model)
                logger.marker("Starting combination %d with model %s" % (i_attempt + 1, model))
                try:
                    response, stop = run(self.pr_data,
                                         self.config,
                                         model=model,
                                         mock_response=self.mock_response,
                                         i_attempt=i_attempt,
                                         post_comment=False)
                    logger.success(f"Combination %d with model %s finished successfully" % (i_attempt + 1, model))
                    self.record_result(self.payload["number"], model, i_attempt + 1, stop)
                except ExecutionError as e:
                    self.record_result(self.payload["number"], model, i_attempt + 1, str(e))
                except Exception as e:
                    logger.critical("Failed with unexpected error:\n%s" % e)
                    self.record_result(self.payload["number"], model, i_attempt + 1, "unexpected error")

                if stop:
                    gen_test = Path(self.config.output_dir, "generation", "generated_test.txt").read_text(
                        encoding="utf-8")
                    new_filename = f"{self.execution_id}_{self.config.output_dir.name}.txt"
                    Path(self.config.gen_test_dir, new_filename).write_text(gen_test, encoding="utf-8")
                    logger.success(f"Test file copied to {self.config.gen_test_dir}/{new_filename}")

                i_attempt += 1

        # if not stop:
        #     model = LLM.GPTo4_MINI
        #     self.config.setup_output_dir(0, model)
        #     logger.marker("Starting with model o4-mini")
        #     try:
        #         response, stop = run(self.pr_data,
        #                              self.config,
        #                              model=model,
        #                              i_attempt=0,
        #                              post_comment=False)
        #         logger.success("o4-mini finished successfully")
        #         self.record_result(self.payload["number"], model, 1, stop)
        #     except ExecutionError as e:
        #         self.record_result(self.payload["number"], model, 1, str(e))
        #     except Exception as e:
        #         logger.critical("Failed with unexpected error:\n%s" % e)
        #         self.record_result(self.payload["number"], model, 1, "unexpected error")
        #
        #     if stop:
        #         gen_test = Path(self.config.output_dir, "generation", "generated_test.txt").read_text(encoding="utf-8")
        #         new_filename = f"{self.execution_id}_{self.config.output_dir.name}.txt"
        #         Path(self.config.gen_test_dir, new_filename).write_text(gen_test, encoding="utf-8")
        #         logger.success(f"Test file copied to {self.config.gen_test_dir}/{new_filename}")

        logger.marker(f"=============== Finished Payload #{self.pr_data.number} ===============")
        return response

    def cleanup(self):
        helpers.remove_dir(Path(self.config.cloned_repo_dir), log_success=True)
        image_tag = f"image_{self.pr_data.image_tag}:latest"
        try:
            client = docker.from_env()
            client.images.remove(image=image_tag, force=True)
            logger.success(f"Removed Docker image '{image_tag}'")
        except ImageNotFound:
            logger.error(f"Tried to remove image '{image_tag}', but it was not found")
        except Exception as e:
            logger.error(f"Failed to remove Docker image '{image_tag}': {e}")
        with EXECUTED_TESTS.open("a", encoding='utf-8') as f:
            f.write(f"{self.execution_id}\n")

EXECUTED_TESTS = Path("executed_tests.txt")

#
# RUN With: python manage.py test webhook_handler.test.<filename>.<testname>
#
class TestGenerationPdfJs19849(TestCase):
    def setUp(self):
        global EXECUTED_TESTS
        mock_file = Path("test_mocks", "pdf_js_19849.json")
        execution_id = mock_file.stem
        self.config = Config()
        helpers.remove_dir(Path(self.config.cloned_repo_dir))
        EXECUTED_TESTS = Path(self.config.bot_log_dir, "executed_tests.txt")
        EXECUTED_TESTS.touch(exist_ok=True)
        self.helper = RunHelper(payload_path=str(mock_file), config=self.config, execution_id=execution_id)

    def tearDown(self):
        global EXECUTED_TESTS
        EXECUTED_TESTS = Path("executed_tests.txt")
        self.helper.cleanup()
        del self.config
        del self.helper

    def test_generation_pdf_js_16275(self):
        response = self.helper.run_payload()
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse


class TestGenerationPdfJs19880(TestCase):
    def setUp(self):
        global EXECUTED_TESTS
        mock_file = Path("test_mocks", "pdf_js_19880.json")
        execution_id = mock_file.stem
        self.config = Config()
        helpers.remove_dir(Path(self.config.cloned_repo_dir))
        EXECUTED_TESTS = Path(self.config.bot_log_dir, "executed_tests.txt")
        EXECUTED_TESTS.touch(exist_ok=True)
        self.helper = RunHelper(payload_path=str(mock_file), config=self.config, execution_id=execution_id)

    def tearDown(self):
        global EXECUTED_TESTS
        EXECUTED_TESTS = Path("executed_tests.txt")
        self.helper.cleanup()
        del self.config
        del self.helper

    def test_generation_pdf_js_16275(self):
        response = self.helper.run_payload()
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse


class TestGenerationPdfJs19918(TestCase):
    def setUp(self):
        global EXECUTED_TESTS
        mock_file = Path("test_mocks", "pdf_js_19918.json")
        execution_id = mock_file.stem
        self.config = Config()
        helpers.remove_dir(Path(self.config.cloned_repo_dir))
        EXECUTED_TESTS = Path(self.config.bot_log_dir, "executed_tests.txt")
        EXECUTED_TESTS.touch(exist_ok=True)
        self.helper = RunHelper(payload_path=str(mock_file), config=self.config, execution_id=execution_id)

    def tearDown(self):
        global EXECUTED_TESTS
        EXECUTED_TESTS = Path("executed_tests.txt")
        self.helper.cleanup()
        del self.config
        del self.helper

    def test_generation_pdf_js_16275(self):
        response = self.helper.run_payload()
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse


class TestGenerationPdfJs19955(TestCase):
    def setUp(self):
        global EXECUTED_TESTS
        mock_file = Path("test_mocks", "pdf_js_19955.json")
        execution_id = mock_file.stem
        self.config = Config()
        helpers.remove_dir(Path(self.config.cloned_repo_dir))
        EXECUTED_TESTS = Path(self.config.bot_log_dir, "executed_tests.txt")
        EXECUTED_TESTS.touch(exist_ok=True)
        self.helper = RunHelper(payload_path=str(mock_file), config=self.config, execution_id=execution_id)

    def tearDown(self):
        global EXECUTED_TESTS
        EXECUTED_TESTS = Path("executed_tests.txt")
        self.helper.cleanup()
        del self.config
        del self.helper

    def test_generation_pdf_js_16275(self):
        response = self.helper.run_payload()
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse


class TestGenerationPdfJs19972(TestCase):
    def setUp(self):
        global EXECUTED_TESTS
        mock_file = Path("test_mocks", "pdf_js_19972.json")
        execution_id = mock_file.stem
        self.config = Config()
        helpers.remove_dir(Path(self.config.cloned_repo_dir))
        EXECUTED_TESTS = Path(self.config.bot_log_dir, "executed_tests.txt")
        EXECUTED_TESTS.touch(exist_ok=True)
        self.helper = RunHelper(payload_path=str(mock_file), config=self.config, execution_id=execution_id)

    def tearDown(self):
        global EXECUTED_TESTS
        EXECUTED_TESTS = Path("executed_tests.txt")
        self.helper.cleanup()
        del self.config
        del self.helper

    def test_generation_pdf_js_16275(self):
        response = self.helper.run_payload()
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse