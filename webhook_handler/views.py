import hmac
import hashlib
import json
import requests
import sys
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
import re
import os
import logging
from datetime import datetime
import traceback
import subprocess
import jwt
import time
from .paper_utils import *

logger = logging.getLogger("myapp")
logger.debug("Entered webhook")

# Directory where webhook requests will be saved
is_in_server = os.path.isdir("/home/ubuntu")
if is_in_server:
    WEBHOOK_RAW_LOG_DIR = "/home/ubuntu/logs/raw/" # for raw requests
    WEBHOOK_LOG_DIR     = "/home/ubuntu/logs/" # for parsed requests
else:
    WORKING_DIR = os.getcwd()
    WEBHOOK_RAW_LOG_DIR = os.path.join(WORKING_DIR, "bot_logs") # for raw requests
    WEBHOOK_LOG_DIR     = os.path.join(WORKING_DIR, "bot_logs") # for parsed requests

# GitHub webhook secret. Must be the same when setting up the hook in GH.
GITHUB_WEBHOOK_SECRET = "1234"

# GitHub personal access token
GITHUB_TOKEN = "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"

HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": f"Bearer {GITHUB_TOKEN}",
}

openai.api_key = OPENAI_API_KEY

comment_template_generation = """Hi! 🤖 The test below is automatically generated and serves as a regression test for this PR because it:
- passes, and
- fails in the codebase before the PR.

```javascript
%s
```

If you find this regression test useful, feel free to insert it to your test suite.
Our automated pipeline inserted the test at the end of the `%s` file before running it.

This is part of our research at the [ZEST](https://www.ifi.uzh.ch/en/zest.html) group of University of Zurich in collaboration with [Mozilla](https://www.mozilla.org).
If you have any suggestions, questions, or simply want to learn more, feel free to contact us at konstantinos.kitsios@uzh.ch and mcastelluccio@mozilla.com.

<details>
<summary> Click to see which lines were covered.</summary>

```diff
%s
```

Line coverage\\* achieved: %0.1f%%

\\* Line coverage is calculated over the lines added in this PR.

<details>
""" 


comment_template_amplification = """Hi! 🤖 The test below is automatically generated and increases the coverage of this PR because it:
- passes, and
- covers lines that were not covered by the tests introduced in this PR.

```javascript
%s
```

If you find this coverage-increasing test useful, feel free to insert it to your test suite.
Our automated pipeline inserted the test at the end of the `%s` file before running it.


This is part of our research at the [ZEST](https://www.ifi.uzh.ch/en/zest.html) group of University of Zurich in collaboration with [Mozilla](https://www.mozilla.org).
If you have any suggestions, questions, or simply want to learn more, feel free to contact us at konstantinos.kitsios@uzh.ch and mcastelluccio@mozilla.com.

<details>
<summary> Click to see which aditional lines were covered.</summary>

```diff
%s
```

Line coverage\\* achieved with developer tests: %0.1f%%
Line coverage\\* achieved with developer & the AI-generated test above: %0.1f%%

\\* Line coverage is calculated over the lines added in this PR.

<details>
"""

PROMPT_COMBINATIONS_GEN = {
    "include_golden_code"        : [1, 1, 1, 1, 0],
    "include_pr_desc"            : [0, 1, 0, 0, 0],
    "include_predicted_test_file": [1, 0, 1, 0, 0],
    "sliced"                     : ["LongCorr", "LongCorr", "No", "No", "No"]
}
# Keep the same length, because we don't know a-priori if it's generation or amplification
PROMPT_COMBINATIONS_AMPL = {
    "test_code_sliced"           : [1, 0, 1, 1, 1],     
    "include_golden_code"        : [1, 1, 1, 1, 0],
    "include_pr_desc"            : [0, 1, 1, 0, 0],
    "sliced"                     : ["LongCorr", "LongCorr", "LongCorr", "No", "No"]
}

@csrf_exempt
def github_webhook(request):
    """Handle GitHub webhook events"""
    if request.method != 'POST':
        logger.info("Method is not POST")
        return HttpResponseForbidden("Invalid method")

    if not verify_signature(request):
        logger.info("Invalid signature")
        return HttpResponseForbidden("Invalid signature")
    
    payload = json.loads(request.body)
    # Save the payload to the logs
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    os.makedirs(WEBHOOK_RAW_LOG_DIR, exist_ok=True)
    filename = f"webhook_{timestamp}.json"
    file_path = os.path.join(WEBHOOK_RAW_LOG_DIR, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)
    logger.info(f"Webhook saved to {file_path}")  # Log the save action

    
    event = request.headers.get('X-GitHub-Event')
    if event == "pull_request" :
        try:
            # Only trigger when PR opens (or if it is my repo)
            if payload.get("action") == "opened" or payload["repository"]["owner"]["login"]=="kitsiosk":

                iAttempt     = 0
                stop         = False # we stop when successful

                # gpt-4o
                while iAttempt<len(PROMPT_COMBINATIONS_GEN) and not stop:
                    response, stop = run(payload, iAttempt=iAttempt, model="gpt-4o",
                                         timestamp=timestamp, post_comment=True)
                    iAttempt +=1
            
                # llama3.3
                iAttempt = 0
                while iAttempt<len(PROMPT_COMBINATIONS_GEN) and not stop:
                    response, stop = run(payload, iAttempt=iAttempt, model="meta-llama/Llama-3.3-70B-Instruct",
                                         timestamp=timestamp, post_comment=True)
                    iAttempt +=1

                # o3-mini-high (last resort)
                if not stop:
                    response, stop = run(payload, iAttempt=1, model="o3-mini",
                                            timestamp=timestamp, post_comment=True)
                return response

            else:
                logger.info("PR event, but not opening of a PR, so skipping...")
                return JsonResponse({"status": "success"})
        except Exception as e:
            traceback.print_exc()
            return JsonResponse({"error": str(e)}, status=400)
    else:
        logger.info("Non-PR event")
        return JsonResponse({"status": "success"})


def run(payload, dockerfile=None, 
        model_test_generation=None, 
        model_test_amplification=None, 
        iAttempt=0,
        post_comment=False,
        model="gpt-4o",
        timestamp=0):

    # Extract data from payload
    pr_number      = payload["pull_request"]["number"]
    pr_title       = payload["pull_request"]["title"]
    pr_description = payload["pull_request"]["body"]
    pr_url         = payload["pull_request"]["url"]
    owner          = payload["repository"]["owner"]["login"]
    repo           = payload["repository"]["name"]
    diff           = payload["pull_request"]["diff_url"]
    base_branch    = payload["pull_request"]["base"]["ref"]
    base_commit    = payload["pull_request"]["base"]["sha"]
    head_branch    = payload["pull_request"]["head"]["ref"]
    head_commit    = payload["pull_request"]["head"]["sha"]
    instance_id    = f"{owner}__{repo}-{pr_number}"
    image_tag      = f"image_{instance_id}"
    if pr_description is None:
        pr_description = ""

    os.makedirs(WEBHOOK_LOG_DIR, exist_ok=True)
    this_instance_log_dir = os.path.join(WEBHOOK_LOG_DIR, instance_id+"_%s"%timestamp, "i%s"%iAttempt+"_%s"%model)
    os.makedirs(this_instance_log_dir, exist_ok=True)
    os.makedirs(os.path.join(this_instance_log_dir, "generation"))
    os.makedirs(os.path.join(this_instance_log_dir, "amplification"))

    # Get the file contents from the github API (we could also get them by cloning the repo in the docker)
    files = fetch_pr_files(pr_number, owner, repo)

    code_fname_arr          = []
    code_content_before_arr = []
    code_content_after_arr  = []
    test_fname_arr          = []
    test_content_before_arr = []
    test_content_after_arr  = []
    at_least_one_javascript_code_file = False
    for file_dict in files:
        # Get the version of the file AFTER the PR
        fname = file_dict["filename"]
        after_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{head_commit}/{fname}"
        response_after = requests.get(after_url, headers=HEADERS)
        if response_after.status_code == 200:
            content_after = response_after.text
        else:
            content_after = "" # probably file deleted

        # Get the version of the file BEFORE the PR
        before_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{base_commit}/{fname}"
        response_before = requests.get(before_url, headers=HEADERS)
        if response_before.status_code == 200:
            content_before = response_before.text
        else:
            content_before = "" # probably file deleted

        if is_test_file(fname):
            test_fname_arr.append(fname)
            test_content_before_arr.append(content_before)
            test_content_after_arr.append(content_after)
        else:
            code_fname_arr.append(fname)
            code_content_before_arr.append(content_before)
            code_content_after_arr.append(content_after)
            if fname.endswith(".js") and not at_least_one_javascript_code_file:
                at_least_one_javascript_code_file = True

    if not at_least_one_javascript_code_file: # if the PR changed only non-javascript files return
        logger.info("No .js code files (except maybe for test) were modified, skipping")
        return JsonResponse({"status": "success"}), True
    
    # If test file already exists, we do amplification, otherwise generation
    contains_test_file = len(test_fname_arr) > 0

    # Get golden code patch
    diffs = []
    for (fname, fcontent_before, fcontent_after) in zip(code_fname_arr, code_content_before_arr, code_content_after_arr):
        diff = unified_diff_with_function_context(fcontent_before, fcontent_after, fname)
        diffs.append(diff)
    golden_code_patch = "\n\n".join(diffs)+"\n"

    # Get golden test patch
    diffs = []
    for (fname, fcontent_before, fcontent_after) in zip(test_fname_arr, test_content_before_arr, test_content_after_arr):
        diff = unified_diff(fcontent_before, fcontent_after, fromfile=fname, tofile=fname)
        diffs.append(diff)
    golden_test_patch = "\n".join(diffs)+"\n"

    # We re-calculate the code contents after because we want to capture the offset of the golden patch
    code_content_after_arr_from_patch, stderr = apply_patch(code_content_before_arr, golden_code_patch)
    try:
        offsets = extract_offsets_from_stderr(stderr)
    except AssertionError as e:
        logger.info("Different offsets in a single file for %s, skipping" % instance_id)
        exit(0)

    # Slice golden files
    if code_fname_arr: # sometimes all the changes are counted as tests e.g., test_test_scheduling.py
        code_content_before_sliced_arr = slice_golden_file(
            code_content_before_arr, 
            golden_code_patch,
            "",
            return_file="pre",
            append_line_numbers=True
            )
    else:
        code_content_before_sliced_arr = code_content_before_arr.copy()

    if test_fname_arr: # sometimes there are no tests
        test_content_after_sliced_arr = slice_golden_file(
            test_content_before_arr, 
            golden_test_patch,
            "",
            return_file="post",
            append_line_numbers=True
            )
    else:
        test_content_after_sliced_arr = test_content_before_arr.copy()


    # Check if the PR is linked to a GH Issue
    has_linked_issue, linked_issue, issue_title, issue_description = check_if_has_linked_issue(pr_description, owner, repo)
    issue_description = f"{issue_title}\n{issue_description}" # concatenate title and description
    if has_linked_issue:
        logger.info("Linked issue: %d" % linked_issue)
    else:
        logger.info("No linked issue")


    # Build Docker image of the repo-under-test
    client = docker.from_env()
    if dockerfile is None: # if no mock dockerfile given
        if repo == "bugbug" and owner == "kitsiosk" and pr_number == 5:
            dockerfile = f"dockerfiles/Dockerfile_bugbug_old1" # for integration testing
        else:
            dockerfile = f"dockerfiles/Dockerfile_{repo}"
    build_docker_image(client, dockerfile, base_commit, image_tag=image_tag)

    # Create central datastructure containing all the PR/Issue data
    instance = {}
    instance["instance_id"]          = instance_id
    instance["patch"]                = golden_code_patch
    instance["golden_test_names"]    = test_fname_arr
    instance["golden_test_contents"] = test_content_after_arr
    instance["golden_test_contents_sliced"] = test_content_after_sliced_arr
    instance["problem_statement"]    = issue_description
    instance["hints_text"]           = ""
    instance["golden_code_names"]    = code_fname_arr
    instance["golden_code_contents"] = code_content_before_arr
    instance["golden_code_contents_sliced_long"] = code_content_before_sliced_arr
    instance["title"]                = pr_title
    instance["description"]          = pr_description
    instance["base_commit"]          = base_commit




    if contains_test_file: # Amplification
        amplification_completed = False
        logger.info("=============== Test Amplification Started ===============")

        # Run the developer tests
        tests_to_run = []
        for (fname, content_before, content_after) in zip(test_fname_arr, test_content_before_arr, test_content_after_arr):
            this_file_tests_to_run = extract_test_scope(content_before, content_after, fname)
            tests_to_run += this_file_tests_to_run
        test_result_dev, stdout_dev, coverage_report_dev = run_test_in_container(client, image_tag, golden_test_patch, tests_to_run, golden_code_patch=golden_code_patch)

        if test_result_dev == "FAIL":
            logger.info("Developer tests failed, skipping amplification...")
            return JsonResponse({"status": "success"}), False

        with open(os.path.join(this_instance_log_dir, "amplification",  "dev.txt"), "w") as f:
            f.write(stdout_dev)
        with open(os.path.join(this_instance_log_dir, "amplification", "coverage_report_dev.txt"), "w") as f:
            f.write(coverage_report_dev)

        missed_lines_dev, decorated_patch_dev = get_missed_lines_and_decorate_patch(code_fname_arr, code_content_before_arr, code_content_after_arr_from_patch, golden_code_patch, offsets, coverage_report_dev)
        instance["patch_labeled"] = decorated_patch_dev

        # Build prompt
        include_issue_description   = True
        include_golden_code         = PROMPT_COMBINATIONS_AMPL["include_golden_code"][iAttempt]
        sliced                      = PROMPT_COMBINATIONS_AMPL["sliced"][iAttempt]
        include_issue_comments      = False
        include_pr_desc             = PROMPT_COMBINATIONS_AMPL["include_pr_desc"][iAttempt]
        # These signify amplification instead of generation
        include_golden_test_code = True
        test_code_sliced         = PROMPT_COMBINATIONS_AMPL["test_code_sliced"][iAttempt]
        include_uncovered_lines_by_dvlpr_test = True

        prompt = build_prompt(instance,
                            include_issue_description=include_issue_description,
                            include_golden_code      = include_golden_code, 
                            sliced                   = sliced, 
                            include_issue_comments   = include_issue_comments, 
                            include_pr_desc          = include_pr_desc,
                            include_golden_test_code = include_golden_test_code,
                            test_code_sliced         = test_code_sliced,
                            include_uncovered_lines_by_dvlpr_test=include_uncovered_lines_by_dvlpr_test
                            )

        with open(os.path.join(this_instance_log_dir, "amplification", "prompt.txt"), "w") as f:
            f.write(prompt)

        if len(prompt)>=1048576: # gpt4o limit (can I get it from a config or sth?)
            logger.info("Prompt exceeds limits, skipping...")
            raise ValueError("")
        
        if model_test_amplification is None: # if not mock, query model
            # Query model
            T     = 0.0
            response = query_model(prompt, model=model, T=T)
            with open(os.path.join(this_instance_log_dir, "amplification", "raw_model_response.txt"), "w") as f:
                f.write(response)
            new_test = response.replace('```python', '')
            new_test = new_test.replace('```', '')
            new_test = adjust_function_indentation(new_test)
        else:
            logger.info("Using mocked model response for amplification")
            new_test = model_test_amplification # use mock response for testing

        with open(os.path.join(this_instance_log_dir, "amplification",  "generated_test.txt"), "w") as f:
            f.write(new_test)

        # Inject test
        most_similar_changed_func_or_class, most_similar_file, success = get_best_file_to_inject_golden(test_content_before_arr, test_content_after_arr, test_fname_arr, new_test) 
        if success:
            if not most_similar_changed_func_or_class:
                # it may be the case that a global variable holding parameterization values
                # for a test was changed (see astropy__astropy-12907)
                # In this case, append to the end
                insert_in_class="NOCLASS"
                logger.info("Never goes in here anymore I think")
            elif most_similar_changed_func_or_class[0] == 'function':
                insert_in_class="NOCLASS"
            else:
                insert_in_class=most_similar_changed_func_or_class[1]
        else:
            # Grab the first test file and insert at the end
            most_similar_file = [xx for xx in test_content_before_arr if xx.split('/')[-1].startswith('test') and xx.endswith('.py')][0]
            insert_in_class="NOCLASS"

        most_similar_file_idx = test_fname_arr.index(most_similar_file)
        golden_test_content = test_content_before_arr[most_similar_file_idx]
        golden_test_content_after = test_content_after_arr[most_similar_file_idx]

        # Add the model test on top of the developer test to measure difference
        try:
            new_test_file_contents = append_function(golden_test_content_after, new_test, insert_in_class=insert_in_class)
        except:
            logger.info("Generated code does not compile, skipping")
            return JsonResponse({"status": "success"}), False

        model_test_patch = ""
        tests_to_run = []
        for (test_filename, test_code, test_code_after_patch, ii) in zip(test_fname_arr, test_content_before_arr, test_content_after_arr, range(len(test_fname_arr))):
            if ii == most_similar_file_idx:
                model_test_patch += unified_diff(test_code, 
                                new_test_file_contents, 
                                fromfile=test_filename, 
                                tofile=test_filename, 
                                context_lines=40) + "\n"
                
                this_file_tests_to_run = extract_test_scope(test_code, new_test_file_contents, fname)
            else:
                model_test_patch += unified_diff(test_code, 
                                test_code_after_patch, 
                                fromfile=test_filename, 
                                tofile=test_filename, 
                                context_lines=40) + "\n"
                                # we write many context lines in the file because the edited
                                # function name must appear in order for TDD-Bench to run the test

                this_file_tests_to_run = extract_test_scope(test_code, test_code_after_patch, fname)

            tests_to_run += this_file_tests_to_run

        # Run developer + AI tests
        test_result_dev_and_ai, stdout_dev_and_ai, coverage_report_dev_and_ai = run_test_in_container(client, image_tag, model_test_patch, tests_to_run, golden_code_patch=golden_code_patch)
        # Extract missed lines
        missed_lines_dev_and_ai, decorated_patch_dev_and_ai = get_missed_lines_and_decorate_patch(code_fname_arr, code_content_before_arr, code_content_after_arr_from_patch, golden_code_patch, offsets, coverage_report_dev_and_ai)
        
        with open(os.path.join(this_instance_log_dir, "amplification",  "dev_and_ai.txt"), "w") as f:
            f.write(stdout_dev_and_ai)
        with open(os.path.join(this_instance_log_dir, "amplification", "coverage_report_dev_and_ai.txt"), "w") as f:
            f.write(test_result_dev_and_ai)

        # The lines modified by the developer code patch
        modified_lines = [l[1:].strip() for l in golden_code_patch.splitlines() if l.startswith('+') and not l.startswith('+++')]
        n_modified = len(modified_lines)
        # The lines covered by AI only
        new_lines = set(missed_lines_dev) - set(missed_lines_dev_and_ai)
        coverage_dev = (n_modified-len(set(missed_lines_dev)))/n_modified
        coverage_dev_and_ai = (n_modified-len(set(missed_lines_dev_and_ai)))/n_modified
        logger.info("Coverage dev: %0.2f\nCoverage dev+AI: %0.2f\n" % (coverage_dev, coverage_dev_and_ai))

        if len(new_lines) > 0 and test_result_dev_and_ai == "PASS":
            logger.info("These lines were missed by the developer test by covered by the AI test:\n%s" % "\n".join(new_lines))
        
            patch_for_comment_lines = []
            for (ldev, ldevai) in zip(decorated_patch_dev.splitlines(), decorated_patch_dev_and_ai.splitlines()):
                if ldev!=ldevai:
                    patch_for_comment_lines.append(ldev.replace("###NOT COVERED###", "### ✅ Only covered by above test ✅"))
                else:
                    patch_for_comment_lines.append(ldev)
            patch_for_comment = "\n".join(patch_for_comment_lines)

            # Add a comment to the PR
            comment = comment_template_amplification % (new_test,
                                                        test_filename, 
                                                        patch_for_comment,
                                                        coverage_dev*100,
                                                        coverage_dev_and_ai*100)

            if post_comment:
                status_code, response_data = add_comment_to_pr(owner, repo, pr_number, comment)
            else:
                status_code, response_data = 201, ""
                logger.info("Would add this comment:\n%s\n" % comment)

            if status_code == 201:
                logger.info("Comment added successfully!")
            else:
                logger.info(f"Failed to add comment: {status_code}", response_data)

            amplification_completed = True
        elif test_result_dev_and_ai == "FAIL":
            logger.info("The AI test failed")
            amplification_completed = False
        elif len(new_lines) == 0:
            logger.info("No new lines covered by AI")
            amplification_completed = False

        logger.info("=============== Test Amplification Finished ===============")
        # # We don't return here because we want to run test generation as well
        #return JsonResponse({"status": "success"}), True
    else:
        amplification_completed = True

    logger.info("=============== Test Generation Started ===============")
    generation_completed = False

    # Calculate temporal coupling to find where to inject the test
    tmp_repo_dir = "tmp_repo_dir"
    if not os.path.exists(tmp_repo_dir):
        logger.info(f"[*] Cloning repository https://github.com/{owner}/{repo}.git")
        res = subprocess.run(["git", "clone", f"https://github.com/{owner}/{repo}.git", tmp_repo_dir], capture_output=True, check=True)
        logger.info(f"[+] Cloning successful.")
    try:
        test_filename, test_file_content, test_file_content_sliced = get_contents_of_test_file_to_inject(instance, tmp_repo_dir)
        if test_filename == "":
            logger.info("No suitable file found for %s, skipping" % instance_id)
            exit(0)
        test_filename = test_filename.replace(tmp_repo_dir+'/', '')
        instance['predicted_test_file_content_sliced'] = test_file_content_sliced
    finally:
        is_windows = sys.platform.startswith("win")
        args = ["cmd", "/c", "rmdir", "/s", "/q", tmp_repo_dir] if is_windows else ["rm", "-rf", tmp_repo_dir]
        res = subprocess.run(args, capture_output=True, check=True)


    # Build prompt
    include_issue_description = True
    include_golden_code       = PROMPT_COMBINATIONS_GEN["include_golden_code"][iAttempt]
    sliced                    = PROMPT_COMBINATIONS_GEN["sliced"][iAttempt]
    include_issue_comments    = False
    include_pr_desc           = PROMPT_COMBINATIONS_GEN["include_pr_desc"][iAttempt]
    include_predicted_test_file = PROMPT_COMBINATIONS_GEN["include_predicted_test_file"][iAttempt]
    prompt = build_prompt(instance,
                        include_issue_description=include_issue_description,
                        include_golden_code=include_golden_code, 
                        sliced=sliced, 
                        include_issue_comments=include_issue_comments, 
                        include_pr_desc=include_pr_desc,
                        include_predicted_test_file=include_predicted_test_file
                        )

    if len(prompt)>=1048576: # gpt4o limit
        logger.info("Prompt exceeds limits, skipping...")
        raise ValueError("")
    
    with open(os.path.join(this_instance_log_dir, "generation", "prompt.txt"), "w") as f:
        f.write(prompt)


    if model_test_generation is None: # if not mock, query model
        # Query model
        #model = "o1-2024-12-17"
        T     = 0.0
        response = query_model(prompt, model=model, T=T)

        new_test = response.replace('```javascript', '')
        new_test = new_test.replace('```', '')
        new_test = adjust_function_indentation(new_test)  # TODO: Required for Javascript?

        with open(os.path.join(this_instance_log_dir, "generation", "raw_model_response.txt"), "w") as f:
            f.write(response)
    else:
        new_test = model_test_generation


    with open(os.path.join(this_instance_log_dir, "generation", "generated_test.txt"), "w") as f:
        f.write(new_test)

    # Append generated test to existing test file
    new_test_file_content = append_function(test_file_content, new_test, insert_in_block="NOBLOCK")

    # Construct test patch
    model_test_patch = unified_diff(test_file_content, new_test_file_content, fromfile=test_filename, tofile=test_filename)+"\n"

    test_to_run = extract_test_scope(test_file_content, new_test_file_content, test_filename)


    #### Run test in pre-PR codebase
    test_result_before, stdout_before, coverage_report_before = run_test_in_container(client, image_tag, model_test_patch, test_to_run)
    with open(os.path.join(this_instance_log_dir, "generation", "before.txt"), "w") as f:
        f.write(stdout_before)
    with open(os.path.join(this_instance_log_dir, "generation", "coverage_report_before.txt"), "w") as f:
        f.write(coverage_report_before)
    with open(os.path.join(this_instance_log_dir, "generation", "new_test_file_content.py"), "w") as f:
        f.write("#%s\n%s" % (test_filename, new_test_file_content))

    #### Run test in post-PR codebase
    golden_code_patch = instance["patch"]
    test_result_after, stdout_after, coverage_report_after = run_test_in_container(client, image_tag, model_test_patch, test_to_run, golden_code_patch=golden_code_patch)
    with open(os.path.join(this_instance_log_dir, "generation", "after.txt"), "w") as f:
        f.write(stdout_after)
    with open(os.path.join(this_instance_log_dir, "generation", "coverage_report_after.txt"), "w") as f:
        f.write(coverage_report_after)

    isFail2Pass = (test_result_before == "FAIL") and (test_result_after=="PASS")

    if isFail2Pass:
        missed_lines, decorated_patch = get_missed_lines_and_decorate_patch(code_fname_arr, code_content_before_arr, code_content_after_arr_from_patch, golden_code_patch, offsets, coverage_report_after)
        decorated_patch_new_lines = []
        for ln in decorated_patch.splitlines():
            if "###NOT COVERED###" in ln:
                new_line = ln.replace("###NOT COVERED###", "")
            elif ln.startswith("+") and not ln.startswith("+++"):
                new_line = ln + "# ✅ Covered by above test"
            else:
                new_line = ln
            decorated_patch_new_lines.append(new_line)
        decorated_patch_new = "\n".join(decorated_patch_new_lines)

        # Calculate patch coverage
        modified_lines = [l[1:].strip() for l in golden_code_patch.splitlines() if l.startswith('+') and not l.startswith('+++')]
        n_modified = len(modified_lines)
        patch_coverage = (n_modified - len(missed_lines))/n_modified

        # Add comment to the PR
        comment = comment_template_generation % (new_test, 
                                                 test_filename,
                                                 decorated_patch_new, 
                                                 patch_coverage*100)
        # If the task was amplification, we don't post a comment upon successful
        # generation, we just run it to benchmark our pipeline
        if post_comment and not contains_test_file:
            status_code, response_data = add_comment_to_pr(owner, repo, pr_number, comment)
        else:
            status_code, response_data = 201, ""
            logger.info("Debugging: would add this comment to PR:\n%s\n" % comment)

        if status_code == 201:
            logger.info("Comment added successfully!")
        else:
            logger.info(f"Failed to add comment: {status_code}", response_data)
        
        generation_completed = True
    elif not isFail2Pass:
        logger.info("No Fail-to-Pass test generated")
        generation_completed = False

    logger.info("=============== Test Generation Finished ===============")

    # Whether to stop or try again with different prompt inputs
    stop = (contains_test_file and amplification_completed) or (not contains_test_file and generation_completed)
    return JsonResponse({"status": "success"}), stop


def verify_signature(request):
    """Verify the webhook signature."""
    signature = request.headers.get('X-Hub-Signature-256')
    if not signature:
        return False
    sha_name, signature = signature.split('=')
    if sha_name != 'sha256':
        return False
    # Encode the request body using the same secret
    mac = hmac.new(GITHUB_WEBHOOK_SECRET.encode(), msg=request.body, digestmod=hashlib.sha256)
    # If the two encodings are the same, we are good.
    return hmac.compare_digest(mac.hexdigest(), signature)

def check_if_has_linked_issue(pr_description, owner, repo):
    # Seach for "Closes #2" etc
    issue_pattern  = r'\b(?:Closes|Fixes|Resolves)\s+#(\d+)\b'
    matches        = re.findall(issue_pattern, pr_description)

    # Since PRs and Issues are treated the same by the GH API, we need to check if the
    # referenced entity is PR or GH Issue
    for match in matches:
        match_int = int(match) # match was originally string
        issue_or_pr, title, description = is_issue_or_pr(owner, repo, match_int)
        if issue_or_pr == "Issue":
            logger.info("Linked with issue #%d" % match_int)
            return True, match_int, title, description  # we don't support linking of >1 issues yet

    return False, None, None, None

def is_issue_or_pr(owner, repo, number):
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"
    
    response = requests.get(url, headers=HEADERS)    
    
    if response.status_code == 200:
        issue_data = response.json()
        if "pull_request" in issue_data:
            return "PR", None, None
        else:
            return "Issue", issue_data["title"], issue_data["body"]
    else:
        logger.info(f"Failed to fetch data for #{number}: {response.status_code}")
        return None, None, None


#### Helpers to construct test string (fname::class::method)
import ast
import difflib
from typing import List, Dict

def find_changed_its(old_its: dict, new_its: dict) -> List[str]:
    """Find its that have changed between two versions of a Javascript file."""
    changed_functions = []
    
    for it_name, new_body in new_its.items():
        old_body = old_its.get(it_name)
        if old_body is None:
            # Function is new
            changed_functions.append(it_name)
        elif old_body and old_body != new_body:
            # Function exists but has changed
            diff = list(difflib.unified_diff(old_body.splitlines(), new_body.splitlines()))
            if diff:
                changed_functions.append(it_name)
    
    return changed_functions

def build_expression_map(tree: Tree) -> tuple:
    expression_map = {}
    its = {}

    def visit_body(node: Node, scope_name: str) -> None:
        # Visit the describe body if available
        for child in get_call_expression_content(node):
            visit_node(child, scope_name)

    def visit_node(node: Node, scope_name: str = "global") -> None:
        expression_type = get_call_expression_type(node)
        if expression_type == "it":
            new_scope = get_call_expression_description(node, "<it>")
            expression_map[new_scope] = scope_name
            its[new_scope] = node.text.decode("utf-8")

        elif expression_type == "describe":
            new_scope = get_call_expression_description(node, "<describe>")
            if scope_name != "global":
                new_scope = f"{scope_name} {new_scope}"

            visit_body(node, new_scope)

    for root_child in tree.root_node.children:
        visit_node(root_child)
    return expression_map, its

def extract_test_scope(test_file_content, new_test_file_content, test_filename) -> dict:
    # Extract string of the type fname describe it
    _, contributing_its_old = build_expression_map(test_file_content)
    it2describe, contributing_its_new = build_expression_map(new_test_file_content)

    contributing_its = find_changed_its(contributing_its_old, contributing_its_new)
    it2test_arr      = {}
    if contributing_its:
        for it in contributing_its:
            scope = it2describe.get(it, "")
            if scope == "":
                pass
            elif scope == "global":
                it2test_arr[it] = test_filename
            else: # describe scope
                it2test_arr[f"{scope} {it}"] = test_filename

    return it2test_arr

#### Helpers to run the tests in docker
import docker

# def read_dockerfile(commit_hash, dockerfile_path="Dockerfile"):
#     """Reads the Dockerfile, replaces the commit hash, and returns the modified content."""
#     with open(dockerfile_path, "r") as f:
#         content = f.read()

#     # Replace the commit hash dynamically
#     content = content.replace("RUN git checkout <commit_hash>", f"RUN git checkout {commit_hash}")

#     return content

def build_docker_image(client, dockerfile_path, commit_hash, image_tag="no_name_image"):
    """Builds a Docker image using the Python Docker SDK."""

    # # Read the modified Dockerfile content
    # dockerfile_content = read_dockerfile(commit_hash, dockerfile_path)

    # # Write a temporary Dockerfile (this avoids modifying the original file)
    # temp_dockerfile = "Dockerfile.temp"
    # with open(temp_dockerfile, "w") as f:
    #     f.write(dockerfile_content)

    logger.info(f"[*] Building Docker image based on commit {commit_hash}")
    
    # Build the Docker image
    build_args = {"commit_hash": commit_hash}
    try:
        image, build_logs = client.images.build(path=".", 
                                                tag=image_tag, 
                                                dockerfile=dockerfile_path,
                                                buildargs=build_args,
                                                network_mode="host")

        # # Print build logs
        # for log in build_logs:
        #     if "stream" in log:
        #         print(log["stream"].strip())

        logger.info(f"[+] Docker image '{image_tag}' built successfully.")
    except docker.errors.BuildError as e:
        logger.info(f"[!] Build failed: {e}")
        sys.exit(1)
    except docker.errors.APIError as e:
        logger.info(f"[!] Docker API error: {e}")
        sys.exit(1)


import tempfile
import tarfile
import io

def run_test_in_container(client, image_tag, model_test_patch, tests_to_run, golden_code_patch=None):
    """Creates a container, applies the patch, runs the test, and returns the result."""

    # Create a temporary patch file
    with tempfile.NamedTemporaryFile(delete=False, mode="w") as patch_file:
        patch_file.write(model_test_patch)
        patch_file_path = patch_file.name

    try:
        logger.info("[*] Creating container...")
        container = client.containers.create(
            image=image_tag,
            command="/bin/sh -c 'sleep infinity'",  # Keep the container running
            tty=True,  # Allocate a TTY for interactive use
            detach=True
        )

        container.start()
        logger.info(f"[+] Container {container.short_id} started.")

        #### A) Test patch (Always)
        model_test_patch_fname = "test_patch.diff"
        patch_dest_path = f"/app/testbed/{model_test_patch_fname}"
        # Create a tar archive
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            tar.add(patch_file_path, arcname=model_test_patch_fname)
        tar_stream.seek(0)
        # Copy the tar archive to the container
        container.put_archive("/app/testbed", tar_stream.getvalue())
        logger.info(f"[+] Patch file copied to {patch_dest_path}")

        

        # Apply the patch inside the container
        apply_patch_cmd = f"/bin/sh -c 'cd /app/testbed && git apply {model_test_patch_fname}'"
        exec_result = container.exec_run(apply_patch_cmd)

        if exec_result.exit_code != 0:
            logger.info(f"[!] Failed to apply patch: {exec_result.output.decode()}")
            return "ERROR", exec_result.output.decode()

        logger.info("[+] Test patch applied successfully.")


        if golden_code_patch is not None:

            # Create a temporary patch file
            with tempfile.NamedTemporaryFile(delete=False, mode="w") as patch_file:
                patch_file.write(golden_code_patch)
                patch_file_path = patch_file.name
        
            #### B) Model patch (Only in post-PR code)
            golden_code_patch_fname = "golden_code_patch.diff"
            patch_dest_path = f"/app/testbed/{golden_code_patch_fname}"
            # Create a tar archive
            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode="w") as tar:
                tar.add(patch_file_path, arcname=golden_code_patch_fname)
            tar_stream.seek(0)
            # Copy the tar archive to the container
            container.put_archive("/app/testbed", tar_stream.getvalue())
            logger.info(f"[+] Patch file copied to {patch_dest_path}")

            # Apply the patch inside the container
            apply_patch_cmd = f"/bin/sh -c 'cd /app/testbed && git apply {golden_code_patch_fname}'"
            exec_result = container.exec_run(apply_patch_cmd)
    
            if exec_result.exit_code != 0:
                logger.info(f"[!] Failed to apply patch: {exec_result.output.decode()}")
                return "ERROR", exec_result.exit_code
    
            logger.info("[+] Code patch applied successfully.")

        # Run the test command
        coverage_report_separator = "COVERAGE_REPORT_STARTING_HERE"
        test_commands = [
            f'npx nyc --all --no-source-map --reporter=text --reporter=lcov jasmine --filter="{desc}" {file}'
            for desc, file in tests_to_run.items()
        ]
        test_command = (
            "/bin/sh -c 'cd /app/testbed && "
            f"{' ; '.join(test_commands)} ; "
            "npx nyc report --reporter=text > coverage_report.txt && "
            f"echo '{coverage_report_separator}' && "
            "cat coverage_report.txt'"
        )
        exec_result = container.exec_run(test_command, stdout=True, stderr=True)
        stdout_output_all = exec_result.output.decode()
        try: # TODO: fix, find a better way to handle the "test-not-ran" error
            stdout, coverage_report = stdout_output_all.split(coverage_report_separator)
        except:
            logger.info("Internal error: docker command failed with: %s" % stdout_output_all)
        logger.info("[+] Test command executed.")

        # Extract only the number of failures from the output.
        match = re.search(r'\b(\d+)\s+failures\b', stdout)
        if match:
            num_failures = int(match.group(1))
            test_result = "PASS" if num_failures == 0 else "FAIL"
        else:
            # If the summary line cannot be found, consider it a failure (or handle as needed)
            logger.info("Could not determine test summary from output.")
            test_result = "FAIL"

        logger.info(f"[+] Test result: {test_result}")

        return test_result, stdout, coverage_report

    finally:
        # Cleanup
        os.remove(patch_file_path)
        container.stop()
        container.remove()
        logger.info("[*] Container stopped and removed.")

######### Helper to fetch file contents that changed in the PR
def fetch_pr_files(pr_number, repo_owner, repo_name):
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls/{pr_number}/files"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 403 and "X-RateLimit-Reset" in response.headers:
        reset_time = int(response.headers["X-RateLimit-Reset"])
        wait_time = reset_time - int(time.time()) + 1
        #logger.info(f"Rate limit exceeded. Waiting for {wait_time} seconds...")
        time.sleep(max(wait_time, 1))
        return fetch_pr_files(pr_number)
        
    response.raise_for_status()
    return response.json()



def add_comment_to_pr(owner, repo, pr_number, comment):
    """Add a comment to the PR"""
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {"body": comment}
    response = requests.post(url, json=data, headers=headers)
    return response.status_code, response.json()


### Helpers for test amplification
def get_missed_lines_and_decorate_patch(edited_files, code_content_before_arr, code_content_after_arr, golden_code_patch, offsets, coverage_report):
    # In code_after_labeled, we will label every line that is not covered with a 
    # comment: "# NOT COVERED"
    code_after_labeled_arr    = []
    modified_and_missed_lines = []
    
    for (edited_file, code_after, offset, ii) in zip(edited_files, code_content_after_arr, offsets, range(len(edited_files))):
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

        line_number_of_edited_lines = get_line_number_of_edited_lines(golden_code_patch)
        for (line, line_no, line_file) in line_number_of_edited_lines:
            if line_file == edited_file:
                # + offset because of fuzzy diff | -1 because it's 1-indexed
                line_no_adjusted = line_no+offset-1
                # logger.info(line)
                # logger.info(code_after.splitlines()[line_no_adjusted].strip())
                # logger.info("=========")
                assert line == code_after.splitlines()[line_no_adjusted].strip(), "Line mismatch"
                # Make it 1-indexed again
                if line_no_adjusted+1 in missed_lines or all_lines_in_file_missed:
                    modified_and_missed_lines.append(code_after.splitlines()[line_no_adjusted].strip()) # here it's 0-indexed
                    code_after_labeled[line_no_adjusted] = code_after_labeled[line_no_adjusted] + " ###NOT COVERED###"
    
        
        code_after_labeled_arr.append("\n".join(code_after_labeled)+"\n")
    
        
    golden_patch_labeled = ""
    for (c, c_labeled, fname) in zip(code_content_before_arr, code_after_labeled_arr, edited_files):
        
        golden_patch_labeled += unified_diff(c, 
                                        c_labeled, 
                                        fromfile=fname, 
                                        tofile=fname) + "\n"
        
    # if modified_and_missed_lines is empty, golden_patch_labeled is the same as golden_patch
    return modified_and_missed_lines, golden_patch_labeled


######################### The commented code is for the Github App version of the hook ####
# # GitHub API Base URL
# GITHUB_API_URL = "https://api.github.com"
# # Load GitHub App Credentials from Environment Variables
# GITHUB_APP_ID = 1131987 # os.getenv("GITHUB_APP_ID")
# GITHUB_PRIVATE_KEY_PATH = "/home/ubuntu/pr-tester-bot.2025-02-03.private-key.pem" #os.getenv("GITHUB_PRIVATE_KEY_PATH")

# def generate_github_jwt():
#     """Generate a JWT for authenticating as a GitHub App."""
#     with open(GITHUB_PRIVATE_KEY_PATH, "r") as key_file:
#         private_key = key_file.read()

#     payload = {
#         "iat": int(time.time()),  # Issued at
#         "exp": int(time.time()) + 600,  # Expires in 10 minutes
#         "iss": GITHUB_APP_ID  # GitHub App ID
#     }

#     return jwt.encode(payload, private_key, algorithm="RS256")

# def verify_signature(request):
#     """Verify the webhook signature using HMAC SHA-256."""
#     signature = request.headers.get("X-Hub-Signature-256")
#     if not signature:
#         return False

#     mac = hmac.new(GITHUB_WEBHOOK_SECRET.encode(), request.body, hashlib.sha256)
#     expected_signature = f"sha256={mac.hexdigest()}"

#     return hmac.compare_digest(expected_signature, signature)

# def get_installation_access_token(installation_id):
#     """Get an access token for the GitHub App installation."""
#     jwt_token = generate_github_jwt()
#     url = f"{GITHUB_API_URL}/app/installations/{installation_id}/access_tokens"

#     headers = {
#         "Authorization": f"Bearer {jwt_token}",
#         "Accept": "application/vnd.github.v3+json"
#     }

#     response = requests.post(url, headers=headers)
#     if response.status_code == 201:
#         return response.json()["token"]
#     else:
#         raise Exception(f"Failed to get installation token: {response.text}")


# @csrf_exempt
# def github_webhook(request):
#     """Handle GitHub App webhook events (PRs & Installations)."""
#     logger.info("Entered")
#     if request.method != "POST":
#         return JsonResponse({"message": "Invalid request"}, status=400)

#     if not verify_signature(request):
#         return JsonResponse({"message": "Invalid signature"}, status=403)

#     try:
#         payload = json.loads(request.body)

#         # Save the payload to the logs
#         timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
#         filename = f"webhook_{timestamp}.json"
#         file_path = os.path.join(WEBHOOK_RAW_LOG_DIR, filename)
#         with open(file_path, "w", encoding="utf-8") as f:
#             json.dump(payload, f, indent=4)
#         logger.info(f"Webhook saved to {file_path}")  # Log the save action

#         # Extract installation ID (needed for authentication)
#         installation_id = payload.get("installation", {}).get("id")
#         if not installation_id:
#             return JsonResponse({"message": "No installation ID found"}, status=400)

#         logger.info("Found installation ID")

#         # Handle PR events
#         if "pull_request" in payload:
#             logger.info("In PR event")
#             pr_number      = payload["pull_request"]["number"]
#             repo_full_name = payload["repository"]["full_name"]

            
#             # Save the payload to the logs
#             timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
#             filename = f"{repo_full_name.replace('/', '__')}_{pr_number}_{timestamp}.json"
#             file_path = os.path.join(WEBHOOK_LOG_DIR, filename)
#             with open(file_path, "w", encoding="utf-8") as f:
#                 json.dump(payload, f, indent=4)
#             logger.info(f"Webhook saved to {file_path}")  # Log the save action


#             logger.info(pr_number)
#             # Get a dynamic token for this specific repo installation
#             installation_token = get_installation_access_token(installation_id)

#             # For now, don't post comment yet
#             return JsonResponse({"message": "Webhook received"}, status=200)
        
#             ###################################################################
#             ### TODO: Code to query the model and run the tests goes here######
#             ###################################################################
            
#             # Post a bot comment on the PR
#             post_github_comment(repo_full_name, pr_number, installation_token)

#         # Handle installation events (when someone installs the app)
#         if payload.get("action") == "created" and "installation" in payload:
#             logger.info(f"GitHub App was installed on a new repository")

#     except json.JSONDecodeError:
#         return JsonResponse({"message": "Invalid JSON"}, status=400)

#     return JsonResponse({"message": "Webhook received"}, status=200)


# # def post_github_comment(repo_full_name, pr_number, token):
#     """Posts a comment on a GitHub PR using the App's authentication."""
#     url = f"{GITHUB_API_URL}/repos/{repo_full_name}/issues/{pr_number}/comments"

#     headers = {
#         "Authorization": f"token {token}",
#         "Accept": "application/vnd.github.v3+json",
#         "User-Agent": "MyWebhookBot"
#     }

#     data = {"body": "🤖 Hello! This is an automated bot comment triggered by a GitHub App webhook!"}

#     response = requests.post(url, headers=headers, json=data)

#     if response.status_code == 201:
#         logger.info(f"✅ Comment posted on PR #{pr_number}")
#         return JsonResponse({"message": "Webhook received"}, status=200)

#     else:
#         logger.info(f"❌ Failed to post comment: {response.status_code} - {response.text}")
#         return JsonResponse({"message": "Invalid JSON"}, status=400)
######################### The commented code is for the Github App version of the hook ####

