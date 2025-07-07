import shutil
import re
import subprocess
import os
import stat
import time
import json
import logging

from pathlib import Path
from collections import defaultdict


logger = logging.getLogger(__name__)


def extract_packages(base_commit: str, repo_dir: str) -> str:
    """
    Filters the repository for the package.json file and extracts all its dependencies.

    Parameters:
        base_commit (str): The base commit to check out
        repo_dir (str): The path to the temporary directory

    Returns:
        str: All the dependencies
    """

    current_branch = run_command("git rev-parse --abbrev-ref HEAD", cwd=repo_dir)
    run_command(f"git checkout {base_commit}", cwd=repo_dir)
    try:
        package_json_path = Path(repo_dir, "package.json")
        if not package_json_path.is_file():
            logger.warning('No package.json found')
            return ""
        package_data = json.loads(package_json_path.read_text(encoding="utf-8"))
        dependencies = package_data.get("dependencies", {})
        dev_dependencies = package_data.get("devDependencies", {})
        engines = package_data.get("engines", {})
        output_lines = ["Available Packages"]
        if not dependencies and not dev_dependencies:
            return ""
        if dependencies:
            output_lines.append("Dependencies:")
            for pkg, version in dependencies.items():
                output_lines.append(f"- {pkg}: {version}")
            output_lines.append("\n")
        if dev_dependencies:
            output_lines.append("Dev Dependencies:")
            for pkg, version in dev_dependencies.items():
                output_lines.append(f"- {pkg}: {version}")
            output_lines.append("\n")
        if engines:
            output_lines.append("Engines:")
            for engine, version in engines.items():
                output_lines.append(f"- {engine}: {version}")

        return "\n".join(output_lines)
    finally:
        run_command(f"git checkout {current_branch}", cwd=repo_dir)  # Reset to the original commit


def extract_relative_imports(base_commit:str, repo_dir: str) -> str:
    """
    Loops through all test files and extracts all relative imports.

    Parameters:
        base_commit (str): The base commit to check out
        repo_dir (str): The path to the temporary directory

    Returns:
        str: All the relative imports
    """

    current_branch = run_command("git rev-parse --abbrev-ref HEAD", cwd=repo_dir)
    run_command(f"git checkout {base_commit}", cwd=repo_dir)
    try:
        import_block_pattern = re.compile(
            r'import\s+(?P<imports>[^;]+?)\s+from\s+[\'"](?P<path>(\./|\.\./)[^\'"]+)[\'"]',
            re.DOTALL # for multi-line imports
        )
        import_map = defaultdict(set)
        for file in Path(repo_dir, 'test', 'unit').rglob("*.js"):
            content = file.read_text(encoding="utf-8")
            for match in import_block_pattern.finditer(content):
                import_path = match.group("path")
                raw_imports = match.group("imports")
                raw_imports = raw_imports.replace("{", "").replace("}", "")
                symbols = [s.strip() for s in raw_imports.split(",") if s.strip()]
                for sym in symbols:
                    # Handle "A as B" → resolve to A
                    if " as " in sym:
                        original_sym = sym.split(" as ")[0].strip()
                    else:
                        original_sym = sym
                    if original_sym:
                        import_map[import_path].add(original_sym)

        output_lines = ["Available Relative Imports:"]
        for path in sorted(import_map):
            symbols = sorted(import_map[path])
            output_lines.append(f"- `{path}`: {', '.join(symbols)}")
        return "\n".join(output_lines) if import_map else ""
    finally:
        run_command(f"git checkout {current_branch}", cwd=repo_dir)  # Reset to the original commit


def run_command(command: str, cwd: str = None) -> str | None:
    """
    Helper method to run a command in subprocess.

    Parameters:
        command (str): The command to execute
        cwd (str): The location in which the command should be executed

    Returns:
        str: Output of the command
    """

    result = subprocess.run(command, cwd=cwd, shell=True, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else None


def remove_dir(path: Path, max_retries: int = 3, delay: float = 0.1, log_success: bool = False) -> None:
    """
    Helper method to remove a directory.

    Parameters:
        path (Path): The path to the directory to remove
        max_retries (int, optional): The maximum number of times to retry the command
        delay (float, optional): The delay between retries
        log_success (bool, optional): Whether to log the success message

    Returns:
        None
    """

    if not path.exists():
        return

    def on_error(func, path, _) -> None:
        os.chmod(path, stat.S_IWRITE)
        func(path)

    for attempt in range(max_retries):
        try:
            shutil.rmtree(path, onerror=on_error)
            if log_success: logger.success(f"Directory {path} removed successfully")
            return
        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"Failed attempt {attempt} removing {path}: {e}, retrying in {delay}s")
                time.sleep(delay)
            else:
                logger.error(f"Final attempt failed removing {path}, must be removed manually: {e}")