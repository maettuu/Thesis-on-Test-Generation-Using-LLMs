import shutil
import re
import difflib
import ast
import tokenize
import subprocess
import os
import stat
import time
import json
import logging

from tree_sitter import Parser
from io import BytesIO
from pathlib import Path
from collections import Counter, defaultdict


logger = logging.getLogger(__name__)


def get_best_file_to_inject_golden(pr_diff_ctx, new_test):
    """The golden test patch may contain >1 edited test file. In that case,
    we seek the most similar (token-wise) to the generated test (new_test) and
    inject the new test there.
    """
    # Only consider files start with test*.py
    files_starting_with_test = [x for x in pr_diff_ctx.test_names if x.startswith('test')]

    r = {}
    for pr_file_diff in pr_diff_ctx.test_file_diffs:
        if files_starting_with_test and not pr_file_diff.name in files_starting_with_test:
            # If there is at least one file starting with test*, we skip files not starting with test*
            continue
        changed_funcs_or_classes, success = find_changed_funcs_or_classes(pr_file_diff.before, pr_file_diff.after)
        # changed_funcs_or_classes: [("function"/"class", name, code)]
        if success:
            r[pr_file_diff.name] = changed_funcs_or_classes

    # return the class/func with the highest token similarity with the
    # generated test
    new_test_tokens = extract_tokens_from_code(new_test)
    max_similarity = 0
    max_similarity_file = None
    max_similarity_class_or_func = None
    for file, class_or_func_arr in r.items():
        for class_or_func in class_or_func_arr:
            contents = class_or_func[2]
            tkns = extract_tokens_from_code(contents)

            if tkns:
                intersection = len(new_test_tokens & tkns)
                similarity_score = intersection / len(new_test_tokens)
                if similarity_score > max_similarity:
                    max_similarity = similarity_score
                    max_similarity_class_or_func = class_or_func
                    max_similarity_file = file

    success = max_similarity_class_or_func is not None
    return max_similarity_class_or_func, max_similarity_file, success


def find_changed_funcs_or_classes(initial_content, changed_content):
    """
    We want to find changed funcs or classes between two versions of a test file
    to locate in which place we should insert the model-generated test:
    we apply the golden test patch to the golden test file and check for changed
    funcs/classes and insert our model-generated test patch there
    """
    success = True # for handling errors in the higher level
    def extract_top_level_defs(content):
        """Extract top-level function and class definitions from the Python content."""
        tree = ast.parse(content)
        definitions = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                start_lineno = node.lineno
                end_lineno = node.end_lineno if hasattr(node, 'end_lineno') else None
                name = node.name
                type_ = 'class' if isinstance(node, ast.ClassDef) else 'function'
                definitions[name] = (type_, start_lineno, end_lineno)
        return definitions

    def extract_code_block(content, start, end):
        """Extract the specific code block based on line numbers."""
        lines = content.splitlines()
        return '\n'.join(lines[start - 1:end])

    try:
        initial_defs = extract_top_level_defs(initial_content)
        changed_defs = extract_top_level_defs(changed_content)
    except SyntaxError as e:
        # If the file content is not compilable we cannot use the AST to extract top level defs.
        # In this case, skip the instance
        success = False
        return [], success

    modified_or_missing = []

    # For model only uncomment these
    for name, (type_, start, end) in initial_defs.items():
        if name not in changed_defs:
            # If the definition is missing in changed_content
            code = extract_code_block(initial_content, start, end)
            modified_or_missing.append((type_, name, code))
        else:
            # Check if the content has changed
            initial_block = extract_code_block(initial_content, start, end)
            changed_type, changed_start, changed_end = changed_defs[name]
            changed_block = extract_code_block(changed_content, changed_start, changed_end)

            if list(difflib.unified_diff(initial_block.splitlines(), changed_block.splitlines())):
                modified_or_missing.append((type_, name, initial_block))

    # # For golden_and_model uncomment these
    # for name, (type_, start, end) in changed_defs.items():
    #     if name not in initial_defs:
    #         # If the definition is missing in changed_content
    #         code = extract_code_block(changed_content, start, end)
    #         modified_or_missing.append((type_, name, code))
    #     else:
    #         # Check if the content has changed
    #         changed_block = extract_code_block(changed_content, start, end)
    #         initial_type, initial_start, initial_end = initial_defs[name]
    #         initial_block = extract_code_block(initial_content, initial_start, initial_end)

    #         if list(difflib.unified_diff(initial_block.splitlines(), changed_block.splitlines())):
    #             modified_or_missing.append((type_, name, changed_block))

    return modified_or_missing, success


def extract_tokens_from_code(code):
    """
    Extracts all tokens from a Python code string using the tokenize module.
    Returns a set of token strings (ignores comments and whitespace).
    """
    tokens = set()
    try:
        for token in tokenize.tokenize(BytesIO(code.encode('utf-8')).readline):
            if token.type in {tokenize.NAME, tokenize.NUMBER, tokenize.STRING}:
                tokens.add(token.string)
    except tokenize.TokenError:
        pass  # Handle incomplete input gracefully
    return tokens


def get_contents_of_test_file_to_inject(
        parse_language,
        base_commit,
        golden_code_patch,
        repo_dir
):
    logger.info("Fetching test file for injection...")
    test_filename, test_file_content = find_file_to_inject(base_commit, golden_code_patch, repo_dir)
    if not test_file_content:
        logger.warning(f"No suitable test file {test_filename} found. New file created.")
        return test_filename, "", ""
    else:
        logger.success("Test file found")
        test_file_content_sliced = keep_first_N_defs(parse_language, test_file_content)

    return test_filename, test_file_content, test_file_content_sliced


def find_file_to_inject(base_commit: str, golden_code_patch: str, repo_dir):
    current_branch = run_command("git rev-parse --abbrev-ref HEAD", cwd=repo_dir)
    run_command(f"git checkout {base_commit}", cwd=repo_dir)

    try:
        edited_files = extract_edited_files(golden_code_patch)
        ### First search for the file "test_<x>.js" where "<x>.js" was changed by the golden patch
        for edited_file in edited_files:
            matching_test_files = []  # could be more than 1 matching files in different dirs

            # ".../x.js" => ".../x_spec.js"
            edited_path = Path(edited_file)
            stem = edited_path.stem  # filename without suffix
            suffix = edited_path.suffix  # “.py”, “.js”, etc.
            potential_test_file = f"{stem}_spec{suffix}"

            repo_path = Path(repo_dir)
            for file_path in repo_path.rglob(potential_test_file):
                # file_path.parts is a tuple of all path segments from repo_path down to the file
                if any(part.startswith("test") for part in file_path.parts):
                    # if you need a string path rather than a Path object:
                    matching_test_files.append(file_path.as_posix())
            if matching_test_files:  # stop in the first file for which we find (possibly >1) matching tests
                break

        if matching_test_files:
            ### Then, if the simple naming rule did not work, try Git History
            matching_test_files_relative = [y.replace(repo_dir + '/', '') for y in matching_test_files]  # make relative
            test_file_to_inject = find_most_similar_matching_test_file(edited_file, matching_test_files_relative)
            test_file_to_inject = repo_dir + '/%s' % test_file_to_inject  # make absolute again
        else:
            coedited_files = find_coedited_files(edited_files, repo_dir, 100)
            if not coedited_files:
                # if we did not find in the last 100 commits, go to last 1000 (only in pylint-dev__pylint-4661)
                coedited_files = find_coedited_files(edited_files, repo_dir, 1000)
                if not coedited_files:
                    return Path("test", "unit", potential_test_file).as_posix(), ""

            coedited_files = sorted(coedited_files, key=lambda x: -x[1])  # sort by # of co-edits

            test_file_to_inject = None
            for coedited_file in coedited_files:  # coedited_file is a tuple (fname, #coedits)
                # we need to check if these files still exist because they
                # come from a past commit
                if coedited_file[0] and os.path.isfile(repo_dir + '/' + coedited_file[0]):
                    test_file_to_inject = repo_dir + '/' + coedited_file[0]
                    break  # the first one we find that exists we keep it

            # if none of the coedited files exist anymore, create new test file
            if not test_file_to_inject:
                return Path("test", "unit", potential_test_file).as_posix(), ""

        # Read the contents of the test file
        test_content = Path(test_file_to_inject).read_text(encoding='utf-8')

    finally:
        run_command(f"git checkout {current_branch}", cwd=repo_dir)  # Reset to the original commit

    return Path(test_file_to_inject).as_posix(), test_content


def keep_first_N_defs(parse_language, source_code: str, N: int = 3) -> str:
    """
    Takes Javascript source code as input and returns a sliced version
    where all import/global statements, global comments, and JSDocs
    are retained, but only the first three global class/function definitions are kept,
    along with their comments, JSDocs, and decorators.
    """
    tree = Parser(parse_language).parse(bytes(source_code, 'utf-8'))
    root_node = tree.root_node

    result_lines = []
    global_defs_count = 0
    source_lines = source_code.splitlines()
    kept_lines = set()

    for node in root_node.children:
        node_type = node.type
        if node_type in {"import_statement", "variable_declaration", "lexical_declaration", "comment"}:
            """
                variable_declaration: var x = 0
                lexical_declaration: const / let x = 0
                lexical_declaration: const foo = function() {}
                lexical_declaration: const foo = () => {}
            """
            kept_lines.update(range(node.start_point[0], node.end_point[0] + 1))
        elif node_type in {"function_declaration", "class_declaration"}:
            """
                function_declaration: function foo() {}
            """
            if global_defs_count < N:
                kept_lines.update(range(node.start_point[0], node.end_point[0] + 1))
                global_defs_count += 1

                if node.prev_sibling:
                    prev_node = node.prev_sibling
                    text = prev_node.text.decode("utf-8")
                    if text.startswith("@"):  # Decorators
                        kept_lines.update(range(prev_node.start_point[0], prev_node.end_point[0] + 1))

    result_lines = [source_lines[i] for i in sorted(kept_lines) if i < len(source_lines)]

    return "\n".join(result_lines)


def extract_packages(base_commit: str, repo_dir):
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


def extract_relative_imports(base_commit:str, repo_dir):
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


# Function to run a shell command and return its output
def run_command(command, cwd=None):
    result = subprocess.run(command, cwd=cwd, shell=True, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else None


def remove_dir(path: Path, max_retries: int = 3, delay: float = 0.1, temp_repo: bool = False) -> None:
    def on_error(func, path, _) -> None:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    for attempt in range(max_retries):
        try:
            shutil.rmtree(path, onerror=on_error)
            if temp_repo: logger.success(f"Directory {path} removed successfully")
            return
        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"Failed attempt {attempt} removing {path}: {e}, retrying in {delay}s")
                time.sleep(delay)
            else:
                logger.error(f"Final attempt failed removing {path}, must be removed manually: {e}")


def extract_edited_files(diff_content):
    """
    Extract the filenames of all edited files from a unified diff.

    Parameters:
        diff_content (str): The unified diff content as a string.

    Returns:
        list: A list of relative paths of the edited files.
    """
    # Regular expression to capture the file paths from `+++ b/` lines
    matches = re.findall(r'^\+\+\+ b/(.+)$', diff_content, re.MULTILINE)
    return matches


def find_most_similar_matching_test_file(code_filepath, test_filepaths):
    """
    Find the test file whose path is most similar to the code path.

    Parameters:
        code_filepath (str): Path to the code file (e.g., "astropy/utils/misc.py").
        test_filepaths (list): List of test file paths (e.g.,
            ["astropy/utils/tests/test_misc.py", "astropy/visualization/wcsaxes/tests/test_misc.py"]
        ).

    Returns:
        str: The test file path most similar to the code path.
    """
    # Split the code filepath into components
    code_components = code_filepath.split(os.sep)

    def similarity(test_filepath):
        """Calculate similarity between the code path and a test file path."""
        test_components = test_filepath.split(os.sep)
        # Count the number of matching components from the start of the paths
        match_count = 0
        for code_comp, test_comp in zip(code_components, test_components):
            if code_comp == test_comp:
                match_count += 1
            else:
                break
        return match_count

    # Find the test file with the highest similarity
    most_similar_test = max(test_filepaths, key=similarity)
    return most_similar_test


# Function to find the most commonly co-edited file for each file in file_list
# starting from base_commit
def find_coedited_files(file_list, repo_dir, n_last_commits=10, n_files=3):

    common_files = []
    for file in file_list:
        # Get the last 10 commits for the current file
        commits = get_last_N_commits(file, repo_dir, n_last_commits)
        # Get all files edited in the same commits
        coedited_files = []
        for commit in commits:
            coedited_files.extend(get_files_in_commit(commit, repo_dir))

        # Remove the file itself from the list of coedited files
        coedited_files = [f for f in coedited_files if f != file]

        # Filter files starting with "test*"
        coedited_files = [f for f in coedited_files if _is_test_file(f)]

        # Find the most common coedited file and its count
        if coedited_files:
            most_common_files = Counter(coedited_files).most_common(n_files)
            common_files.extend(most_common_files)

    return common_files


def _is_test_file(filepath: str, test_folder: str = '') -> bool:
    """
    Determines whether a file is a test file

    Parameters:
        filepath (str): The path to the file
        test_folder (str, optional): The path to the folder where the test file is located

    Returns:
        bool: Whether the file is a test file
    """

    is_in_test_folder = False
    parts = filepath.split('/')

    # if a predefined test folder is given, we check if the filepath contains it
    if test_folder:
        is_in_test_folder = (test_folder in filepath)
    else:
        # otherwise, we want the file to be in a dir where at least one folder in the dir path starts with test
        for part in parts[:-1]:
            if part.startswith('test'):
                is_in_test_folder = True
                break

    if is_in_test_folder and 'spec' in parts[-1] and parts[-1].endswith("js"):
        return True
    else:
        return False


def get_first_test_file(root_dir: str) -> str | None:
    """
    Our last resort: find the first file in a subfolder where at least one component starts with 'test'
    and the filename itself also starts with 'test'.

    :param root_dir: The root directory to search in.
    :return: The first matching file path relative to root_dir, or None if no such file exists.
    """

    # First search in folders starting with "test" for files starting with "test"
    for dirpath, _, filenames in os.walk(root_dir):
        if not any(
                part.startswith(".") for part in dirpath.split(os.sep)
        ) and any(
            part.startswith("test") for part in dirpath.split(os.sep)
        ):
            for filename in filenames:
                if "spec" in filename:
                    return os.path.relpath(os.path.join(dirpath, filename), root_dir)

    # If nothing is found, search only for files starting with "test" (e.g., requests repo in old commits)
    for dirpath, _, filenames in os.walk(root_dir):
        if not any(part.startswith(".") for part in dirpath.split(os.sep)):
            for filename in filenames:
                if "spec" in filename:
                    return os.path.relpath(os.path.join(dirpath, filename), root_dir)
    return None


# Function to get the last N commits that edit a file
def get_last_N_commits(file_path, repo_dir, N=10):
    command = f"git log -n {N} --pretty=format:'%H' -- {file_path}"
    commits = run_command(command, cwd=repo_dir)
    return commits.splitlines() if commits else []


# Function to get the files edited in a specific commit
def get_files_in_commit(commit_hash, repo_dir):
    command = f"git show --name-only --pretty=format:'' {commit_hash}"
    files = run_command(command, cwd=repo_dir)
    return files.splitlines() if files else []
