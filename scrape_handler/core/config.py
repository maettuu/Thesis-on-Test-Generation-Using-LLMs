import os
import tree_sitter_javascript
import logging

from dotenv import load_dotenv
from tree_sitter import Language
from pathlib import Path

logger: logging.Logger | None = None

class Config:
    def __init__(self):
        ############# Environment Variables #############
        load_dotenv()
        self.github_webhook_secret = os.getenv('GITHUB_WEBHOOK_SECRET')
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.hug_api_key = os.getenv('HUG_API_KEY')
        self.groq_api_key = os.getenv('GROQ_API_KEY')

        ################### API Config ##################
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"Bearer {self.github_token}",
        }

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
            self.project_root = "/home/ubuntu/"
            self.bot_log_dir = "/home/ubuntu/logs_js/" # for parsed requests
        else:
            self.project_root = Path(__file__).resolve().parent.parent.parent
            self.bot_log_dir = Path(self.project_root, "bot_logs") # for parsed requests
        self.run_log_dir = None

        self.cloned_repo_dir = "tmp_repo_dir"

    def init_logger(self, run_id: str) -> logging.Logger:
        global logger

        logfile = Path(self.run_log_dir, f"{run_id}.log")

        # get root logger (or you can pick a named one)
        logger = logging.getLogger()
        logger.setLevel("INFO")

        # remove any existing handlers (so pytest reruns don't duplicate)
        for h in list(logger.handlers):
            logger.removeHandler(h)

        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel("INFO")
        ch.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
            datefmt="%H:%M:%S"
        ))
        logger.addHandler(ch)

        # File handler (overwrite each run)
        fh = logging.FileHandler(logfile, mode="w", encoding="utf-8")
        fh.setLevel("INFO")
        fh.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(fh)

        return logger

    def setup_log_dir(self, instance_id: str, timestamp: str, iAttempt: int, model: str) -> Path:
        Path(self.bot_log_dir).mkdir(parents=True, exist_ok=True)
        self.run_log_dir = Path(self.bot_log_dir, instance_id + "_%s" % timestamp)
        log_dir = Path(
            self.run_log_dir,
            "i%s" % (iAttempt + 1) + "_%s" % model
        )
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        Path(log_dir, "generation").mkdir(parents=True)
        Path(log_dir, "amplification").mkdir(parents=True)
        return log_dir
