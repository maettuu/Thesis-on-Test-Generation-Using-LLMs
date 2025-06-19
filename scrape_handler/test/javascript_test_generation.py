import os
import json
import pytest

from datetime import datetime
from pathlib import Path

from scrape_handler.core import Config, helpers
from scrape_handler.pipeline import run
from scrape_handler.data_models import PullRequestData


class TestHelper:
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
        self.logger = None
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

    def run_payload(self):
        stop = False  # we stop when successful
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        post_comment = True
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
                pr_data = PullRequestData.from_payload(self.payload)
                log_dir = self.config.setup_log_dir(pr_data.id, timestamp, iAttempt, model)
                self.logger = self.config.init_logger(self.run_id)

                self.logger.info("[*] Starting combination %d with model %s" % (iAttempt + 1, model))
                response, stop = run(pr_data,
                                     self.config,
                                     self.logger,
                                     log_dir=log_dir,
                                     model=model,
                                     model_test_generation=self.mock_response_generation,
                                     model_test_amplification=self.mock_response_amplification,
                                     iAttempt=iAttempt,
                                     post_comment=False)
                if stop:
                    post_comment = False
                if not Path(self.config.run_log_dir, 'results.csv').exists():
                    Path(self.config.run_log_dir, 'results.csv').write_text("prNumber,model,iAttempt,stop\n", encoding="utf-8")
                with open(Path(self.config.run_log_dir, 'results.csv'), 'a') as f:
                    f.write("%s,%s,%s,%s\n" % (self.payload["number"], model, iAttempt + 1, stop))

                iAttempt += 1

        if not stop:
            model = "o3-mini"
            self.logger.info("[*] Starting o3-mini...")
            pr_data = PullRequestData.from_payload(self.payload)
            log_dir = self.config.setup_log_dir(pr_data.id, timestamp, 0, model)
            self.logger = self.config.init_logger(self.run_id)

            response, stop = run(pr_data,
                                 self.config,
                                 self.logger,
                                 log_dir=log_dir,
                                 model=model,
                                 iAttempt=0,
                                 post_comment=post_comment)
            if stop:
                post_comment = False
            with open(Path(self.config.run_log_dir, 'results.csv'), 'a') as f:
                f.write("%s,%s,%s,%s\n" % (self.payload["number"], model, 1, stop))

        return response

    def cleanup(self):
        helpers.remove_dir(Path(self.config.cloned_repo_dir))


@pytest.mark.parametrize("mock_file", sorted(Path("scrape_mocks", "code_only").glob("*.json")))
def test_pr_payload(mock_file):
    run_id = mock_file.stem
    config = Config()

    helper = TestHelper(payload_path=str(mock_file), config=config, run_id=run_id, run_all_models=False)
    response = helper.run_payload()
    assert response is not None
    assert isinstance(response, dict) or hasattr(response, "status_code")
    helper.cleanup()



