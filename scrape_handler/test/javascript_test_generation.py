import os
import json
import pytest

from pathlib import Path

from scrape_handler.core import Config
from scrape_handler.pipeline import Pipeline


def _get_payload(rel_path: str) -> dict:
    abs_path = os.path.join(os.path.dirname(__file__), rel_path)
    with open(abs_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload


Path("scrape_logs").mkdir(parents=True, exist_ok=True)
EXECUTED_TESTS = Path("scrape_logs", "executed_tests.txt")
EXECUTED_TESTS.touch(exist_ok=True)
completed = set(EXECUTED_TESTS.read_text(encoding='utf-8').splitlines())
all_mock_files = sorted(
    Path("scrape_mocks", "code_only").glob("*.json"),
    key=lambda p: int(p.stem.rsplit("_", 1)[-1]),
    reverse=True
)
mock_files = [mf for mf in all_mock_files if mf.stem not in completed and int(mf.stem.rsplit("_", 1)[-1]) >= 16668]  # new repo state
# mock_files = [mf for mf in all_mock_files if mf.stem not in completed and int(mf.stem.rsplit("_", 1)[-1]) < 16668]  # old repo state
# mock_files = [Path("scrape_mocks", "code_only", "pdf_js_19797.json")]  # specific payload

@pytest.mark.parametrize("mock_file", mock_files, ids=[mf.stem for mf in mock_files])
def test_pr_payload(mock_file):
    payload = _get_payload(str(mock_file))
    config = Config()
    mock_path = Path("scrape_mocks", "mock_responses", f"{mock_file.stem}_response.txt")
    if mock_path.exists():
        mock_response = mock_path.read_text(encoding="utf-8")
        pipeline = Pipeline(payload, config, mock_response=mock_response)
    else:
        pipeline = Pipeline(payload, config)
    generation_completed = pipeline.execute_pipeline()
    assert generation_completed is True
