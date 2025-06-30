import logging
import difflib
import re

from tree_sitter import Parser, Tree, Node, Language

from scrape_handler.core import git_diff
from scrape_handler.services.pr_diff_context import PullRequestDiffContext


logger = logging.getLogger(__name__)


class CSTBuilder:
    """
    Used to build, traverse and manipulate concrete syntax trees.
    """
    def __init__(self, parse_language: Language, pr_diff_ctx: PullRequestDiffContext):
        self._parser = Parser(parse_language)
        self.pr_diff_ctx = pr_diff_ctx

    def _parse(self, source: str) -> Tree | None:
        try:
            return self._parser.parse(bytes(source, 'utf-8'))
        except SyntaxError:
            return None

    def slice_code_file(self) -> list:
        """
        Detects which files have been modified to call slice_javascript_code.

        Returns:
            list: Sliced code for modified code, unsliced for untouched code.
        """

        if not self.pr_diff_ctx.code_names:
            return self.pr_diff_ctx.code_before

        code_after, stderr = git_diff.apply_patch(
            self.pr_diff_ctx.code_before,
            self.pr_diff_ctx.golden_code_patch
        )

        patches = ["diff --git" + x for x in self.pr_diff_ctx.golden_code_patch.split("diff --git")[1:]]
        result = []

        for before, after, diff in zip(self.pr_diff_ctx.code_before, code_after, patches):
            before_map, after_map = self._build_changed_lines_scope_map(
                before,
                after,
                diff
            )
            if not before_map and not after_map:
                result.append(before)
                continue

            funcs_before = [list(x.values())[0] for x in before_map]
            funcs_after = [list(x.values())[0] for x in after_map]

            map_cls = (self._build_function_class_maps(funcs_before) +
                       self._build_function_class_maps(funcs_after))

            class2methods = {}
            for m2c in map_cls:
                for (k, v) in m2c.items():
                    class2methods[v] = class2methods.get(v, []) + [k]

            global_funcs = class2methods.pop('global', [])

            sliced = self._slice_javascript_code(
                before,
                global_funcs,
                class2methods
            )
            result.append(sliced)
        return result

    def extract_changed_tests(self, pr_file_diff) -> list:
        """
        Analyzes the file for both pre- and post-PR, determines the changed tests and extracts their descriptions

        Parameters:
            pr_file_diff (PullRequestFileDiff): The file diff including the file name and content of pre- and post-PR

        Returns:
            list: All descriptions of changed tests
        """

        tests_old = self._build_test_scope_map(self._parse(pr_file_diff.before))
        tests_new = self._build_test_scope_map(self._parse(pr_file_diff.after))

        if tests_old and tests_new:
            contributing_tests = self._find_changed_tests(tests_old, tests_new)

            return [
                desc if tests_new[desc]['scope'] == "global"
                else f"{tests_new[desc]['scope']} {desc}"
                for desc in contributing_tests
            ]

        return []

    def append_function(self, file_content: str, new_function: str) -> str:
        """
        Inserts new_function at the bottom of the file_content.

        Parameters:
            file_content (str): The file content where the function will be inserted
            new_function (str): The new function to be inserted

        Returns:
            str: The new file content with the inserted function
        """

        tree = self._parse(file_content)

        if tree is not None:
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

        return ""

    def _build_changed_lines_scope_map(self, before: str, after: str, diff: str) -> [list, list]:
        """
        Extracts added and removed lines from diff and retrieves the scope for each of those lines.

        Parameters:
            before (str): The code before the patch
            after (str): The code after the patch
            diff (str): The diff between the before and after

        Returns:
            list: Mapping of each line before to its scope
            list: Mapping of each line after to its scope
        """

        def _build_line_scope_map(tree: Tree) -> dict:
            line_scope_map = {}

            def _add_scope(node: Node, scope_name: str) -> None:
                if any([
                    node.start_point is None,
                    node.end_point is None,
                    node.start_point[0] is None,
                    node.end_point[0] is None
                ]):
                    return

                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1
                for ln in range(start_line, end_line + 1):
                    line_scope_map[ln] = scope_name

            def _handle_decorators(node: Node, scope_name: str) -> None:
                prev = node.prev_sibling
                if prev:
                    txt = prev.text.decode("utf-8")
                    if all([
                        (txt.startswith("@") or txt.startswith("/**")),
                        node.start_point[0] - 1 == prev.end_point[0]
                    ]):
                        _add_scope(prev, scope_name)
                        _handle_decorators(prev, scope_name)

            def _visit_body(node: Node, scope_name: str) -> None:
                for child in self._get_node_body(node):
                    _visit_node(child, scope_name)

            def _visit_node(node: Node, scope_name: str = "global") -> None:
                if node.type in {"function_declaration", "method_definition"}:
                    new_scope = self._get_node_name(node, "<function>")
                    scope_name = f"{scope_name}.{new_scope}"  # concatenate with dot for methods

                    _handle_decorators(node, scope_name)
                    _add_scope(node, scope_name)
                    _visit_body(node, scope_name)

                elif node.type == "class_declaration":
                    new_scope = self._get_node_name(node, "<class>")
                    if scope_name != "global":
                        new_scope = f"{scope_name}:{new_scope}"  # concatenate with colon for classes

                    _handle_decorators(node, scope_name)
                    _add_scope(node, scope_name)
                    _visit_body(node, new_scope)

                else:
                    if any([
                        node.start_point is None,
                        node.end_point is None,
                        node.start_point[0] is None,
                        node.end_point[0] is None,
                        all([
                            scope_name == "global",
                            node.type == "comment",
                            not node.text.decode("utf-8").startswith("/**")
                        ])
                    ]):
                        pass
                    else:
                        _add_scope(node, scope_name)

            for root_child in tree.root_node.children:
                _visit_node(root_child)
            return line_scope_map

        added, removed = self._get_added_removed_lines(diff)

        tree_after = self._parse(after)
        after_map = []
        if tree_after is not None:
            line_scope_map_after = _build_line_scope_map(tree_after)
            for (added_line_number, added_line_text) in added:
                scope = line_scope_map_after.get(added_line_number, "global")
                after_map.append({added_line_text: scope})

        tree_before = self._parse(before)
        before_map = []
        if tree_before is not None:
            line_scope_map_before = _build_line_scope_map(tree_before)
            for (removed_line_number, removed_line_text) in removed:
                scope = line_scope_map_before.get(removed_line_number, "global")
                before_map.append({removed_line_text: scope})

        return before_map, after_map

    @staticmethod
    def _get_added_removed_lines(diff: str) -> [list, list]:
        """
        Analyzes diff to extract which lines have been changed.

        Parameters:
            diff (str): The diff to analyze

        Returns:
            list: Added lines
            list: Removed lines
        """

        added = []
        removed = []

        hunk_header_regex = re.compile(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@')
        diff_lines = diff.splitlines()
        i = 0

        while i < len(diff_lines):
            line = diff_lines[i]
            match = hunk_header_regex.match(line)
            if match:
                # start lines
                old_start = int(match.group(1))
                new_start = int(match.group(2))

                # line counters
                current_line_original = old_start - 1
                current_line_updated = new_start - 1
                i += 1

                while i < len(diff_lines) and not diff_lines[i].startswith('@@'):
                    patch_line = diff_lines[i]

                    # lines that begin with '+' but not "+++" are added lines
                    if patch_line.startswith('+') and not patch_line.startswith('+++'):
                        current_line_updated += 1
                        added_text = patch_line[1:]  # remove leading '+'
                        added.append((current_line_updated, added_text))

                    # lines that begin with '-' but not "---" are removed lines
                    elif patch_line.startswith('-') and not patch_line.startswith('---'):
                        current_line_original += 1
                        removed_text = patch_line[1:]  # remove leading '-'
                        removed.append((current_line_original, removed_text))

                    else:
                        # skip other lines
                        current_line_original += 1
                        current_line_updated += 1

                    i += 1
            else:
                i += 1

        return added, removed

    def _slice_javascript_code(self,
                               source_code: str,
                               global_funcs: list,
                               class2methods: dict) -> str:
        """
        Returns a 'sliced' version of the given source code, preserving
        original whitespace (and optionally annotating lines with original line numbers).

        The resulting code includes:
            1. All global variables (including import statements).
            2. Global functions whose names are in `global_funcs`.
            3. Classes (defined in the global scope) whose names are keys in `class_methods`.
                For each kept class:
                    - Keep all class-level assignments (properties).
                    - Keep the constructor (constructor()) if defined.
                    - Keep only the methods listed in class_methods[class_name].
                    - Keep JSDocs (which appear outside of class).
                    - Keep nested classes

        Parameters:
            source_code (str): The source code to slice
            global_funcs (list): The functions with a 'global' scope
            class2methods (dict): Holds which methods belong to a class

        Returns:
            str: The sliced source code
        """


        tree = self._parse(source_code)
        lines_to_skip: set[int] = set()
        source_lines = source_code.splitlines(keepends=True)

        def _is_jsdoc(node: Node) -> bool:
            return (
                    node.type == "comment"
                    and node.text.decode("utf-8").startswith("/**")
            )

        def _skip_lines(start: int, end: int) -> None:
            for ln in range(start, end + 1):
                lines_to_skip.add(ln)

        def _keep_lines(start: int, end: int) -> None:
            lines_to_skip.difference_update(list(range(start, end + 1)))

        def _keep_top_level_node(node: Node) -> bool:
            if node.type == "import_statement":
                return True
            if node.type in {"variable_declaration", "lexical_declaration"}:
                return True
            if node.type == "function_declaration":
                return self._get_node_name(node) in global_funcs
            if node.type == "class_declaration":
                return self._get_node_name(node) in class2methods
            if node.type == "comment":
                return not _is_jsdoc(node)
            return False

        def _keep_class_child(node: Node, class_name: str) -> bool:
            if node.type in {"variable_declaration", "lexical_declaration", "field_definition"}:
                return True
            if node.type == "comment":
                return not _is_jsdoc(node)
            if node.type == "method_definition":
                if self._get_node_name(node) == 'constructor':
                    return True
                allowed_list = [method_name.split(".") for method_name in class2methods[class_name]]
                if any(self._get_node_name(node) in sublist for sublist in allowed_list):
                    return True
            return False

        def _handle_decorators(node: Node) -> None:
            prev = node.prev_sibling
            if prev:
                txt = prev.text.decode("utf-8")
                if all([
                    (txt.startswith("@") or txt.startswith("/**")),
                    node.start_point[0] - 1 == prev.end_point[0]
                ]):
                    _mark_lines(prev, True)
                    _handle_decorators(prev)

        def _mark_lines(node: Node, keep: bool) -> None:
            if any([
                node.start_point is None,
                node.end_point is None,
                node.start_point[0] is None,
                node.end_point[0] is None
            ]):
                return

            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            if keep:
                _keep_lines(start_line, end_line)
            else:
                _skip_lines(start_line, end_line)
                return

            if node.type in {"class_declaration", "function_declaration", "method_definition"}:
                _handle_decorators(node)
            if node.type == "class_declaration":
                for child in self._get_node_body(node):
                    child_keep = _keep_class_child(child, self._get_node_name(node))
                    _mark_lines(child, child_keep)

        if tree is not None:
            for root_child in tree.root_node.children:
                keep_flag = _keep_top_level_node(root_child)
                _mark_lines(root_child, keep_flag)

            result_lines = []
            for i, original_line in enumerate(source_lines, start=1):
                if i not in lines_to_skip:
                    stripped_line = original_line.rstrip('\n')
                    annotated_line = f"{i} {stripped_line}\n"
                    result_lines.append(annotated_line)

            res = "".join(result_lines)
            res_cln = self._filter_stray_decorators(res)
            res_cln = re.sub(r'(^\d+ \n)(\d+ \n)+', r'\1', res_cln, flags=re.MULTILINE)
            return res_cln

        return ""

    @staticmethod
    def _build_function_class_maps(function_list: list) -> list:
        """
        Creates a list of dicts: [{"function_scope_name": scope}, ...] where `scope` is either
        the class name in which the function is defined, or "global" if
        it is defined at the top level.

        Parameters:
          function_list (list): Function names (full scope) to check

        Returns:
          list: Dictionaries with functions and their scope
        """

        results = []
        for item in function_list:
            parts = item.split(":")
            segments = [class_scope.split(".") for class_scope in parts]
            if len(segments) == 1 and len(segments[0]) > 1:  # If only one segment, no nested classes
                key = ".".join(segments[0][1:]) if segments[0][0] == "global" else item  # Skip "global" keyword
                results.append({key: segments[0][0]})
            elif len(segments) > 1:
                results.append({item: segments[-1][0]})
        return results

    def _build_test_scope_map(self, tree: Tree) -> dict:
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

        if tree is not None:
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

    def _filter_stray_decorators(self, file_content: str) -> str:
        """
        Removes any decorators which don't belong to a function or class.

        Parameters:
            file_content (str): The content to filter

        Returns:
            str: Code without stray decorators
        """

        lines = file_content.splitlines()
        kept = []
        i = 0
        n = len(lines)

        while i < n:
            line = lines[i]

            if self._is_decorator_start(line):
                decorator_blocks = []

                while i < n and self._is_decorator_start(lines[i]):
                    block_start = i
                    block_end = self._get_decorator_end(lines, block_start)
                    block_lines = lines[block_start: block_end + 1]
                    decorator_blocks.append(block_lines)
                    i = block_end + 1

                if i < n and self._is_function_or_class_start(lines[i]):
                    for block in decorator_blocks:
                        kept.extend(block)
                else:
                    pass

            else:
                kept.append(line)
                i += 1

        return "\n".join(kept)

    @staticmethod
    def _is_decorator_start(line: str) -> bool:
        """
        Checks if a line starts with optional digits/spaces followed by '@'.
        e.g. "300 @something", "   @something", "@something"

        Parameters:
            line (str): The line to check

        Returns:
            bool: True if the line is a decorator, False otherwise
        """

        return bool(re.match(r'^\s*\d*\s*@', line))

    @staticmethod
    def _is_function_or_class_start(line: str) -> bool:
        """
        Checks if a line starts with optional digits/spaces followed by:
          - an optional 'async' then 'function' (for global function declarations),
          - 'class', or
          - an optional 'async' then an identifier followed by '(' (for class method definitions).
        e.g. "  10 function foo() {", "  async function bar() {",
             "  class Baz {", or "  async myMethod() {"

        Parameters:
            line (str): The line to check

        Returns:
            bool: True if the line is a function or class, False otherwise
        """

        return bool(
            re.match(
                r'^\s*\d*\s*(?:(?:async\s+)?function\b|class\b|(?:async\s+)?[A-Za-z_$][A-Za-z0-9:$]*\s*\()',
                line
            )
        )

    @staticmethod
    def _get_decorator_end(lines: list, start_index: int) -> int:
        """
        Retrieves the last line index which still belongs to the decorator. Namely, if there
        are any brackets present which need to be included

        Parameters:
            lines (list): The lines to search
            start_index (int): The index of the first line to search

        Returns:
            int: The index of the last line which still belongs to the decorator
        """
        open_brackets = 0
        end_index = start_index
        i = start_index

        while i < len(lines):
            line = lines[i]
            for char in line:
                if char == '(':
                    open_brackets += 1
                elif char == ')':
                    open_brackets -= 1

            end_index = i
            i += 1

            if open_brackets == 0:
                break

        return end_index

    @staticmethod
    def _get_node_body(node: Node) -> list | None:
        """
        Return the body of a node (i.e., function / class body).

        Parameters:
            node (Node): The node to get the body of

        Returns:
            list: The body of the node
        """

        body = node.child_by_field_name("body")
        return body.named_children if body else []

    @staticmethod
    def _get_node_name(node: Node, fallback: str = "") -> str:
        """
        Return the name of a node (i.e., function / class name).

        Parameters:
            node (Node): The node to get the name of
            fallback (str, optional): The fallback name to return

        Returns:
            str: The name of the node
        """

        identifier = node.child_by_field_name("name")
        return identifier.text.decode("utf-8") if identifier else fallback

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
