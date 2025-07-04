import re

from huggingface_hub import InferenceClient
from openai import OpenAI
from groq import Groq

from scrape_handler.core.config import Config
from scrape_handler.data_models.llm_enum import LLM
from scrape_handler.data_models.pr_pipeline_data import PullRequestPipelineData


class LLMHandler:
    """
    Used to interact with LLMs.
    """
    def __init__(self, config: Config, data: PullRequestPipelineData):
        self._pr_pipeline_data = data
        self._pr_data = data.pr_data
        self._pr_diff_ctx = data.pr_diff_ctx
        self._openai_client = OpenAI(api_key=config.openai_api_key)
        self._hug_client = InferenceClient(api_key=config.hug_api_key)
        self._groq_client = Groq(api_key=config.groq_api_key)

    def build_prompt(
            self,
            include_golden_code: bool,
            sliced: bool,
            include_pr_desc: bool,
            include_predicted_test_file: bool,
            test_filename: str,
            test_file_content_sliced: str,
            available_packages: str,
            available_relative_imports: str
    ) -> str:
        """
        Builds prompt with available data.

        Parameters:
            include_golden_code (bool): Whether to include golden code
            sliced (bool): Whether to slice source code or not
            include_pr_desc (bool): Whether to include pull request description
            include_predicted_test_file (bool): Whether to include test file
            test_filename (str): The filename of the test file
            test_file_content_sliced (str): The content of the test file
            available_packages (str): The available packages
            available_relative_imports (str): The relative imports of all unit test files

        Returns:
            str: Prompt
        """

        guidelines = ("Before you begin:\n"
                      "- Keep going until the job is completely solved — don’t stop halfway.\n"
                      "- If you’re unsure about the behavior, reread the provided patch carefully; do not hallucinate.\n"
                      "- Plan your approach before writing code by reflecting on whether the test truly fails before and passes after.\n\n")

        linked_issue = f"Issue:\n<issue>\n{self._pr_pipeline_data.problem_statement}\n</issue>\n\n"
        patch = f"Patch:\n<patch>\n{self._pr_diff_ctx.golden_code_patch}\n</patch>\n\n"
        available_imports = f"Imports:\n<imports>\n{available_packages}\n\n\n{available_relative_imports}\n</imports>\n\n"

        golden_code = ""
        if include_golden_code:
            code_filenames = self._pr_diff_ctx.code_names
            if sliced:
                code = self._pr_pipeline_data.code_sliced
                golden_code += "Code:\n<code>\n"
                for (f_name, f_code) in zip(code_filenames, code):
                    golden_code += ("File:\n"
                                    f"{f_name}\n"
                                    f"{f_code}\n")
                golden_code += "</code>\n\n"
            else:
                code = self._pr_diff_ctx.code_before  # whole code
                code = [self._add_line_numbers(x) for x in code]
                golden_code += "Code:\n<code>\n"
                for (f_name, f_code) in zip(code_filenames, code):
                    golden_code += ("File:\n"
                                    f"{f_name}\n"
                                    f"{f_code}\n")
                golden_code += "</code>\n\n"

        instructions = ("Your task:\n"
                        f"You are a software tester at {self._pr_data.repo}.\n"
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
            if test_file_content_sliced:
                test_code += f"Test file:\n<test_file>\nFile:\n{test_filename}\n{test_file_content_sliced}\n</test_file>\n\n"
                instructions = ("Your task:\n"
                                f"You are a software tester at {self._pr_data.repo}.\n"
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
                                f"You are a software tester at {self._pr_data.repo}.\n"
                                "1. Create a new test file that includes:\n"
                                "   - All necessary imports (use only the provided imports and respect the "
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
                self._pr_data.title
            }\n{
                self._pr_data.description
            }\n</pr_description>\n\n"

        return (f"{guidelines}"
                  f"{linked_issue}"
                  f"{patch}"
                  f"{available_imports}"
                  f"{golden_code}"
                  f"{test_code}"
                  f"{pr_description}"
                  f"{instructions}"
                  f"{example}")

    def query_model(self, prompt: str, model: LLM, temperature: float = 0.0) -> str:
        """
        Query a model and return its results.

        Parameters:
            prompt (str): Prompt to ask for
            model (LLM): Model to use
            temperature (float, optional): Temperature to use. Defaults to 0.0

        Returns:
            str: Response from model
        """

        try:
            if model == LLM.GPT4o:
                response = self._openai_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature
                )
                return response.choices[0].message.content.strip()
            # elif model == LLM.GPTo4_MINI:  # does not accept temperature
            #     response = self._openai_client.chat.completions.create(
            #         model=model,
            #         messages=[{"role": "user", "content": prompt}],
            #     )
            #     return response.choices[0].message.content.strip()
            elif model == LLM.LLAMA:
                completion = self._groq_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=700,
                    temperature=temperature
                )
                return completion.choices[0].message.content
            elif model == LLM.DEEPSEEK:
                response = self._groq_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system",
                         "content": "You are an experienced software tester specializing in developing regression tests. Follow the user's instructions for generating a regression test. The output format is STRICT: do all your reasoning in the beginning, but the end of your output should ONLY contain javascript code, i.e., NO natural language after the code."},
                        {"role": "user", "content": prompt}
                    ]
                )
                return response.choices[0].message.content
        except:
            return ""

    def postprocess_response(self, raw: str) -> str:
        """
        Cleans LLM response by removing any non-code elements

        Parameters:
            raw (str): The raw LLM response

        Returns:
            str: The cleaned LLM response
        """

        cleaned_test = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL)
        cleaned_test = cleaned_test.replace('```javascript', '')
        cleaned_test = cleaned_test.replace('```', '')
        cleaned_test = cleaned_test.lstrip('\n')
        cleaned_test = self._clean_descriptions(cleaned_test)
        return self._adjust_function_indentation(cleaned_test)

    @staticmethod
    def _add_line_numbers(code: str) -> str:
        """
        Adds line numbers to code.

        Parameters:
            code (str): Code to add line numbers to

        Returns:
            str: code with added line numbers
        """

        code_lines = code.splitlines()
        code_with_line_nums = []
        for (i,line) in enumerate(code_lines):
            code_with_line_nums.append(f"{i+1} {line}")
        return "\n".join(code_with_line_nums)

    @staticmethod
    def _clean_descriptions(function_code: str) -> str:
        """
        Cleans the call expression descriptions used in the generated test by removing every non-letter character.

        Parameters:
            function_code (str): Function code to clean

        Returns:
            str: Cleaned function code
        """

        pattern = re.compile(
            r'\b(?P<ttype>describe|it)\(\s*'  # match describe( or it(
            r'(?P<quote>[\'"])\s*'  # capture opening quote
            r'(?P<name>.*?)'  # capture the raw name
            r'(?P=quote)\s*,',  # match the same closing quote, then comma
        flags = re.DOTALL
        )

        def clean_test_name(match):
            test_type = match.group('ttype')
            q = match.group('quote')
            name = match.group('name')
            # strip out anything but A–Z or a–z
            cleaned = re.sub(r'[^A-Za-z ]', '', name)
            return f"{test_type}({q}{cleaned}{q},"

        return pattern.sub(clean_test_name, function_code)

    @staticmethod
    def _adjust_function_indentation(function_code: str) -> str:
        """
        Adjusts the indentation of a Javascript function so that the function definition
        has no leading spaces, and the internal code indentation is adjusted accordingly.

        Parameters:
            function_code (str): The Javascript function

        Returns:
            str: The adjusted function code
        """

        lines = function_code.splitlines()

        if not lines:
            return ""

        # find the leading spaces of the first non-empty line
        first_non_empty_line = next(line for line in lines if line.strip())
        leading_spaces = len(first_non_empty_line) - len(first_non_empty_line.lstrip())

        return "\n".join([
            line[leading_spaces:] if line.strip()
            else ""
            for line in lines
        ])
