import os
import json
from pathlib import Path
import re


def extract_failure_type(file_path: str, fallback = "NaN") -> [str, str | None]:
    """
    Reads the given file.

    Parameters:
        file_path (string): Path to the file
        fallback (string, optional): Defaults to "NaN"

    Returns:
        str:
            - 'GulpError' if the file has fewer than 80 lines
            - the line immediately after the first occurrence of 'Message:'
            - if 'Message:' is not found, the first line containing 'SyntaxError:'
            - if 'SyntaxError:' is not found, check for missing executions
            - fallback otherwise
        str | None: failure content
    """

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except:
        return f'ReadError', None

    # check line count
    if len(lines) < 80:
        return 'GulpError', None

    # search for 'Message:'
    for idx, line in enumerate(lines):
        if 'Message:' in line:
            if idx + 1 < len(lines):
                try:
                    response = lines[idx + 1].rstrip("\n")
                    if 'Expected' in response:
                        return 'ExpectedNotActual', response.strip()
                    split = response.split(':', 1)
                    return split[0].strip(), split[1].strip()
                except:
                    return fallback, None
            else:
                return fallback, None

    # search for 'SyntaxError:'
    for line in lines:
        if 'SyntaxError:' in line:
            return 'SyntaxError', line.split(': ', 1)[1].strip()

    # check missing execution
    for line in lines:
        if '0 specs, 0 failures' in line:
            return 'PatchFailure', None

    return fallback, None


def is_fail_to_pass(before_path: str, after_path: str) -> bool:
    """
    Checks content of before and after files.

    Parameters:
        before_path (str): Path to the before file
        after_path (str): Path to the after file

    Returns:
        bool: True if before contains '1 spec, 1 failure' and after contains '1 spec, 0 failures', False otherwise
    """

    try:
        with open(before_path, 'r', encoding='utf-8') as bf:
            before = bf.read()
        with open(after_path, 'r', encoding='utf-8') as af:
            after = af.read()
    except:
        return False

    return '1 spec, 1 failure' in before and '1 spec, 0 failures' in after


def analyze_generation_folder(gen_path: Path, base_id: str, sub_name: str, stats: dict, tests: dict) -> bool | None:
    """
    Checks for before.txt and after.txt in gen_path and prints messages or errors.

    Parameters:
        gen_path (Path): Path to the 'generation' directory
        base_id (str): ID pointing to current LLM
        sub_name (str): Name of the current sub folder (identifies attempt number)
        stats (dict): Dictionary to save failure types
        tests (dict): Dictionary to save generated tests

    Returns:
        bool | None: True if test is Fail-to-Pass, False otherwise
    """

    before_path = os.path.join(gen_path, 'before.txt')
    after_path = os.path.join(gen_path, 'after.txt')
    test_path = os.path.join(gen_path, 'generated_test.txt')

    def save_in_stats(error_type, error_message=''):
        stats.setdefault(error_type, {}).setdefault(base_id, {})[sub_name] = error_message

    def save_in_tests(file):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
                tests.setdefault(base_id, {})[sub_name] = content
        except:
            pass

    # 1. Check presence
    if os.path.isfile(before_path) and not os.path.isfile(after_path):
        save_in_stats('PassToX')
        return
    if not (os.path.isfile(before_path) and os.path.isfile(after_path)):
        save_in_stats('NoFilesFound')
        return

    if os.path.isfile(test_path):
        save_in_tests(test_path)

    # 2. Extract
    before_error, before_message = extract_failure_type(before_path)
    after_error, after_message = extract_failure_type(after_path)

    # 3. Analyze
    if before_error == after_error:
        save_in_stats(before_error, before_message)
    else:
        save_in_stats(before_error, before_message)
        save_in_stats(after_error, after_message)
        save_in_stats('DoubleEntries')

    # 4. Check for Fail-to-Pass
    return is_fail_to_pass(before_path, after_path)


def execute_analysis(root_dir: Path) -> None:
    """
    Traverses root_dir to find 'generation' folders and analyze files.

    Parameters:
        root_dir (Path): The root directory to analyze
    """

    root_dir = Path(root_dir)
    if not root_dir.is_dir():
        print(f"Root directory not found: {root_dir}")
        return

    stats = {}
    tests = {}
    fix_ids = set()

    # loop first-level directories
    for rc_path in sorted(root_dir.iterdir()):
        if not rc_path.is_dir():
            continue

        match = re.search(r'mozilla__pdf\.js-(\d+)_', rc_path.name)
        base_id = match.group(1) if match else rc_path.name

        # loop second-level directories
        for sc_path in sorted(rc_path.iterdir()):
            if not sc_path.is_dir():
                continue

            # enter 'generation' folder
            gen_path = sc_path / 'generation'
            if gen_path.is_dir():
                test_generated = analyze_generation_folder(gen_path, base_id, sc_path.name, stats, tests)
                if test_generated:
                    fix_ids.add(base_id)

    # remove entries for fix base_ids from stats
    for err in list(stats.keys()):
        for bid in list(stats[err].keys()):
            if bid in fix_ids:
                del stats[err][bid]
        if not stats[err]:
            del stats[err]

    # remove entries for fix base_ids from tests
    for bid in list(tests.keys()):
        if bid in fix_ids:
            del tests[bid]

    # save stats to JSON
    output_file = root_dir / 'stats.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    print(f"Stats written to {output_file}")

    # save tests to JSON
    output_file = root_dir / 'tests.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(tests, f, indent=2)
    print(f"Tests written to {output_file}")


    print(f"SUCCESS: {len(fix_ids)} fixes")

    # prepare sorted keys
    keys = sorted(k for k in stats.keys() if k != 'NaN') + (['NaN'] if 'NaN' in stats else [])
    total_entries = 0

    # print counts per failure type, sorted alphabetically except 'NaN' last
    for failure_type in keys:
        count = sum(len(ids) for ids in stats[failure_type].values())
        total_entries = total_entries - count if failure_type == 'DoubleEntries' else total_entries + count
        entries = 'entry' if count == 1 else 'entries'
        print_failure = 'ImportError' if failure_type == 'Error' else failure_type
        print(f"{print_failure}: {count} {entries}")

    # print overall total
    print(f"Total entries: {total_entries}")


if __name__ == '__main__':
    execute_analysis(Path("results_with_pdf_context"))
    execute_analysis(Path("results_without_pdf_context"))
