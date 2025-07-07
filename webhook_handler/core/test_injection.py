import re
import os
import logging

from tree_sitter import Parser, Language
from pathlib import Path
from collections import Counter

from . import helpers


logger = logging.getLogger(__name__)


def get_candidate_test_file(
        parse_language: Language,
        base_commit: str,
        patch: str,
        tmp_repo_dir: str
) -> [str, str, str]:
    """
    Finds a fitting test file and its content to inject the newly generated test into.

    Parameters:
        parse_language (Language): The language the parser should use
        base_commit (str): The base commit used to check out
        patch (str): The golden code patch
        tmp_repo_dir (str): The directory to look for test files in

    Returns:
        str: The name of the test file
        str: The contents of the test file
        str: The sliced contents of the test file
    """

    logger.info("Fetching test file for injection...")
    test_filename, test_file_content = _find_file_to_inject(base_commit, patch, tmp_repo_dir)
    if not test_file_content:
        logger.warning(f"No suitable test file {test_filename} found. New file created.")
        return test_filename, "", ""
    else:
        logger.success(f"Test file {test_filename} found")
        test_file_content_sliced = _keep_first_n_defs(parse_language, test_file_content)

    return test_filename, test_file_content, test_file_content_sliced


def _find_file_to_inject(base_commit: str, patch: str, tmp_repo_dir: str) -> [str, str]:
    """
    Looks through repository and tries to find the candidate test file.

    Parameters:
        base_commit (str): The base commit used to check out
        patch (str): The golden code patch
        tmp_repo_dir (str): The directory to look for test files in

    Returns:
        str: The name of the test file
        str: The contents of the test file
    """

    current_branch = helpers.run_command("git rev-parse --abbrev-ref HEAD", cwd=tmp_repo_dir)
    helpers.run_command(f"git checkout {base_commit}", cwd=tmp_repo_dir)

    try:
        edited_files = _extract_edited_files(patch)
        candidate_files = []
        edited_file = ""
        desired_file = ""
        repo_path = Path(tmp_repo_dir)
        i = 0

        while i < len(edited_files) and not candidate_files:
            candidate_files.clear()

            # candidate: ".../x.js" => ".../x_spec.js"
            edited_path = Path(edited_files[i])
            stem = edited_path.stem
            suffix = edited_path.suffix
            desired_file = f"{stem}_spec{suffix}"

            for filepath in repo_path.rglob(desired_file):
                if "test/unit/" in filepath.as_posix():
                    candidate_files.append(filepath.as_posix())

            i += 1

        if candidate_files:
            candidate_file_relative = [y.replace(tmp_repo_dir + '/', '') for y in candidate_files]
            file_to_inject = _find_most_similar_matching_test_file(edited_file, candidate_file_relative)
            file_to_inject = tmp_repo_dir + '/' + file_to_inject
        else:
            co_edited_files = _find_co_edited_files(edited_files, tmp_repo_dir, 100)
            if not co_edited_files:
                co_edited_files = _find_co_edited_files(edited_files, tmp_repo_dir, 1000)
                if not co_edited_files:
                    return Path("test", "unit", desired_file).as_posix(), ""

            co_edited_files = sorted(co_edited_files, key=lambda x: -x[1])

            file_to_inject = None
            for co_edited_file in co_edited_files:
                if co_edited_file[0] and os.path.isfile(tmp_repo_dir + '/' + co_edited_file[0]):
                    file_to_inject = tmp_repo_dir + '/' + co_edited_file[0]
                    break

            if not file_to_inject:
                return Path("test", "unit", desired_file).as_posix(), ""

        test_content = Path(file_to_inject).read_text(encoding='utf-8')

    finally:
        helpers.run_command(f"git checkout {current_branch}", cwd=tmp_repo_dir)

    return Path(file_to_inject).as_posix().replace(tmp_repo_dir + '/', ''), test_content


def _keep_first_n_defs(parse_language: Language, source_code: str, n: int = 3) -> str:
    """
    Takes source code as input and returns a sliced version
    where all import/global statements, global comments, and JSDocs
    are retained, but only the first N global class/function definitions are kept,
    along with their comments, JSDocs, and decorators.

    Parameters:
        parse_language (Language): The language used to parse the source code
        source_code (str): The source code
        n (int): The number of global statements to keep

    Returns:
        str: The sliced code
    """

    tree = Parser(parse_language).parse(bytes(source_code, 'utf-8'))

    global_defs_count = 0
    source_lines = source_code.splitlines()
    kept_lines: set[int] = set()

    for root_child in tree.root_node.children:
        node_type = root_child.type
        if node_type in {"import_statement", "variable_declaration", "lexical_declaration", "comment"}:
            """
                variable_declaration: var x = 0
                lexical_declaration: const / let x = 0
                lexical_declaration: const foo = function() {}
                lexical_declaration: const foo = () => {}
            """
            kept_lines.update(range(root_child.start_point[0], root_child.end_point[0] + 1))
        elif node_type in {"function_declaration", "class_declaration"}:
            """
                function_declaration: function foo() {}
            """
            if global_defs_count < n:
                kept_lines.update(range(root_child.start_point[0], root_child.end_point[0] + 1))
                global_defs_count += 1

                if root_child.prev_sibling:
                    prev_node = root_child.prev_sibling
                    text = prev_node.text.decode("utf-8")
                    if text.startswith("@"):  # Decorators
                        kept_lines.update(range(prev_node.start_point[0], prev_node.end_point[0] + 1))

    result_lines = [source_lines[i] for i in sorted(kept_lines) if i < len(source_lines)]

    return "\n".join(result_lines)


def _extract_edited_files(diff_content: str) -> list:
    """
    Extracts the filenames of all edited files from a unified diff.

    Parameters:
        diff_content (str): The unified diff content as a string.

    Returns:
        list: A list of relative paths of the edited files.
    """

    matches = re.findall(r'^\+\+\+ b/(.+)$', diff_content, re.MULTILINE)
    return matches


def _find_most_similar_matching_test_file(source: str, candidates: list) -> str:
    """
    Finds the test file whose path is most similar to the code path.

    Parameters:
        source (str): Path to the code file
        candidates (list): List of test file paths

    Returns:
        str: The test file path most similar to the code path.
    """

    def _similarity(file_candidates):
        match_count = 0
        for source_part, candidate_part in zip(source.split(os.sep), file_candidates.split(os.sep)):
            if source_part == candidate_part:
                match_count += 1
            else:
                break
        return match_count

    return max(candidates, key=_similarity)


def _find_co_edited_files(file_list: list, tmp_repo_dir: str, n_last_commits: int = 10, n_files: int = 3) -> list:
    """
    Finds the most commonly co-edited file for each file in a list.

    Parameters:
        file_list (list): List of filepaths to analyze
        tmp_repo_dir (str): Path to the temporary repository
        n_last_commits (int): Number of last commits to look for
        n_files (int): Number of most common files to return

    Returns:
        list: A list of filepaths of most common co-edited files
    """

    common_files = []
    for file in file_list:
        commits = _get_last_n_commits(file, tmp_repo_dir, n_last_commits)
        co_edited_files = []
        for commit in commits:
            co_edited_files.extend(_get_files_in_commit(commit, tmp_repo_dir))

        co_edited_files = [f for f in co_edited_files if f != file and _is_test_file(f)]

        if co_edited_files:
            most_common_files = Counter(co_edited_files).most_common(n_files)
            common_files.extend(most_common_files)

    return common_files


def _is_test_file(filepath: str) -> bool:
    """
    Determines whether a file is a test file

    Parameters:
        filepath (str): The path to the file

    Returns:
        bool: Whether the file is a test file
    """

    is_in_test_folder = False
    parts = filepath.split('/')

    if "test/unit/" in filepath:
        is_in_test_folder = True

    if is_in_test_folder and 'spec' in parts[-1] and parts[-1].endswith("js"):
        return True
    else:
        return False


def _get_last_n_commits(filepath: str, tmp_repo_dir: str, n: int = 10) -> list:
    """
    Retrieves the last N commits of a file.

    Parameters:
        filepath (str): The path to the file
        tmp_repo_dir (str): Path to the temporary repository
        n (int): Number of commits to retrieve

    Returns:
        list: A list of commits
    """

    command = f"git log -n {n} --pretty=format:%H -- {filepath}"
    commits = helpers.run_command(command, cwd=tmp_repo_dir)
    return commits.splitlines() if commits else []


def _get_files_in_commit(commit_hash: str, tmp_repo_dir: str) -> list:
    """
    Gets all the files in a commit.

    Parameters:
        commit_hash (str): The commit hash for which to retrieve files
        tmp_repo_dir (str): Path to the temporary repository

    Returns:
        list: The list of files for the chosen commit
    """

    command = f"git show --name-only --pretty=format:'' {commit_hash}"
    files = helpers.run_command(command, cwd=tmp_repo_dir)
    return files.splitlines() if files else []
