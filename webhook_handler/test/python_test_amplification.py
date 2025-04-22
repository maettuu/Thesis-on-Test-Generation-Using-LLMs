import os
import json

from django.test import TestCase
from datetime import datetime

from webhook_handler.pipeline import run
from webhook_handler.webhook import logger, config


#
# RUN With: python manage.py test webhook_handler.test.<filename>.<testname>
#
class TestAmplificationAndGeneration(TestCase):
    def setUp(self):
        # Load the local JSON file
        mock_payload = "test_mocks/2_kitsiosk_bugbug.json"
        # mock_payload = "test_mocks/webhook_2025-02-10_16-37-53.json"
        payload_path = os.path.join(os.path.dirname(__file__), mock_payload)
        with open(payload_path, "r", encoding="utf-8") as f:
            self.payload = json.load(f)

        mock_model_test_generation = "test_mocks/2_generated_test_generation.txt"
        # mock_model_test_generation = "test_mocks/3_generated_test_generation.txt"
        mock_model_test_generation_path = os.path.join(os.path.dirname(__file__), mock_model_test_generation)
        with open(mock_model_test_generation_path, "r", encoding="utf-8") as f:
            self.model_test_generation = f.read()

        mock_model_test_amplification = "test_mocks/2_generated_test_amplification.txt"
        mock_model_test_amplification_path = os.path.join(os.path.dirname(__file__), mock_model_test_amplification)
        with open(mock_model_test_amplification_path, "r", encoding="utf-8") as f:
            self.model_test_amplification = f.read()

        self.dockerfile = "dockerfiles/Dockerfile_bugbug_old1"

    def test_run_function_with_local_payload(self):
        iAttempt     = 0
        stop         = False # we stop when successful
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        while iAttempt <len(config.prompt_combinations_gen["include_golden_code"]) and not stop:
            response, stop = run(self.payload,
                                 config,
                                 logger,
                                 dockerfile=self.dockerfile,
                                 model_test_generation=self.model_test_generation,
                                 model_test_amplification=self.model_test_amplification,
                                 iAttempt=iAttempt,
                                 timestamp=timestamp,
                                 post_comment=False)

            iAttempt +=1

        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse