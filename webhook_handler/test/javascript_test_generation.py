import os
import json

from django.test import TestCase
from datetime import datetime
from pathlib import Path

from webhook_handler.pipeline import run
from webhook_handler.webhook import logger, config


class TestHelper():
    def __init__(
            self,
            payload_path: str,
            mock_response_generation_path: str = None,
            mock_response_amplification_path: str = None,
            run_all_models: bool = False
    ):
        self.payload = self._get_payload(payload_path)
        self.mock_response_generation = self._get_file_content(mock_response_generation_path)
        self.mock_response_amplification = self._get_file_content(mock_response_amplification_path)
        self.run_all_models = run_all_models

    @staticmethod
    def _get_payload(rel_path: str) -> str:
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
            "meta-llama/Llama-3.3-70B-Instruct",
            "llama-3.3-70b-versatile",
            "qwen-qwq-32b"
        ]
        for model in models:
            iAttempt = 1
            while iAttempt <= len(config.prompt_combinations_gen["include_golden_code"]) and (not stop or self.run_all_models):
                response, stop = run(self.payload,
                                     config,
                                     logger,
                                     model=model,
                                     model_test_generation=self.mock_response_generation,
                                     model_test_amplification=self.mock_response_amplification,
                                     iAttempt=iAttempt,
                                     timestamp=timestamp,
                                     post_comment=False)
                if stop:
                    post_comment = False
                with open(Path(config.run_log_dir, 'results.csv'), 'a') as f:
                    f.write("%s,%s,%s,%s\n" % (self.payload["number"], model, iAttempt, stop))

                iAttempt += 1

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
            with open(Path(config.run_log_dir, 'results.csv'), 'a') as f:
                f.write("%s,%s,%s,%s\n" % (self.payload["number"], model, 1, stop))

        return response

#
# RUN With: python manage.py test webhook_handler.test.<filename>.<testname>
#
class TestGenerationPdfJs16275(TestCase):
    def setUp(self):
        self.test_helper = TestHelper(payload_path="test_mocks/pdf_js_16275.json", run_all_models=True)

    def test_generation_pdf_js_16275(self):
        response = self.test_helper.run_payload()
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse


class TestGenerationPdfJs16318(TestCase):
    def setUp(self):
        self.test_helper = TestHelper(payload_path="test_mocks/pdf_js_16318.json", run_all_models=True)

    def test_generation_pdf_js_16318(self):
        response = self.test_helper.run_payload()
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse


class TestGenerationPdfJs16798(TestCase):
    def setUp(self):
        self.test_helper = TestHelper(payload_path="test_mocks/pdf_js_16798.json", run_all_models=True)

    def test_generation_pdf_js_16798(self):
        response = self.test_helper.run_payload()
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse


class TestGenerationPdfJs17602(TestCase):
    def setUp(self):
        self.test_helper = TestHelper(payload_path="test_mocks/pdf_js_17602.json", run_all_models=True)

    def test_generation_pdf_js_17602(self):
        response = self.test_helper.run_payload()
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse


class TestGenerationPdfJs17905(TestCase):
    def setUp(self):
        self.test_helper = TestHelper(
            payload_path="test_mocks/pdf_js_17905.json",
            mock_response_generation_path="test_mocks/pdf_js_17905_response.txt"
        )

    def test_generation_pdf_js_17905(self):
        response = self.test_helper.run_payload()
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse


class TestGenerationPdfJs18430(TestCase):
    def setUp(self):
        self.test_helper = TestHelper(payload_path="test_mocks/pdf_js_18430.json", run_all_models=True)

    def test_generation_pdf_js_18430(self):
        response = self.test_helper.run_payload()
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse


class TestGenerationPdfJs19010(TestCase):
    def setUp(self):
        self.test_helper = TestHelper(payload_path="test_mocks/pdf_js_19010.json", run_all_models=True)

    def test_generation_pdf_js_19010(self):
        response = self.test_helper.run_payload()
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse


class TestGenerationPdfJs19232(TestCase):
    def setUp(self):
        self.test_helper = TestHelper(payload_path="test_mocks/pdf_js_19232.json", run_all_models=True)

    def test_generation_pdf_js_19232(self):
        response = self.test_helper.run_payload()
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse


class TestGenerationPdfJs19470(TestCase):
    def setUp(self):
        self.test_helper = TestHelper(payload_path="test_mocks/pdf_js_19470.json", run_all_models=True)

    def test_generation_pdf_js_19470(self):
        response = self.test_helper.run_payload()
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse


class TestGenerationPdfJs19504(TestCase):
    def setUp(self):
        self.test_helper = TestHelper(payload_path="test_mocks/pdf_js_19504.json", run_all_models=True)

    def test_generation_pdf_js_19504(self):
        response = self.test_helper.run_payload()
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse


