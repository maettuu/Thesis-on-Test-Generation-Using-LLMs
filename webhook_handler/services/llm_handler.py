from huggingface_hub import InferenceClient
from openai import OpenAI
from groq import Groq

from webhook_handler.core.config import Config
from webhook_handler.data_models.pr_pipeline_data import PullRequestPipelineData


class LLMHandler:
    def __init__(self, config: Config, data: PullRequestPipelineData):
        self.config = config
        self.data = data
        self.openai_client = OpenAI(api_key=config.openai_api_key)
        self.hug_client = InferenceClient(api_key=config.hug_api_key)
        self.groq_client = Groq(api_key=config.groq_api_key)

    def build_prompt(
            self,
            include_issue_description=False,
            include_golden_code=False,
            sliced="No",
            include_issue_comments=False,
            include_pr_desc=False,
            include_golden_test_code=False,
            test_code_sliced=False,
            include_uncovered_lines_by_dvlpr_test=False,
            isCoT_amplification=False,
            include_predicted_test_file=False,
    ):
        golden_patch = self.data.pr_diff_ctx.golden_code_patch
        cot_text = ""
        predicted_test_file_text = ""
        predicted_test_file_contents = ""
        task3 = ". The test function should be self-contained and to-the-point, containing only the necessary assertions to verify that the issue is resolved."

        if include_golden_test_code:
            # If we include the golden_test_code, we are talking about Test Amplification, where we give the
            # developer (golden) test to the model and ask for a test that increases coverage
            test_names_with_code = ""
            test_filenames = self.data.pr_diff_ctx.test_names
            if test_code_sliced:
                test_code = self.data.test_sliced
            else:
                test_code = self.data.pr_diff_ctx.test_after
                print("Warning, using Test Amplification without slicing the test code, performance may be bad")

            for (fname, fcode) in zip(test_filenames, test_code):
                test_names_with_code += "File %s\n%s\n\n" % (fname, fcode)

            if include_uncovered_lines_by_dvlpr_test:
                golden_patch = self.data.patch_labeled
                task = "The developer has also submitted some tests in the PR that fail before the <patch> is applied and pass after the <patch> is applied, hence validating that the <patch> resolves the <issue>. The these fail-to-pass tests are shown in the <developer_tests> brackets (only parts relevant to the PR are shown with their respective line numbers; lines added in the PR start with '+'). However, these tests do not cover all the added code; specifically, the <patch> lines that are not covered end with the comment ###NOT COVERED###. Your task is to **write an additional fail-to-pass test that covers at least some ###NOT COVERED### lines**. If a test function from the <developer_tests> can be modified to cover ###NOT COVERED### lines, feel free to do it, otherwise (e.g., not covered lines are in a different file) you can ignore the <developer_tests>. You must import any needed modules in your test function. "
                task2 = "<developer_tests>\n%s\n</developer_tests>\n\nGenerate another fail-to-pass test that covers lines of the new code (<patch>) that were not covered by the <developer_tests>. " % test_names_with_code
            else:
                task = "The developer has also submitted some tests in the PR that fail before the <patch> is applied and pass after the <patch> is applied, hence validating that the <patch> resolves the <issue>. The these fail-to-pass tests are shown in the <developer_tests> brackets (only parts relevant to the PR are shown with their respective line numbers; lines added in the PR start with '+'). However, these tests do not cover all the added code. Your task is to **write an additional fail-to-pass test that covers at least some of the lines missed by the <developer_tests>. You must import any needed modules in your test function. "
                task2 = "<developer_tests>\n%s\n</developer_tests>\n\nGenerate another fail-to-pass test that covers lines of the new code (<patch>) that were not covered by the <developer_tests>. " % test_names_with_code

            if isCoT_amplification:
                cot_text = "Think step-by-step to generate the test:\n1. Select one or more ###NOT COVERED### line(s) from <code>.\n2. If the line(s) you selected belongs to a file already tested by one of the <developer_tests>, modify the developer test to cover the ###NOT COVERED### line(s) \n3. If, on the other hand, the line(s) you selected 1. are not covered by any developer test, write a new test function to cover them.\n"
                task3 = ", without any explanation or any natural language in general."
        else:
            task = "Your task is to write one javascript test 'it' that fails before the changes in the <patch> and passes after the changes in the <patch>, hence verifying that the <patch> resolves the <issue>. "
            task2 = "Generate one test that checks whether the <patch> resolves the <issue>.\n"
            if include_predicted_test_file:
                predicted_test_file_text = "Your generated test will then be manually inserted by us in the test file shown in the <test_file> brackets; you can use the contents in these brackets for motivation if needed. "
                predicted_test_file_contents = "<test_file>\n%s\n</test_file>\n\n" % self.data.predicted_test_sliced

                task3 = ", or at most you can include a decorator to parameterize the test inputs, if one is used by the a test in <test_file> from which you drew motivation (if any). The test should be self-contained (e.g., no parameters unless a decorator is used to parameterize inputs) and to-the-point."

        if include_issue_description:
            issue_text = self.data.problem_statement
        else:
            issue_text = self.data.problem_statement.split('\n')[0]

        if include_golden_code:
            # Add golden code contents
            # - whole file
            # - random part of file
            # - targeted part of file (through AST)
            # filenames of the files changed by the golden patch
            code_filenames = self.data.pr_diff_ctx.code_names
            if sliced == "Short":
                # code = row['golden_code_contents_sliced']
                sliced_text = " (only parts relevant to the patch are shown with their respective line numbers)"
            elif sliced == "Long" or sliced == "LongCorr":
                code = self.data.code_sliced
                sliced_text = " (only parts relevant to the patch are shown with their respective line numbers)"
            elif sliced == "No":
                code = self.data.pr_diff_ctx.code_before  # whole code
                code = [self.add_line_numbers(x) for x in code]
                sliced_text = ""
            else:
                raise ValueError("Unrecongnized value for 'sliced': %s" % sliced)

            code_string = "This patch will be applied to the file(s) shown within the <code> brackets%s. " % sliced_text

            fnames_with_code = ""
            for (fname, fcode) in zip(code_filenames, code):
                fnames_with_code += "File %s\n%s\n\n" % (fname, fcode)
            code_string2 = "<code>\n%s\n</code>\n\n" % fnames_with_code
        else:
            code_string = ""
            code_string2 = ""

        if include_issue_comments:
            comments_string = "\nIssue comments (discussion):\n %s" % self.data.hints_text
        else:
            comments_string = ""

        if include_pr_desc:
            pr_desc_string = ". The description of this Pull Request is shown in the <pr_description> brackets"
            pr_desc_string2 = "<pr_description>\nPR Title: %s\n%s\n</pr_description>\n\n" % (self.data.pr_data.title, self.data.pr_data.description)
        else:
            pr_desc_string = ""
            pr_desc_string2 = ""

        _, repo_name, _ = self.parse_instanceID_string()
        prompt = f"""The following text contains a user issue (in <issue> brackets) posted at the {repo_name} repository. A developer has submitted a Pull Request (PR) that resolves this issue{pr_desc_string}. Their modification is provided in the form of a unified diff format inside the <patch> brackets. {code_string}{task}{predicted_test_file_text}You must only return a raw test and you must import anything you need inside that test which isn't already imported. More details at the end of this text.
    
        <issue>
        {issue_text}{comments_string}
        </issue>
        
        <patch>
        {golden_patch}
        </patch>
        
        {code_string2}{predicted_test_file_contents}{pr_desc_string2}{task2}{cot_text}Return only one test WITHOUT considering the integration to the test file, because your raw test will then be inserted in a file by us, either as a standalone test or as a method of an existing describe block, depending on the file conventions; Return only one test and nothing else{task3}. Import anything you need inside that test which isn't already imported."""

        #     if include_predicted_test_file:
        #         x1 = "in the <test_file>"
        #     else:
        #         x1 = "in a file"

        #     prompt = f"""You are an experienced software tester working at the {repo_name} repository, where your main responsibility is writing regression tests.
        # The <issue> brackets contain an issue posted by a user in your repository.
        # The <pr> brackets contain the changes introduced in a recent Pull Request (PR) that resolves the <issue>.
        # Your task as an experienced software tester is to write a REGRESSION TEST for this <issue>.
        # A regression test is a test that:
        # A) FAILS on the current version of the code (shown in the <code> brackets).
        # B) PASSES after the <pr> is applied to the <code>.

        # <issue>
        # {issue_text}
        # </issue>

        # <pr>
        # {golden_patch}
        # </pr>

        # {code_string2}

        # {predicted_test_file_contents}

        # Think step-by-step to generate a REGRESSION test, i.e., a test function that:
        # A) FAILS when we run it in the current version of the <code>.
        # B) PASSES when we run it after applying the <pr> to the <code>.
        # Note that the changes will be applied by us externally, you only have to provide one raw test function that satisfies A) and B).

        # Return only one test function at the default indentation level WITHOUT considering the integration to
        # the test file, e.g., in a unittest.TestCase class because your raw test function will then be inserted
        # in a file by us, either as a standalone function or as a method of an existing unittest.TestCase
        # class, depending on the file conventions; you must provide only one raw test function and must import
        # any needed module inside your test function. The test function should be self-contained and to-the-point, containing only the necessary assertions to verify that the test is a regression test.
        # """

        return prompt

    @staticmethod
    def add_line_numbers(code):
        """Input (String):
                x = 1
                print(x)
            Output (String):
                1 x = 1
                2 print(x)
        """
        code_lines = code.splitlines()
        code_with_line_nums = []
        for (i,line) in enumerate(code_lines):
            code_with_line_nums.append(f"{i+1} {line}")
        return "\n".join(code_with_line_nums)

    def parse_instanceID_string(self):
        # instanceIDs are of the form "<owner>__<repo>-<pr_number>"
        owner = self.data.pr_data.id.split('__')[0]
        tmp = self.data.pr_data.id.split('__')[1].split('-')
        if len(tmp) == 2: # "django-1111"
            repo, pr_number = tmp
        else: # "scikit-learn-1111"
            repo = '-'.join(tmp[0:-1])
            pr_number = tmp[-1]
        return owner, repo, pr_number

    def query_model(self, prompt, model="gpt-4o", T=0.0):
        # model: "gpt-4o" | "meta-llama/Llama-3.3-70B-Instruct" | "microsoft/Phi-3.5-mini-instruct"
        if model.startswith("gpt"):
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=T
            )
            return response.choices[0].message.content.strip()
        elif model.startswith("o3"):  # does not accept temperature
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content.strip()
        elif model.startswith("o1"):  # temperature does not apply in o1 series
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content.strip()
        elif model.startswith("meta") or model.startswith('microsoft'):
            response = self.hug_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=T
            )
            return response.choices[0].message['content']
        elif model.startswith("llama"):
            completion = self.groq_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=700,
                temperature=T
            )
            return completion.choices[0].message.content
        elif model.startswith("qwen"):
            response = self.groq_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system",
                     "content": "You are an experienced software tester specializing in developing regression tests. Follow the user's instructions for generating a regression test. The output format is STRICT: do all your reasoning in the beginning, but the end of your output should ONLY contain javascript code, i.e., NO natural language after the code."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content