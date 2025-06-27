import logging
import difflib

from tree_sitter import Parser, Tree, Node, Language


logger = logging.getLogger(__name__)


class CSTBuilder:
    """
    Used to build, traverse and manipulate concrete syntax trees.
    """
    def __init__(self, parse_language: Language):
        self._parse_language = parse_language

    def extract_changed_tests(self, pr_file_diff) -> list:
        """
        Analyzes the file for both pre- and post-PR, determines the changed tests and extracts their descriptions

        Parameters:
            pr_file_diff (PullRequestFileDiff): The file diff including the file name and content of pre- and post-PR

        Returns:
            list: All descriptions of changed tests
        """

        tests_old = self._build_test_map(
            Parser(self._parse_language).parse(bytes(pr_file_diff.before, 'utf-8'))
        )
        tests_new = self._build_test_map(
            Parser(self._parse_language).parse(bytes(pr_file_diff.after, 'utf-8'))
        )

        contributing_tests = self._find_changed_tests(tests_old, tests_new)

        return [
            desc if tests_new[desc]['scope'] == "global"
            else f"{tests_new[desc]['scope']} {desc}"
            for desc in contributing_tests
        ]

    def append_function(self, file_content: str, new_function: str) -> str:
        """
        Inserts new_function at the bottom of the file_content.

        Parameters:
            file_content (str): The file content where the function will be inserted
            new_function (str): The new function to be inserted

        Returns:
            str: The new file content with the inserted function
        """

        tree = Parser(self._parse_language).parse(bytes(file_content, 'utf-8'))

        top_level_items = []

        for root_child in tree.root_node.children:
            if root_child.type == "expression_statement":
                top_level_items.append(root_child)

        if not top_level_items:
            raise ValueError("No top-level blocks found in the file content!")

        # find the last top-level item
        last_item = top_level_items[-1]

        if self._get_call_expression_type(last_item) == "describe":  # last block was 'describe'
            last_method = None
            for child in self._get_call_expression_content(last_item):
                if child.type == "expression_statement":
                    last_method = child

            if not last_method:
                raise ValueError(
                    f"No nested blocks found in the describe block '{self._get_call_expression_description(last_item)}'!"
                )

            # determine indentation
            last_func_line = last_method.start_point[0]  # line before the last block
            last_code_line = last_method.end_point[0] + 1  # last code line of the above block

        else:  # last function was a function in the top-level, not inside a class
            last_func_line = last_item.start_point[0]  # line before the last block
            last_code_line = last_item.end_point[0] + 1  # last code line of the above block

        # extract indentation
        lines = file_content.splitlines()
        last_func_line_content = lines[last_func_line]
        indentation = len(last_func_line_content) - len(last_func_line_content.lstrip())

        # add the new function
        indented_new_function = "\n".join(
            " " * indentation + line if line.strip() else "" for line in new_function.splitlines()
        )

        updated_lines = lines[:last_code_line] + ["\n" + indented_new_function] + lines[last_code_line:]
        return "\n".join(updated_lines)

    def _build_test_map(self, tree: Tree) -> dict:
        """
        Builds a scope map for each call expression (test). A scope is structured using the expression descriptions.
        Each test is saved together with its scope and content.


        Parameters:
            tree (Tree): The concrete syntax tree to build a scope map from

        Returns:
            dict: A mapping of call expressions to their scopes and content
        """

        expression_map = {}

        def _visit_body(node: Node, scope_name: str) -> None:
            for child in self._get_call_expression_content(node):
                _visit_node(child, scope_name)

        def _visit_node(node: Node, scope_name: str = "global") -> None:
            expression_type = self._get_call_expression_type(node)
            if expression_type == "it":
                desc = self._get_call_expression_description(node, "<it>")
                expression_map[desc] = {
                    "scope": scope_name,
                    "content": node.text.decode("utf-8")
                }

            elif expression_type == "describe":
                desc = self._get_call_expression_description(node, "<describe>")
                if scope_name != "global":
                    desc = f"{scope_name} {desc}"

                _visit_body(node, desc)

        for root_child in tree.root_node.children:
            _visit_node(root_child)

        return expression_map

    @staticmethod
    def _find_changed_tests(tests_old: dict, tests_new: dict) -> list[str]:
        """
        Finds tests that have changed between two versions of a Javascript file.

        Parameters:
            tests_old (dict): The tests in the pre-PR version of the file
            tests_new (dict): The tests in the post-PR version of the file

        Returns:
            list: All changed tests (either new of modified)
        """

        changed_tests = []

        for desc, body_new in tests_new.items():
            body_old = tests_old.get(desc)
            if body_old is None:  # function is new
                changed_tests.append(desc)
                continue

            content_new = body_new["content"]
            content_old = body_old["content"]
            if content_old != content_new:  # function exists but has changed
                diff = list(difflib.unified_diff(content_old.splitlines(), content_new.splitlines()))
                if diff:
                    changed_tests.append(desc)

        return changed_tests

    def _get_call_expression_content(self, node: Node) -> list:
        """
        Returns the child nodes of a call expression.

        Parameters:
            node (Node): The node to extract its children from

        Returns:
            list: The child nodes of a call expression
        """

        call_expression = self._get_call_expression(node)
        if not call_expression:
            return []
        args = call_expression.child_by_field_name("arguments")
        content = next((
            child for child in args.named_children
            if child.type in {"function_expression", "arrow_function"}
        ), None)
        body = content.child_by_field_name("body")
        return body.named_children if body else []

    @staticmethod
    def _get_call_expression(node: Node) -> Node:
        """
        Returns the call expression of an expression statement.

        Parameters:
            node (Node): The node to extract the call expression from

        Returns:
            Node: The call expression
        """
        call_expression = next((
            child for child in node.named_children
            if child.type == "call_expression"
        ), None)
        return call_expression

    def _get_call_expression_type(self, node: Node, fallback: str = "") -> str:
        """
        Returns the type of call expression (i.e., 'describe', 'it')

        Parameters:
            node (Node): The node to determine the type of
            fallback (str, optional): The fallback type to return

        Returns:
            str: The type of call expression
        """

        call_expression = self._get_call_expression(node)
        if not call_expression:
            return fallback
        callee = call_expression.child_by_field_name("function")
        return callee.text.decode("utf-8") if callee.type == "identifier" else fallback

    def _get_call_expression_description(self, node: Node, fallback: str = "") -> str:
        """
        Returns the description (i.e., name) of a call expression.

        Parameters:
            node (Node): The node to determine the description of
            fallback (str, optional): The fallback type to return

        Returns:
            str: The description of the call expression
        """

        call_expression = self._get_call_expression(node)
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
