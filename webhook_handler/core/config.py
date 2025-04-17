import os
import tree_sitter_javascript

from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from tree_sitter import Language
from pathlib import Path


class Config:
    def __init__(self):
        ############# Environment Variables #############
        load_dotenv()
        self.github_webhook_secret = os.getenv('GITHUB_WEBHOOK_SECRET')
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')

        ################### API Config ##################
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"Bearer {self.github_token}",
        }
        self.hug_client = InferenceClient(api_key="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")  # for huggingface client

        ################# General Config ################
        self.parse_language = Language(tree_sitter_javascript.language())
        # List length must be the same for both PROMPT_COMBINATIONS
        self.prompt_combinations_gen = {
            "include_golden_code"        : [1, 1, 1, 1, 0],
            "include_pr_desc"            : [0, 1, 0, 0, 0],
            "include_predicted_test_file": [1, 0, 1, 0, 0],
            "sliced"                     : ["LongCorr", "LongCorr", "No", "No", "No"]
        }
        self.prompt_combinations_ampl = {
            "test_code_sliced"           : [1, 0, 1, 1, 1],
            "include_golden_code"        : [1, 1, 1, 1, 0],
            "include_pr_desc"            : [0, 1, 1, 0, 0],
            "sliced"                     : ["LongCorr", "LongCorr", "LongCorr", "No", "No"]
        }

        ################## Path Config ##################
        is_in_server = Path("/home/ubuntu").is_dir() # Directory where webhook requests will be saved
        if is_in_server:
            self.webhook_raw_log_dir = "/home/ubuntu/logs/raw/" # for raw requests
            self.webhook_log_dir     = "/home/ubuntu/logs/" # for parsed requests
        else:
            working_dir = Path.cwd()
            self.webhook_raw_log_dir = Path(working_dir, "bot_logs") # for raw requests
            self.webhook_log_dir     = Path(working_dir, "bot_logs") # for parsed requests
            self.dockerfiles_dir     = Path(working_dir, "dockerfiles")

    def setup_log_dir(self, instance_id: str, timestamp: str, iAttempt: int, model: str) -> Path:
        Path(self.webhook_log_dir).mkdir(parents=True, exist_ok=True)
        log_dir = Path(self.webhook_log_dir, instance_id + "_%s" % timestamp, "i%s" % iAttempt + "_%s" % model)
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        Path(log_dir, "generation").mkdir(parents=True)
        Path(log_dir, "amplification").mkdir(parents=True)
        return log_dir
