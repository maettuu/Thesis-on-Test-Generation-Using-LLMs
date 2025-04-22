import os
import json

from django.test import TestCase
from datetime import datetime

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

    def test_run_function_with_local_payload(self):
        iAttempt = 0
        stop = False  # we stop when successful
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # while iAttempt < len(config.prompt_combinations_gen["include_golden_code"]) and not stop:
        #     response, stop = run(self.payload,
        #                          config,
        #                          logger,
        #                          model="gpt-4o",
        #                          iAttempt=iAttempt,
        #                          timestamp=timestamp,
        #                          post_comment=False)
        #     iAttempt += 1

        iAttempt = 0
        while iAttempt < len(config.prompt_combinations_gen["include_golden_code"]) and not stop:
            response, stop = run(self.payload,
                                 config,
                                 logger,
                                 model="meta-llama/Llama-3.3-70B-Instruct",
                                 iAttempt=iAttempt,
                                 timestamp=timestamp,
                                 post_comment=False)

            iAttempt += 1

        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse


class TestGenerationPdfJs17905(TestCase):
    def setUp(self):
        # Load the local JSON file
        mock_payload = "test_mocks/pdf_js_17905.json"
        payload_path = os.path.join(os.path.dirname(__file__), mock_payload)
        with open(payload_path, "r", encoding="utf-8") as f:
            self.payload = json.load(f)

    def test_run_function_with_local_payload(self):
        iAttempt = 0
        stop = False  # we stop when successful
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # while iAttempt < len(config.prompt_combinations_gen["include_golden_code"]) and not stop:
        #     response, stop = run(self.payload,
        #                          config,
        #                          logger,
        #                          model="gpt-4o",
        #                          iAttempt=iAttempt,
        #                          timestamp=timestamp,
        #                          post_comment=False)
        #     iAttempt += 1

        iAttempt = 0
        while iAttempt < len(config.prompt_combinations_gen["include_golden_code"]) and not stop:
            response, stop = run(self.payload,
                                 config,
                                 logger,
                                 model="meta-llama/Llama-3.3-70B-Instruct",
                                 iAttempt=iAttempt,
                                 timestamp=timestamp,
                                 post_comment=False)

            iAttempt += 1

        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse
