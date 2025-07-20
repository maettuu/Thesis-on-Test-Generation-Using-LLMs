import os
import json

from django.test import TestCase

from webhook_handler.core import Config
from webhook_handler.pipeline import Pipeline


def _get_payload(rel_path: str) -> dict:
    abs_path = os.path.join(os.path.dirname(__file__), rel_path)
    with open(abs_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload


def _get_mock_content(rel_path: str) -> str:
    abs_path = os.path.join(os.path.dirname(__file__), rel_path)
    with open(abs_path, "r", encoding="utf-8") as f:
        content = f.read()
    return content

#
# RUN With: python manage.py test webhook_handler.test.<filename>.<testname>
#
class TestGenerationPdfJs19639(TestCase):
    def setUp(self):
        self.payload = _get_payload("test_mocks/pdf_js_19639.json")
        mock_response = _get_mock_content("test_mocks/pdf_js_19639_response.txt")
        self.config = Config()
        self.pipeline = Pipeline(self.payload, self.config, mock_response=mock_response)

    def tearDown(self):
        del self.payload
        del self.config
        del self.pipeline

    def test_generation_pdf_js_19639(self):
        generation_completed = self.pipeline.execute_pipeline()
        self.assertTrue(generation_completed)


class TestGenerationPdfJs19825(TestCase):
    def setUp(self):
        self.payload = _get_payload("test_mocks/pdf_js_19825.json")
        mock_response = _get_mock_content("test_mocks/pdf_js_19825_response.txt")
        self.config = Config()
        self.pipeline = Pipeline(self.payload, self.config, mock_response=mock_response)

    def tearDown(self):
        del self.payload
        del self.config
        del self.pipeline

    def test_generation_pdf_js_19825(self):
        generation_completed = self.pipeline.execute_pipeline()
        self.assertTrue(generation_completed)


class TestGenerationPdfJs19849(TestCase):
    def setUp(self):
        self.payload = _get_payload("test_mocks/pdf_js_19849.json")
        self.config = Config()
        self.pipeline = Pipeline(self.payload, self.config)

    def tearDown(self):
        del self.payload
        del self.config
        del self.pipeline

    def test_generation_pdf_js_19849(self):
        generation_completed = self.pipeline.execute_pipeline()
        self.assertTrue(generation_completed)


class TestGenerationPdfJs19880(TestCase):
    def setUp(self):
        self.payload = _get_payload("test_mocks/pdf_js_19880.json")
        self.config = Config()
        self.pipeline = Pipeline(self.payload, self.config)

    def tearDown(self):
        del self.payload
        del self.config
        del self.pipeline

    def test_generation_pdf_js_19880(self):
        generation_completed = self.pipeline.execute_pipeline()
        self.assertTrue(generation_completed)


class TestGenerationPdfJs19918(TestCase):
    def setUp(self):
        self.payload = _get_payload("test_mocks/pdf_js_19918.json")
        mock_response = _get_mock_content("test_mocks/pdf_js_19918_response.txt")
        self.config = Config()
        self.pipeline = Pipeline(self.payload, self.config, mock_response=mock_response)

    def tearDown(self):
        del self.payload
        del self.config
        del self.pipeline

    def test_generation_pdf_js_19918(self):
        generation_completed = self.pipeline.execute_pipeline()
        self.assertTrue(generation_completed)


class TestGenerationPdfJs19955(TestCase):
    def setUp(self):
        self.payload = _get_payload("test_mocks/pdf_js_19955.json")
        self.config = Config()
        self.pipeline = Pipeline(self.payload, self.config)

    def tearDown(self):
        del self.payload
        del self.config
        del self.pipeline

    def test_generation_pdf_js_19955(self):
        generation_completed = self.pipeline.execute_pipeline()
        self.assertTrue(generation_completed)


class TestGenerationPdfJs19972(TestCase):
    def setUp(self):
        self.payload = _get_payload("test_mocks/pdf_js_19972.json")
        self.config = Config()
        self.pipeline = Pipeline(self.payload, self.config)

    def tearDown(self):
        del self.payload
        del self.config
        del self.pipeline

    def test_generation_pdf_js_19972(self):
        generation_completed = self.pipeline.execute_pipeline()
        self.assertTrue(generation_completed)


class TestGenerationPdfJs20063(TestCase):
    def setUp(self):
        self.payload = _get_payload("test_mocks/pdf_js_20063.json")
        mock_response = _get_mock_content("test_mocks/pdf_js_20063_response.txt")
        self.config = Config()
        self.pipeline = Pipeline(self.payload, self.config, mock_response=mock_response)

    def tearDown(self):
        del self.payload
        del self.config
        del self.pipeline

    def test_generation_pdf_js_20063(self):
        generation_completed = self.pipeline.execute_pipeline()
        self.assertTrue(generation_completed)
