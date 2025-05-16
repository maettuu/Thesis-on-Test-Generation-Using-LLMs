import shutil
import re
import difflib
import ast
import tokenize
import subprocess
import os
import stat
import time

from tree_sitter import Parser, Tree, Node
from io import BytesIO
from pathlib import Path
from collections import Counter

from .config import logger
from .webhook_execution_error import WebhookExecutionError


def is_test_file(filepath, test_folder=''):
    is_in_test_folder = False
    parts = filepath.split('/')

    # If a predefined test folder is given, we check if the filepath contains it
    if test_folder:
        is_in_test_folder = (test_folder in filepath)
    else:
        # Otherwise, we want the file to be in a dir where at least one folder in the dir path starts with test
        for part in parts[:-1]:
            if part.startswith('test'):
                is_in_test_folder = True
                break

    if is_in_test_folder and 'spec' in parts[-1] and parts[-1].endswith("js"):
        return True
    else:
        return False


def extract_offsets_from_stderr(stderr: str):
    """
    Parses stderr messages from patch application and returns an offset array.
    Each element i in the array corresponds to the offset of the i-th file,
    with an assumption that all hunks of a file have the same offset.

    Args:
        stderr (str): The stderr message from the patch application.

    Returns:
        list: A list of offsets, where each offset corresponds to a file.
              If no offset is mentioned for a file, the value is 0.

    Raises:
        AssertionError: If multiple hunks in the same file have different offsets.
        AssertionError: If Hunk #1 is missing from a file but later hunks exist.

    Example:
        Input:
            stderr_text = \"\"\"
            Checking patch a_lib_matplotlib_axes__base.py...
            Hunk #1 succeeded at 3264 (offset 2 lines).
            Hunk #2 succeeded at 3647 (offset 2 lines).
            Checking patch a_lib_matplotlib_ticker.py...
            Checking patch a_lib_mpl_toolkits_mplot3d_axes3d.py...
            Applied patch a_lib_matplotlib_axes__base.py cleanly.
            Applied patch a_lib_matplotlib_ticker.py cleanly.
            Applied patch a_lib_mpl_toolkits_mplot3d_axes3d.py cleanly.
            \"\"\"

        Output:
            [2, 0, 0]
    """
    file_pattern = re.compile(r'Checking patch (.*?)\.\.\.')
    hunk_pattern = re.compile(r'Hunk #(\d+) succeeded at \d+ \(offset ([+-]?\d+) line(?:s?)\)')

    current_file = None
    file_offsets = {}
    first_hunk_seen = {}

    for line in stderr.splitlines():
        file_match = file_pattern.match(line)
        if file_match:
            current_file = file_match.group(1)
            file_offsets[current_file] = None  # Default to None to detect first offset
            first_hunk_seen[current_file] = False

        hunk_match = hunk_pattern.search(line)
        if hunk_match and current_file:
            hunk_number = int(hunk_match.group(1))
            offset = int(hunk_match.group(2))

            if hunk_number == 1:
                first_hunk_seen[current_file] = True
            else:
                assert first_hunk_seen[current_file], \
                    f"OffsetHunk #1 missing for {current_file}, but later hunks exist."

            if file_offsets[current_file] is None:
                file_offsets[current_file] = offset  # Set initial offset
            else:
                assert file_offsets[current_file] == offset, \
                    f"Mismatched offsets for {current_file}: {file_offsets[current_file]} vs {offset}"

    return [offset if offset is not None else 0 for offset in file_offsets.values()]


def extract_test_descriptions(parse_language, pr_file_diff) -> list:
    # Extract string of the type "fname scope test"
    _, contributing_tests_old = build_call_expression_scope_map(
        Parser(parse_language).parse(bytes(pr_file_diff.before, 'utf-8'))
    )
    test2scope, contributing_tests_new = build_call_expression_scope_map(
        Parser(parse_language).parse(bytes(pr_file_diff.after, 'utf-8'))
    )

    contributing_tests = find_changed_tests(contributing_tests_old, contributing_tests_new)
    test2test_content = []
    if contributing_tests:
        for test in contributing_tests:
            scope = test2scope.get(test, "")
            if scope == "":
                pass
            elif scope == "global":
                test2test_content.append(test)
            else: # describe scope
                test2test_content.append(f"{scope} {test}")

    return test2test_content


def build_call_expression_scope_map(tree: Tree) -> tuple:
    expression_map = {}
    test_cases = {}

    def visit_body(node: Node, scope_name: str) -> None:
        # Visit the describe body if available
        for child in get_call_expression_content(node):
            visit_node(child, scope_name)

    def visit_node(node: Node, scope_name: str = "global") -> None:
        expression_type = get_call_expression_type(node)
        if expression_type == "it":
            new_scope = get_call_expression_description(node, "<it>")
            expression_map[new_scope] = scope_name
            test_cases[new_scope] = node.text.decode("utf-8")

        elif expression_type == "describe":
            new_scope = get_call_expression_description(node, "<describe>")
            if scope_name != "global":
                new_scope = f"{scope_name} {new_scope}"

            visit_body(node, new_scope)

    for root_child in tree.root_node.children:
        visit_node(root_child)
    return expression_map, test_cases


def find_changed_tests(old_tests: dict, new_tests: dict) -> list[str]:
    """Find tests that have changed between two versions of a Javascript file."""
    changed_tests = []

    for name, body in new_tests.items():
        old_body = old_tests.get(name)
        if old_body is None:
            # Function is new
            changed_tests.append(name)
        elif old_body and old_body != body:
            # Function exists but has changed
            diff = list(difflib.unified_diff(old_body.splitlines(), body.splitlines()))
            if diff:
                changed_tests.append(name)

    return changed_tests


def get_call_expression_content(node: Node) -> list:
    """Returns the content of a call expression"""
    call_expression = get_call_expression(node)
    if not call_expression:
        return []
    args = call_expression.child_by_field_name("arguments")
    content = next((
        child for child in args.named_children
        if child.type in {"function_expression", "arrow_function"}
    ), None)
    body = content.child_by_field_name("body")
    return body.named_children if body else []


def get_call_expression(node: Node) -> Node:
    """Returns the call expression of an expression statement."""
    call_expression = next((
        child for child in node.named_children
        if child.type == "call_expression"
    ), None)
    return call_expression


def get_call_expression_type(node: Node, fallback="") -> str:
    """Returns the type of a call expression (i.e., 'describe', 'it')"""
    call_expression = get_call_expression(node)
    if not call_expression:
        return fallback
    callee = call_expression.child_by_field_name("function")
    return callee.text.decode("utf-8") if callee.type == "identifier" else fallback


def get_call_expression_description(node: Node, fallback="") -> str:
    """Returns the description (i.e., name) of a call expression"""
    call_expression = get_call_expression(node)
    if not call_expression:
        return fallback
    args = call_expression.child_by_field_name("arguments")
    identifier = next((
            child for child in args.named_children
            if child.type in {"string", "binary_expression"}
        ), None)
    raw_name = identifier.text.decode("utf-8") if identifier else fallback
    # 1) Remove the quotes and pluses
    clean_name = (
        raw_name.replace('"', '')
        .replace('+', '')
        .replace("'", '')
        .replace("`", '')
    )
    # 2) Turn any literal \n or \t (or others) into a space
    clean_name = (
        clean_name.replace('\n', ' ')
        .replace('\t', ' ')
        .replace('\r', ' ')
    )
    # 3) Collapse any runs of whitespace into one space
    return ' '.join(clean_name.split())


def adjust_function_indentation(function_code: str) -> str:
    """
    Adjusts the indentation of a Javascript function so that the function definition
    has no leading spaces, and the internal code indentation is adjusted accordingly.

    :param function_code: A string representing the Javascript function.
    :return: The adjusted function code as a string.

    # Example Usage
    function_code = \"\"\"
        function exampleFunction(param) {
            if (param) {
                console.log("Hello, world!");
            } else {
                console.log("Goodbye, world!");
            }
        }
    \"\"\"

    adjusted_code = adjust_function_indentation(function_code)
    logger.info(adjusted_code)
    """
    lines = function_code.splitlines()

    if not lines:
        return ""

    # Find the leading spaces of the first non-empty line
    first_non_empty_line = next(line for line in lines if line.strip())
    leading_spaces = len(first_non_empty_line) - len(first_non_empty_line.lstrip())

    # Adjust the indentation by removing the leading spaces
    adjusted_lines = []
    for line in lines:
        if line.strip():  # Non-empty line
            adjusted_lines.append(line[leading_spaces:])
        else:  # Empty line
            adjusted_lines.append("")

    return "\n".join(adjusted_lines)


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


def append_function(parse_language, file_content: str, new_function: str, insert_in_block: str = "NOBLOCK") -> str:
    """
    Append the function new_function to file_content. If insert_in_class is a 'describe' block name,
    insert new_function as a method of that block. Otherwise, insert new_function at the bottom
    of the file_content.

    This handles the indentation.
    """
    # Parse the content using tree-sitter
    tree = Parser(parse_language).parse(bytes(file_content, 'utf-8'))

    if insert_in_block != "NOBLOCK":
        # Search for the specified class
        target_class = None
        for root_child in tree.root_node.children:
            if (root_child.type == "expression_statement"
                    and get_call_expression_description(root_child) == insert_in_block):
                target_class = root_child
                break

        if target_class is None:
            raise ValueError(f"Describe block '{insert_in_block}' not found in the file content!")

        # Find the indentation level of the class
        lines = file_content.splitlines()
        class_start_line = target_class.start_point[0]
        class_indentation = len(lines[class_start_line]) - len(lines[class_start_line].lstrip())

        # Locate the last method in the class
        last_method = None
        for child in get_call_expression_content(target_class):
            if child.type == "expression_statement":
                last_method = child

        if last_method:
            # Insert after the last nested block
            last_code_line = last_method.end_point[0] + 1  # Use end_point for accurate insertion
        else:
            # If no nested block, insert at the end of the root block
            last_code_line = target_class.end_point[0] + 1

        last_line_content = lines[last_code_line - 1]
        indentation = len(last_line_content) - len(last_line_content.lstrip())

    else:
        # Default behavior: Append to the bottom of the file
        top_level_items = []

        for root_child in tree.root_node.children:
            if root_child.type == "expression_statement":
                top_level_items.append(root_child)

        if not top_level_items:
            raise ValueError("No top-level blocks found in the file content!")

        # Find the last top-level item
        last_item = top_level_items[-1]

        if get_call_expression_type(last_item) == "describe":  # last block was 'describe'
            # Handle blocks by finding the nested block
            last_method = None
            for child in get_call_expression_content(last_item):
                if child.type == "expression_statement":
                    last_method = child

            if not last_method:
                raise ValueError(
                    f"No nested blocks found in the describe block '{get_call_expression_description(last_item)}'!"
                )

            # Determine indentation
            last_func_line = last_method.start_point[0]  # line before the last block
            last_code_line = last_method.end_point[0] + 1  # last code line of the above block

        else:  # last function was a function in the top-level, not inside a class
            # For top-level functions
            last_func_line = last_item.start_point[0]  # line before the last block
            last_code_line = last_item.end_point[0] + 1  # last code line of the above block

        # Extract indentation
        lines = file_content.splitlines()
        last_func_line_content = lines[last_func_line]
        indentation = len(last_func_line_content) - len(last_func_line_content.lstrip())

    # Add the new function
    indented_new_function = "\n".join(
        " " * indentation + line if line.strip() else "" for line in new_function.splitlines()
    )

    # updated_content = file_content.rstrip() + "\n\n" + indented_new_function + "\n"
    updated_lines = lines[:last_code_line] + ["\n" + indented_new_function] + lines[last_code_line:]
    return "\n".join(updated_lines)


def get_contents_of_test_file_to_inject(
        parse_language,
        base_commit,
        golden_code_patch,
        pr_id,
        repo_dir
):
    test_filename, test_file_content = find_file_to_inject(base_commit, golden_code_patch, repo_dir)
    if not test_file_content:
        logger.warning(f"[!] No suitable test file {test_filename} found. New file created.")
        return test_filename, "", ""
    else:
        test_file_content_sliced = keep_first_N_defs(parse_language, test_file_content)

    return test_filename, test_file_content, test_file_content_sliced


def find_file_to_inject(base_commit: str, golden_code_patch: str, repo_dir):
    base_commit = base_commit
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


# Function to run a shell command and return its output
def run_command(command, cwd=None):
    result = subprocess.run(command, cwd=cwd, shell=True, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else None


def remove_dir(path: Path, max_retries: int = 3, delay: float = 0.1) -> None:
    def on_error(func, path, _) -> None:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    for attempt in range(max_retries):
        try:
            shutil.rmtree(path, onerror=on_error)
            return
        except Exception as e:
            if attempt < max_retries:
                logger.warning("[!] Failed attempt {attempt} removing {path}: {e}, retrying in {delay}s")
                time.sleep(delay)
            else:
                logger.error(f"[!] Final attempt failed removing {path}: {e}")
                raise WebhookExecutionError(f'Failed to remove temp directory, must be removed manually')


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
        coedited_files = [f for f in coedited_files if is_test_file(f)]

        # Find the most common coedited file and its count
        if coedited_files:
            most_common_files = Counter(coedited_files).most_common(n_files)
            common_files.extend(most_common_files)

    return common_files


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
