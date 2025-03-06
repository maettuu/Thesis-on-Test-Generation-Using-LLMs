import json
import os
from django.test import TestCase
from .views import run, PROMPT_COMBINATIONS_GEN  # Adjust import based on your app structure
from datetime import datetime

#
# RUN With: python manage.py test webhook_handler.tests.<testname>
#

class TestAmplificationAndGeneration(TestCase):
    def setUp(self):
        # Load the local JSON file
        mock_payload = "test_mocks/2_kitsiosk_bugbug.json"
        #mock_payload = "test_mocks/webhook_2025-02-10_16-37-53.json"
        payload_path = os.path.join(os.path.dirname(__file__), mock_payload)
        with open(payload_path, "r") as f:
            self.payload = json.load(f)

        mock_model_test_generation = "test_mocks/2_generated_test_generation.txt"
        #mock_model_test_generation = "test_mocks/3_generated_test_generation.txt"
        mock_model_test_generation_path = os.path.join(os.path.dirname(__file__), mock_model_test_generation)
        with open(mock_model_test_generation_path, "r") as f:
            self.model_test_generation = f.read()

        mock_model_test_amplification = "test_mocks/2_generated_test_amplification.txt"
        mock_model_test_amplification_path = os.path.join(os.path.dirname(__file__), mock_model_test_amplification)
        with open(mock_model_test_amplification_path, "r") as f:
            self.model_test_amplification = f.read()

        self.dockerfile = "dockerfiles/Dockerfile_bugbug_old1"
    
    def test_run_function_with_local_payload(self):
        iAttempt     = 0
        stop         = False # we stop when successful
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        while iAttempt<len(PROMPT_COMBINATIONS_GEN["include_golden_code"]) and not stop:
            response, stop = run(self.payload,
                        dockerfile=self.dockerfile, 
                        model_test_generation=self.model_test_generation,
                        model_test_amplification=self.model_test_amplification,
                        iAttempt=iAttempt,
                        timestamp=timestamp,
                        post_comment=False)

            iAttempt +=1
        
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse



class TestGenerationBugbot2583(TestCase):
    def setUp(self):
        # Load the local JSON file
        mock_payload = "test_mocks/webhook_2025-02-12_18-44-22.json"
        payload_path = os.path.join(os.path.dirname(__file__), mock_payload)
        with open(payload_path, "r") as f:
            self.payload = json.load(f)

    
    def test_run_function_with_local_payload(self):
        iAttempt     = 0
        stop         = False # we stop when successful
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        while iAttempt<len(PROMPT_COMBINATIONS_GEN["include_golden_code"]) and not stop:
            response, stop = run(self.payload,
                        model="gpt-4o",
                        iAttempt=iAttempt,
                        timestamp=timestamp,
                        post_comment=False)

            iAttempt +=1

        iAttempt = 0
        while iAttempt<len(PROMPT_COMBINATIONS_GEN["include_golden_code"]) and not stop:
            response, stop = run(self.payload,
                        model="meta-llama/Llama-3.3-70B-Instruct",
                        iAttempt=iAttempt,
                        timestamp=timestamp,
                        post_comment=False)

            iAttempt +=1
        
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse



class TestGenerationBugbot2586(TestCase):
    def setUp(self):
        # Load the local JSON file
        mock_payload = "test_mocks/bugbot_2586.json"
        payload_path = os.path.join(os.path.dirname(__file__), mock_payload)
        with open(payload_path, "r") as f:
            self.payload = json.load(f)

    
    def test_run_function_with_local_payload(self):
        iAttempt     = 0
        stop         = False # we stop when successful
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        while iAttempt<len(PROMPT_COMBINATIONS_GEN["include_golden_code"]) and not stop:
            response, stop = run(self.payload,
                        model="gpt-4o",
                        iAttempt=iAttempt,
                        timestamp=timestamp,
                        post_comment=False)

            iAttempt +=1

        iAttempt = 0
        while iAttempt<len(PROMPT_COMBINATIONS_GEN["include_golden_code"]) and not stop:
            response, stop = run(self.payload,
                        model="meta-llama/Llama-3.3-70B-Instruct",
                        iAttempt=iAttempt,
                        timestamp=timestamp,
                        post_comment=False)

            iAttempt +=1
        
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse



class TestGenerationBugbot2587(TestCase):
    def setUp(self):
        # Load the local JSON file
        mock_payload = "test_mocks/bugbot_2587.json"
        payload_path = os.path.join(os.path.dirname(__file__), mock_payload)
        with open(payload_path, "r") as f:
            self.payload = json.load(f)

        mock_model_test_generation = "test_mocks/generated_test_2587.txt"
        mock_model_test_generation_path = os.path.join(os.path.dirname(__file__), mock_model_test_generation)
        with open(mock_model_test_generation_path, "r") as f:
            self.model_test_generation = f.read()

    
    def test_run_function_with_local_payload(self):
        iAttempt     = 0
        stop         = False # we stop when successful
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        while iAttempt<len(PROMPT_COMBINATIONS_GEN["include_golden_code"]) and not stop:
            response, stop = run(self.payload,
                        model="gpt-4o",
                        model_test_generation=self.model_test_generation,
                        iAttempt=iAttempt,
                        timestamp=timestamp,
                        post_comment=False)

            iAttempt +=1

        iAttempt = 0
        while iAttempt<len(PROMPT_COMBINATIONS_GEN["include_golden_code"]) and not stop:
            response, stop = run(self.payload,
                        model="meta-llama/Llama-3.3-70B-Instruct",
                        iAttempt=iAttempt,
                        timestamp=timestamp,
                        post_comment=False)

            iAttempt +=1
        
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse


class TestGenerationBugbot2588(TestCase):
    def setUp(self):
        # Load the local JSON file
        mock_payload = "test_mocks/bugbot_2588.json"
        payload_path = os.path.join(os.path.dirname(__file__), mock_payload)
        with open(payload_path, "r") as f:
            self.payload = json.load(f)
    
    def test_run_function_with_local_payload(self):
        iAttempt     = 0
        stop         = False # we stop when successful
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        while iAttempt<len(PROMPT_COMBINATIONS_GEN["include_golden_code"]) and not stop:
            response, stop = run(self.payload,
                        model="gpt-4o",
                        iAttempt=iAttempt,
                        timestamp=timestamp,
                        post_comment=False)

            iAttempt +=1

        iAttempt = 0
        while iAttempt<len(PROMPT_COMBINATIONS_GEN["include_golden_code"]) and not stop:
            response, stop = run(self.payload,
                        model="meta-llama/Llama-3.3-70B-Instruct",
                        iAttempt=iAttempt,
                        timestamp=timestamp,
                        post_comment=False)

            iAttempt +=1
        
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse


class TestGenerationBugbot2588_cachedTest(TestCase):
    def setUp(self):
        # Load the local JSON file
        mock_payload = "test_mocks/bugbot_2588.json"
        payload_path = os.path.join(os.path.dirname(__file__), mock_payload)
        with open(payload_path, "r") as f:
            self.payload = json.load(f)

        mock_model_test_generation = "test_mocks/bugbot_2588_test.txt"
        mock_model_test_generation_path = os.path.join(os.path.dirname(__file__), mock_model_test_generation)
        with open(mock_model_test_generation_path, "r") as f:
            self.model_test_generation = f.read()
    
    def test_run_function_with_local_payload(self):
        iAttempt     = 0
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        response, _ = run(self.payload,
                    model="gpt-4o",
                    model_test_generation=self.model_test_generation,
                    iAttempt=iAttempt,
                    timestamp=timestamp,
                    post_comment=False)

        
        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse


class TestGenerationPdfJs19232(TestCase):
    def setUp(self):
        # Load the local JSON file
        mock_payload = "test_mocks/pdf_js_19232.json"
        payload_path = os.path.join(os.path.dirname(__file__), mock_payload)
        with open(payload_path, "r") as f:
            self.payload = json.load(f)

    def test_run_function_with_local_payload(self):
        iAttempt = 0
        stop = False  # we stop when successful
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        while iAttempt < len(PROMPT_COMBINATIONS_GEN["include_golden_code"]) and not stop:
            response, stop = run(self.payload,
                                 model="gpt-4o",
                                 iAttempt=iAttempt,
                                 timestamp=timestamp,
                                 post_comment=False)

            iAttempt += 1

        iAttempt = 0
        while iAttempt < len(PROMPT_COMBINATIONS_GEN["include_golden_code"]) and not stop:
            response, stop = run(self.payload,
                                 model="meta-llama/Llama-3.3-70B-Instruct",
                                 iAttempt=iAttempt,
                                 timestamp=timestamp,
                                 post_comment=False)

            iAttempt += 1

        self.assertIsNotNone(response)  # Ensure response is not None
        self.assertTrue(
            isinstance(response, dict) or hasattr(response, 'status_code'))  # Ensure response is a dict or HttpResponse