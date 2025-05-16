import subprocess
import difflib
import os
import re

from pathlib import Path

from .config import logger
from . import helpers
from .webhook_execution_error import WebhookExecutionError


def unified_diff_with_function_context(string1, string2, fname="tempfile.py", context_lines=3):
    """
    Writes two input strings to temporary files and uses `git diff --no-index`
    to compute the diff, including function context. This is important when you feed a diff
    to a model.

    Parameters:
    - string1: Original file content.
    - string2: Modified file content.
    - fname: The filename to simulate in the diff output.
    - context_lines: The number of context lines to show in the diff.

    Returns:
    - A string containing the Git-formatted diff.
    """

    temp_dir = './tmp_diff/'

    # Ensure the temp directory exists
    if not Path(temp_dir).exists():
        Path(temp_dir).mkdir()
    try:
        file_dir = "/".join(fname.split('/')[:-1])
        Path(temp_dir, file_dir).mkdir(parents=True)

        file1 = os.path.join(temp_dir, f"{fname}.oldfordiffonly")
        file2 = os.path.join(temp_dir, f"{fname}.newfordiffonly")

        # Write original content
        Path(file1).write_text(string1, encoding="utf-8")

        # Write modified content
        Path(file2).write_text(string2, encoding="utf-8")

        # Run `git diff --no-index`
        result = subprocess.run(
            ["git", "diff", "-p", f"-U{context_lines}", "--no-index", file1, file2],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        diff = result.stdout.strip()
        diff = diff.replace(temp_dir, '')  # make paths relative to target repo again
        diff = diff.replace(f"{fname}.oldfordiffonly", fname)  # >>
        diff = diff.replace(f"{fname}.newfordiffonly", fname)  # >>
        diff_lines = diff.splitlines()
        diff_lines.pop(1)  # this is the "index 09b...." line
        diff = "\n".join(diff_lines)
        return diff
    finally:
        helpers.remove_dir(Path(temp_dir))


def unified_diff(string1, string2, fromfile="original", tofile="modified", context_lines=3):
    """
    Prints the unified diff format of two strings. This is needed to calculate the diff
    given the new test file contents, since the evaluation harness works with the diff.

    Parameters:
        string1 (str): The original string.
        string2 (str): The modified string.
        fromfile (str): Name of the "from" file in the diff output.
        tofile (str): Name of the "to" file in the diff output.
        context_lines (int): Number of lines before and after the changes. Default is 3.

    # Example usage
    original_text = \"\"\"line 1
    line 2
    line 3\"\"\"

    modified_text = \"\"\"line 1
    line 2 modified
    line 3
    line 4 added\"\"\"

    unified_diff(original_text, modified_text)

    """
    fromfile = "a/" + fromfile
    tofile = "b/" + tofile

    # Split the strings into lines
    lines1 = string1.splitlines(keepends=True)
    lines2 = string2.splitlines(keepends=True)

    # Generate the unified diff
    diff = difflib.unified_diff(lines1, lines2, fromfile=fromfile, tofile=tofile, n=context_lines)

    git_header = f"diff --git {fromfile} {tofile}\n"

    # Print the diff
    return git_header + "".join(diff)


def apply_patch(file_content_arr, patch):
    """
    Apply a patch to file_content using the equivalent of "git apply".

    Parameters:
        file_content (str): The original content of the file.
        patch (str): The patch content in unified diff format.

    Returns:
        str: The updated file content after applying the patch.

    IMPORTANT: For `git apply` (and hence, this function) to run, it must be called from
    within a git repository. Alternatively we would have to use `apply` which is less nice.
    """
    temp_dir = './tmp/'
    if not Path(temp_dir).exists():
        Path(temp_dir).mkdir()

    # Important: in order for "git apply" to work, it needs to be inside of a .git repo
    # so we initialize one and delete the .git at the end
    res = subprocess.run(
        ["git", "init", "."],
        check=True,
        cwd=temp_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # Extract all the names of the changed files and save them in a list.
    # Each element of the list is of the form "a/<file_path>"
    patch_lines = patch.splitlines()
    original_file_aprefix_arr = []
    for line in patch_lines:
        if line.startswith("--- "):
            original_file_aprefix = line.split(" ")[1]
            original_file_aprefix_arr.append(original_file_aprefix)

    # Files mentioned in the patch should be the same number as the ones
    # whose content is provided. We also assume that the i-th file in the
    # first content corresponds to the i-th file in the second.
    assert len(original_file_aprefix_arr) == len(file_content_arr), patch

    file_path_arr = []
    for (original_file_aprefix, file_content) in zip(original_file_aprefix_arr, file_content_arr):
        # remove intermediate folders: "a/django/tests/x.py" => "a/x.py"
        file_path = original_file_aprefix.replace('/', '_')

        file_path_arr.append(file_path)
        file_path_aprefix = 'a/' + file_path
        file_path_bprefix = 'b/' + file_path
        patch = patch.replace(original_file_aprefix, file_path_aprefix)  # update patch accordingly
        original_file_bprefix = 'b/' + '/'.join(original_file_aprefix.split('/')[1:])
        patch = patch.replace(original_file_bprefix, file_path_bprefix)

        # Write the file content and patch content to their respective files
        Path(temp_dir, file_path).write_text(file_content, encoding="utf-8")

    patch_path = "patch.diff"
    Path(temp_dir, patch_path).write_text(patch, encoding="utf-8")

    # Apply the patch using git apply
    try:
        # subprocess.run(["git", "apply", patch_path], check=True)
        # with open(patch_path, "r", encoding="utf-8") as file:
        # result = subprocess.run(
        #     ["patch", "-p1"],
        #     stdin=file,  # equivalent to "patch -p1 > patch.diff" but redirection does not work with subprocess
        #     check=False,  # Raises an exception if the command fails
        #     text=True,
        #     capture_output=True,  # Captures stdout and stderr
        # )
        res = subprocess.run(
            ["git", "apply", "--reject", patch_path],
            check=True,
            capture_output=True,
            text=True,
            cwd=temp_dir
        )
    except subprocess.CalledProcessError as e:
        os.remove(temp_dir + patch_path)
        for file_path in file_path_arr:
            os.remove(temp_dir + file_path)
            # pass
        helpers.remove_dir(Path(temp_dir, ".git"))
        ###
        helpers.remove_dir(Path(temp_dir))
        ###
        logger.error(f"Failed to apply patch: {e}")
        raise WebhookExecutionError(f"Failed to apply patch")

    updated_content_all_files = []
    for file_path in file_path_arr:
        # Read the updated file content
        updated_content = Path(temp_dir, file_path).read_text(encoding="utf-8")

        os.remove(temp_dir + file_path)
        updated_content_all_files.append(updated_content)

    os.remove(temp_dir + patch_path)
    helpers.remove_dir(Path(temp_dir, ".git"))
    ###
    helpers.remove_dir(Path(temp_dir))
    ###

    return updated_content_all_files, res.stderr


def get_missed_lines_and_decorate_patch(
        pr_diff_ctx,
        code_content_after_arr,
        offsets,
        coverage_report
):
    # In code_after_labeled, we will label every line that is not covered with a
    # comment: "# NOT COVERED"
    code_after_labeled_arr = []
    modified_and_missed_lines = []

    code_patch_entries = zip(pr_diff_ctx.code_names,
                             code_content_after_arr,
                             offsets,
                             range(len(pr_diff_ctx.code_names)))

    for (edited_file, code_after, offset, ii) in code_patch_entries:
        code_after_labeled = code_after.splitlines()

        this_file_coverage = [l for l in coverage_report.splitlines() if l.startswith(edited_file)]
        if not this_file_coverage:
            # If the file does not even appear in coverage.txt, it means
            # that it was not covered at all
            all_lines_in_file_missed = True
        else:
            all_lines_in_file_missed = False
            this_file_coverage = this_file_coverage[0]
            line_range_str = this_file_coverage.split('%')[-1]
            missed_lines, missed_branches = parse_missed_lines_and_branches(line_range_str)

        line_number_of_edited_lines = get_line_number_of_edited_lines(pr_diff_ctx.golden_code_patch)
        for (line, line_no, line_file) in line_number_of_edited_lines:
            if line_file == edited_file:
                # + offset because of fuzzy diff | -1 because it's 1-indexed
                line_no_adjusted = line_no + offset - 1
                assert line == code_after.splitlines()[line_no_adjusted].strip(), "Line mismatch"
                # Make it 1-indexed again
                if all_lines_in_file_missed or line_no_adjusted + 1 in missed_lines:
                    # here it's 0-indexed
                    modified_and_missed_lines.append(code_after.splitlines()[line_no_adjusted].strip())
                    code_after_labeled[line_no_adjusted] = code_after_labeled[line_no_adjusted] + " ###NOT COVERED###"

        code_after_labeled_arr.append("\n".join(code_after_labeled) + "\n")

    golden_patch_labeled = ""
    for (c, c_labeled, fname) in zip(pr_diff_ctx.code_before, code_after_labeled_arr, pr_diff_ctx.code_names):
        golden_patch_labeled += unified_diff(c,
                                             c_labeled,
                                             fromfile=fname,
                                             tofile=fname) + "\n"

    # if modified_and_missed_lines is empty, golden_patch_labeled is the same as golden_patch
    return modified_and_missed_lines, golden_patch_labeled


def parse_missed_lines_and_branches(line_string):
    """
    Parses a string describing missed line ranges and branches, returning two outputs.

    Args:
        line_string (str): The input string describing missed lines and branches.

    Returns:
        tuple: A tuple containing:
            - A list of integers representing the missed lines.
            - A list of tuples representing missed branches as (x, y).
    """
    missed_lines = []
    missed_branches = []

    # Correct regex to handle both '-' and '->'
    pattern = r'(\d+)(?:\s*(-|->)\s*(\d+))?'

    # Find all matches
    matches = re.findall(pattern, line_string)

    for match in matches:
        start = int(match[0])
        if match[1] == '->':
            # Handle missed branches
            end = int(match[2])
            missed_branches.append((start, end))
        else:
            # Handle missed lines and ranges
            end = int(match[2]) if match[2] else start
            missed_lines.extend(range(start, end + 1))

    return missed_lines, missed_branches


def get_line_number_of_edited_lines(diff_string):
    """
    Parse a unified diff string to find all added lines, their line numbers,
    and the file being edited.

    Args:
        diff_string (str): The unified diff string.

    Returns:
        list: A list of tuples where each tuple contains:
              - The added line (str)
              - The line number in the updated file (int)
              - The file being edited (str)
    """
    added_lines = []
    current_file = None
    updated_line_number = None

    # Split the diff into lines
    lines = diff_string.splitlines()

    for line in lines:
        # Detect file being edited from "+++" lines
        if line.startswith("+++"):
            match = re.match(r"\+\+\+ b/(.+)", line)
            if match:
                current_file = match.group(1)
            continue

        # Match line number changes from @@ -old_start,old_length +new_start,new_length @@
        header_match = re.match(r"@@ -\d+,?\d* \+(\d+),?\d* @@", line)
        if header_match:
            updated_line_number = int(header_match.group(1))
            continue

        # Detect added lines (those starting with '+')
        if line.startswith('+') and not line.startswith('+++'):
            added_line = line[1:].strip()  # Strip the '+' and any surrounding whitespace
            if updated_line_number is not None and current_file is not None:
                added_lines.append((added_line, updated_line_number, current_file))
                updated_line_number += 1

        # Detect unchanged lines (those not starting with '-', '+', or '@')
        elif not line.startswith('-') and not line.startswith('@'):
            if updated_line_number is not None:
                updated_line_number += 1

    return added_lines
