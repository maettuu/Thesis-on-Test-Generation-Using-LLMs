import os
import tree_sitter_javascript
import logging

from dotenv import load_dotenv
from tree_sitter import Language
from pathlib import Path


class Config:
    """
    Holds all configuration and path variables.
    """
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
        self.prompt_combinations = {
            "include_golden_code"        : [1, 1, 1, 1, 0],
            "include_pr_desc"            : [0, 1, 0, 0, 0],
            "include_predicted_test_file": [1, 0, 1, 0, 0],
            "sliced"                     : [1, 1, 0, 0, 0]
        }

        ################## Log Directories Config ##################
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.bot_log_dir = Path(self.project_root, "scrape_handler", "test", "scrape_logs")
        self.pr_log_dir = None
        self.output_dir = None

        self.gen_test_dir = Path(self.project_root, "scrape_handler", "test", "generated_tests")
        self.cloned_repo_dir = "tmp_repo_dir"

        Path(self.bot_log_dir).mkdir(parents=True, exist_ok=True)
        Path(self.gen_test_dir).mkdir(parents=True, exist_ok=True)

    def setup_pr_log_dir(self, pr_id: str, timestamp: str) -> None:
        """
        Sets up directory for logger output file (one directory per PR)

        Parameters:
            pr_id (str): ID of the PR
            timestamp (str): Timestamp for PR test generation execution

        Returns:
            None
        """

        self.pr_log_dir = Path(self.bot_log_dir, pr_id + "_%s" % timestamp)
        Path(self.pr_log_dir).mkdir(parents=True, exist_ok=True)

    def setup_output_dir(self, i_attempt: int, model) -> None:
        """
        Sets up directory for generated pipeline files (one directory per run)

        Parameters:
            i_attempt (int): Attempt number
            model (LLM): Model name

        Returns:
            None
        """

        self.output_dir = Path(
            self.pr_log_dir,
            "i%s" % (i_attempt + 1) + "_%s" % model
        )
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.output_dir, "generation").mkdir(parents=True)


################## Custom Logger Tags ##################
# Marker: used to mark a new section (i.e., new PR, new run)
MARKER_LEVEL_NUM = 21
logging.addLevelName(MARKER_LEVEL_NUM, "MARKER")
def marker(self, message, *args, **kws):
    if self.isEnabledFor(MARKER_LEVEL_NUM):
        self._log(MARKER_LEVEL_NUM, message, args, **kws)
logging.Logger.marker = marker

# Success: used to mark the successful completion of an action
SUCCESS_LEVEL_NUM = 25
logging.addLevelName(SUCCESS_LEVEL_NUM, "SUCCESS")
def success(self, message, *args, **kws):
    if self.isEnabledFor(SUCCESS_LEVEL_NUM):
        self._log(SUCCESS_LEVEL_NUM, message, args, **kws)
logging.Logger.success = success

# Fail: used to mark the failure of an action
FAIL_LEVEL_NUM = 35
logging.addLevelName(FAIL_LEVEL_NUM, "FAIL")
def fail(self, message, *args, **kws):
    if self.isEnabledFor(FAIL_LEVEL_NUM):
        self._log(FAIL_LEVEL_NUM, message, args, **kws)
logging.Logger.fail = fail


class ColoredFormatter(logging.Formatter):
    """
    Reformats the console output and applied custom colors
    """
    RESET  = "\x1b[0m"
    COLORS = {
        logging.DEBUG:     "\x1b[90m",        # grey
        logging.INFO:      "\x1b[94m",        # bright blue
        MARKER_LEVEL_NUM:  "\x1b[96m",        # bright cyan
        SUCCESS_LEVEL_NUM: "\x1b[32m",        # green
        logging.WARNING:   "\x1b[38;5;208m",  # bright orange
        FAIL_LEVEL_NUM:    "\x1b[31m",        # red
        logging.ERROR:     "\x1b[31;1m",      # bold red
        logging.CRITICAL:  "\x1b[91;1m"       # bold bright red
    }

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        msg = super().format(record)
        return f"{color}{msg}{self.RESET}"


################## Logger Initialization ##################
def configure_logger(pr_log_dir: Path, execution_id: str) -> None:
    """
    Sets up the global logger for PR test generation

    Parameters:
        pr_log_dir (Path): Path to the PR log directory
        execution_id (str): ID of the PR test generation execution

    Returns:
        None
    """

    logfile = Path(pr_log_dir, f"{execution_id}.log")

    # get root logger
    root = logging.getLogger()
    root.setLevel("INFO")

    # remove any existing handlers (so pytest reruns don't duplicate)
    for h in list(root.handlers):
        root.removeHandler(h)

    # console handler
    ch = logging.StreamHandler()
    ch.setLevel("INFO")
    ch.setFormatter(ColoredFormatter(
        "[%(asctime)s] %(levelname)-9s: %(message)s",
        datefmt="%H:%M:%S"
    ))
    root.addHandler(ch)

    # file handler
    fh = logging.FileHandler(logfile, mode="w", encoding="utf-8")
    fh.setLevel("INFO")
    fh.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)-8s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    root.addHandler(fh)
