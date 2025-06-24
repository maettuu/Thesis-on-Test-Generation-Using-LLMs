from huggingface_hub import InferenceClient
from openai import OpenAI
from groq import Groq

from scrape_handler.core.config import Config
from scrape_handler.data_models.pr_pipeline_data import PullRequestPipelineData


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
            patch_labeled="",
            test_file_name="",
            test_file_content="",
            available_packages="",
            available_relative_imports=""
    ):
        guidelines = ("Before you begin:\n"
                      "- Keep going until the job is completely solved — don’t stop halfway.\n"
                      "- If you’re unsure about the behavior, reread the provided patch carefully; do not hallucinate.\n"
                      "- Plan your approach before writing code by reflecting on whether the test truly fails before and passes after.\n\n")

        issue_text = (
            self.data.problem_statement
            if include_issue_description
            else self.data.problem_statement.split("\n")[0]
        )
        linked_issue = f"Issue:\n<issue>\n{issue_text}\n</issue>\n\n"
        patch = f"Patch:\n<patch>\n{self.data.pr_diff_ctx.golden_code_patch}\n</patch>\n\n"
        available_imports = f"Imports:\n<imports>\n{available_packages}\n\n{available_relative_imports}\n</imports>\n\n"

        golden_code = ""
        if include_golden_code:
            code_filenames = self.data.pr_diff_ctx.code_names
            if sliced == "LongCorr":
                code = self.data.code_sliced
                golden_code += "Code:\n<code>\n"
                for (f_name, f_code) in zip(code_filenames, code):
                    golden_code += ("File:\n"
                                    f"{f_name}\n"
                                    f"{f_code}\n")
                golden_code += "</code>\n\n"
            elif sliced == "No":
                code = self.data.pr_diff_ctx.code_before  # whole code
                code = [self.add_line_numbers(x) for x in code]
                golden_code += "Code:\n<code>\n"
                for (f_name, f_code) in zip(code_filenames, code):
                    golden_code += ("File:\n"
                                    f"{f_name}\n"
                                    f"{f_code}\n")
                golden_code += "</code>\n\n"

        instructions = ("Your task:\n"
                        f"You are a software tester at {self.data.pr_data.repo}.\n"
                        "1. Write exactly one javascript test `it(\"...\", () => {...})` block.\n"
                        "2. Your test must fail on the code before the patch, and pass after, hence "
                        "the test will verify that the patch resolves the issue.\n"
                        "3. The test must be self-contained and to-the-point.\n"
                        "4. Use only the provided imports (respect the paths exactly how they are given) by importing"
                        "dynamically for compatibility with Node.js — no new dependencies.\n"
                        "5. Return only the javascript code (no comments or explanations).\n\n")

        example = ("Example structure:\n"
                   "it(\"should <describe behavior>\", () => {\n"
                   "  const { example } = await import(\"../../src/core/example.js\");\n"
                   "  <initialize required variables>;\n"
                   "  <define expected variable>;\n"
                   "  <generate actual variables>;\n"
                   "  <compare expected with actual>;\n"
                   "});\n\n")

        test_code = ""
        if include_predicted_test_file:
            if test_file_content:
                test_code += f"Test file:\n<test_file>\nFile:\n{test_file_name}\n{test_file_content}\n</test_file>\n\n"
                instructions = ("Your task:\n"
                                f"You are a software tester at {self.data.pr_data.repo}.\n"
                                "1. Examine the existing test file. You may reuse any imports, helpers or setup blocks it already has.\n"
                                "2. Write exactly one javascript test `it(\"...\", () => {...})` block.\n"
                                "3. Your test must fail on the pre-patch code and pass on the post-patch code, hence "
                                "the test will verify that the patch resolves the issue.\n"
                                "4. The test must be self-contained and to-the-point.\n"
                                "5. If you need something new use only the provided imports (respect the paths "
                                "exactly how they are given) by importing dynamically for compatibility with Node.js"
                                " — no new dependencies.\n"
                                "6. Return only the javascript code for the new `it(...)` block (no comments or explanations).\n\n")
            else:
                instructions = ("Your task:\n"
                                f"You are a software tester at {self.data.pr_data.repo}.\n"
                                "1. Create a new test file that includes:\n"
                                "   - All necessary imports (use only the provided imports andrespect the "
                                "paths exactly how they are given) — no new dependencies.).\n"
                                "   - A top-level `describe(\"<brief suite name>\", () => {{ ... }})`.\n"
                                "   - Exactly one `it(\"...\", () => {{ ... }})` inside that block.\n"
                                "2. The `it` test must fail on the pre-patch code and pass on the post-patch code, hence "
                                "the test will verify that the patch resolves the issue.\n"
                                "3. Keep the file self-contained — no external dependencies beyond those you import here.\n"
                                "4. Return only the full JavaScript file contents (no comments explanations).\n\n")

                example = ("Example structure:\n"
                           "import { example } from \"../../src/core/example.js\";\n\n"
                           "describe(\"<describe purpose>\", () => {\n"
                           "  it(\"<describe behavior>\", () => {\n"
                           "    <initialize required variables>;\n"
                           "    <define expected variable>;\n"
                           "    <generate actual variables>;\n"
                           "    <compare expected with actual>;\n"
                           "  });\n"
                           "});\n\n")

        pr_description = ""
        if include_pr_desc:
            pr_description += f"PR description:\n<pr_description>\n{
                self.data.pr_data.title
            }\n{
                self.data.pr_data.description
            }\n</pr_description>\n\n"

        prompt = (f"{guidelines}"
                  f"{linked_issue}"
                  f"{patch}"
                  f"{available_imports}"
                  f"{golden_code}"
                  f"{test_code}"
                  f"{pr_description}"
                  f"{instructions}"
                  f"{example}")

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
        try:
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
            # elif model.startswith("meta") or model.startswith('microsoft'):
            #     response = self.hug_client.chat.completions.create(
            #         model=model,
            #         messages=[{"role": "user", "content": prompt}],
            #         max_tokens=500,
            #         temperature=T
            #     )
            #     return response.choices[0].message['content']
            elif model.startswith("llama"):
                completion = self.groq_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=700,
                    temperature=T
                )
                return completion.choices[0].message.content
            elif model.startswith("qwen") or model.startswith("deepseek"):
                response = self.groq_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system",
                         "content": "You are an experienced software tester specializing in developing regression tests. Follow the user's instructions for generating a regression test. The output format is STRICT: do all your reasoning in the beginning, but the end of your output should ONLY contain javascript code, i.e., NO natural language after the code."},
                        {"role": "user", "content": prompt}
                    ]
                )
                return response.choices[0].message.content
        except Exception as e:
            return ""
