import os
import json
import pytest
import traceback
import docker
import logging

from datetime import datetime
from pathlib import Path
from docker.errors import ImageNotFound

from scrape_handler.core import Config, configure_logger, ExecutionError, helpers
from scrape_handler.pipeline import run
from scrape_handler.data_models import PullRequestData


logger = logging.getLogger(__name__)


class RunHelper:
    def __init__(
            self,
            payload_path: str,
            config: Config,
            run_id: str,
            mock_response_generation_path: str = None,
            mock_response_amplification_path: str = None,
            run_all_models: bool = False
    ):
        self.payload = self._get_payload(payload_path)
        self.config = config
        self.run_id = run_id
        self.mock_response_generation = self._get_file_content(mock_response_generation_path)
        self.mock_response_amplification = self._get_file_content(mock_response_amplification_path)
        self.run_all_models = run_all_models

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

    def record_result(self, number, model, iAttempt, stop):
        with open(Path(self.config.bot_log_dir, 'results.csv'), 'a') as f:
            f.write(
                "{:<9},{:<30},{:<9},{:<19}\n".format(number, model, iAttempt + 1, stop)
            )

    def run_payload(self):
        stop = False  # we stop when successful
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        pr_data = PullRequestData.from_payload(self.payload)
        self.config.setup_pr_log_dir(pr_data.id, timestamp)
        configure_logger(self.config.pr_log_dir, self.run_id)
        logger.marker(f"============ Running Payload #{pr_data.number} ============")
        if not Path(self.config.bot_log_dir, 'results.csv').exists():
            Path(self.config.bot_log_dir, 'results.csv').write_text(
                "{:<9},{:<30},{:<9},{:<19}\n".format("prNumber", "model", "iAttempt", "stop"),
                encoding="utf-8"
            )

        models = [
            "gpt-4o",
            # "meta-llama/Llama-3.3-70B-Instruct",
            "llama-3.3-70b-versatile",
            "deepseek-r1-distill-llama-70b",
            # "qwen-qwq-32b"
        ]
        for model in models:
            iAttempt = 0
            while iAttempt < len(self.config.prompt_combinations_gen["include_golden_code"]) and (not stop or self.run_all_models):
                self.config.setup_output_dir(iAttempt, model)
                logger.marker("Starting combination %d with model %s" % (iAttempt + 1, model))
                try:
                    response, stop = run(pr_data,
                                         self.config,
                                         model=model,
                                         model_test_generation=self.mock_response_generation,
                                         model_test_amplification=self.mock_response_amplification,
                                         iAttempt=iAttempt,
                                         post_comment=False)
                    logger.success(f"Combination %d with model %s finished successfully" % (iAttempt + 1, model))
                    self.record_result(self.payload["number"], model, iAttempt + 1, stop)
                except ExecutionError:
                    err = traceback.format_exc()
                    logger.critical("Failed with error:\n%s" % err)
                    self.record_result(self.payload["number"], model, iAttempt + 1, "error")
                except Exception as e:
                    logger.critical("Failed with unexpected error:\n%s" % e)
                    self.record_result(self.payload["number"], model, iAttempt + 1, "unexpected error")

                if stop:
                    gen_test = Path(self.config.output_dir, "generation", "generated_test.txt").read_text(
                        encoding="utf-8")
                    new_filename = f"{self.run_id}_{self.config.output_dir.name}.txt"
                    Path(self.config.gen_test_dir, new_filename).write_text(gen_test, encoding="utf-8")
                    logger.success(f"Test file copied to {self.config.gen_test_dir}/{new_filename}")

                iAttempt += 1

        if not stop:
            model = "o3-mini"
            self.config.setup_output_dir(0, model)
            logger.marker("Starting with model o3-mini")
            try:
                response, stop = run(pr_data,
                                     self.config,
                                     model=model,
                                     iAttempt=0,
                                     post_comment=False)
                logger.success("o3-mini finished successfully")
                self.record_result(self.payload["number"], model, 1, stop)
            except ExecutionError:
                err = traceback.format_exc()
                logger.critical("Failed with error:\n%s" % err)
                self.record_result(self.payload["number"], model, 1, "error")
            except Exception as e:
                logger.critical("Failed with unexpected error:\n%s" % e)
                self.record_result(self.payload["number"], model, 1, "unexpected error")

            if stop:
                gen_test = Path(self.config.output_dir, "generation", "generated_test.txt").read_text(encoding="utf-8")
                new_filename = f"{self.run_id}_{self.config.output_dir.name}.txt"
                Path(self.config.gen_test_dir, new_filename).write_text(gen_test, encoding="utf-8")
                logger.success(f"Test file copied to {self.config.gen_test_dir}/{new_filename}")

        logger.marker(f"============ Finished Payload #{pr_data.number} ============")
        return response

    def cleanup(self):
        helpers.remove_dir(Path(self.config.cloned_repo_dir), temp_repo=True)
        image_tag = f"image_{self.payload["repository"]["owner"]["login"]}__{self.payload["repository"]["name"]}-{self.payload["number"]}:latest"
        try:
            client = docker.from_env()
            client.images.remove(image=image_tag, force=True)
            logger.success(f"Removed Docker image '{image_tag}'")
        except ImageNotFound:
            logger.error(f"Tried to remove image '{image_tag}', but it was not found")
        except Exception as e:
            logger.error(f"Failed to remove Docker image '{image_tag}': {e}")


mock_files = sorted(
    Path("scrape_mocks", "code_only").glob("*.json"),
    key=lambda p: int(p.stem.rsplit("_", 1)[-1]),
    reverse=True
)

@pytest.mark.parametrize("mock_file", mock_files, ids=[mf.stem for mf in mock_files])
def test_pr_payload(mock_file):
    run_id = mock_file.stem
    config = Config()

    helper = RunHelper(payload_path=str(mock_file), config=config, run_id=run_id, run_all_models=False)
    response = helper.run_payload()
    assert response is not None
    assert isinstance(response, dict) or hasattr(response, "status_code")
    helper.cleanup()
