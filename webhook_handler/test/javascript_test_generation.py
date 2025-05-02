import os
import json

from django.test import TestCase
from datetime import datetime
from pathlib import Path

from webhook_handler.pipeline import run
from webhook_handler.webhook import logger, config


#
# RUN With: python manage.py test webhook_handler.test.<filename>.<testname>
#
class TestGenerationPdfJs19232(TestCase):
    def setUp(self):
        # Load the local JSON file
        mock_payload = "test_mocks/pdf_js_19232.json"
        payload_path = os.path.join(os.path.dirname(__file__), mock_payload)
        with open(payload_path, "r", encoding="utf-8") as f:
            self.payload = json.load(f)
        Path(config.webhook_log_dir).mkdir(parents=True, exist_ok=True)

    def test_run_function_with_local_payload(self):
        stop = False  # we stop when successful
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        post_comment = True
        models = [
            "gpt-4o",
            "meta-llama/Llama-3.3-70B-Instruct",
            "llama-3.3-70b-versatile",
            "deepseek-r1-distill-qwen-32b"
        ]
        for model in models:
            iAttempt = 1
            while iAttempt < len(config.prompt_combinations_gen["include_golden_code"]) and not stop:
                response, stop = run(self.payload,
                                     config,
                                     logger,
                                     model=model,
                                     iAttempt=iAttempt,
                                     timestamp=timestamp,
                                     post_comment=False)
                iAttempt += 1
                if stop:
                    post_comment = False
                with open(Path(config.webhook_log_dir, 'results.csv'), 'a') as f:
                    f.write("%s,%s,%s,%s\n" % (self.payload["number"], model, iAttempt, stop))

        if not stop:
            response, stop = run(self.payload,
                                 config,
                                 logger,
                                 model="o3-mini",
                                 iAttempt=1,
                                 timestamp=timestamp,
                                 post_comment=post_comment)
            if stop:
                post_comment = False
            with open(Path(config.webhook_log_dir, 'results.csv'), 'a') as f:
                f.write("%s,%s,%s,%s\n" % (self.payload["number"], model, iAttempt, stop))

        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse


class TestGenerationPdfJs17905(TestCase):
    def setUp(self):
        # Load the local JSON file
        mock_payload = "test_mocks/pdf_js_17905.json"
        payload_path = os.path.join(os.path.dirname(__file__), mock_payload)
        with open(payload_path, "r", encoding="utf-8") as f:
            self.payload = json.load(f)
        Path(config.webhook_log_dir).mkdir(parents=True, exist_ok=True)

    def test_run_function_with_local_payload(self):
        stop = False  # we stop when successful
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        post_comment = True
        # mock_model_test_generation = "test_mocks/pdf_js_17905_response.txt"
        # mock_model_test_generation_path = os.path.join(os.path.dirname(__file__), mock_model_test_generation)
        # with open(mock_model_test_generation_path, "r", encoding="utf-8") as f:
        #     self.model_test_generation = f.read()
        models = [
            "gpt-4o",
            "meta-llama/Llama-3.3-70B-Instruct",
            "llama-3.3-70b-versatile",
            "deepseek-r1-distill-qwen-32b"
        ]
        for model in models:
            iAttempt = 1
            while iAttempt <= len(config.prompt_combinations_gen["include_golden_code"]):
                response, stop = run(self.payload,
                                     config,
                                     logger,
                                     model=model,
                                     # model_test_generation=self.model_test_generation,
                                     iAttempt=iAttempt,
                                     timestamp=timestamp,
                                     post_comment=False)
                iAttempt += 1
                if stop:
                    post_comment = False
                with open(Path(config.webhook_log_dir, 'results.csv'), 'a') as f:
                    f.write("%s,%s,%s,%s\n" % (self.payload["number"], model, iAttempt, stop))

        if not stop:
            model = "o3-mini"
            logger.info("[*] Starting o3-mini...")
            response, stop = run(self.payload,
                                 config,
                                 logger,
                                 model=model,
                                 iAttempt=1,
                                 timestamp=timestamp,
                                 post_comment=post_comment)
            if stop:
                post_comment = False
            with open(Path(config.webhook_log_dir, 'results.csv'), 'a') as f:
                f.write("%s,%s,%s,%s\n" % (self.payload["number"], model, 1, stop))

        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse
