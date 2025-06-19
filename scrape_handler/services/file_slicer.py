import re

from tree_sitter import Parser, Tree, Node

from scrape_handler.core.config import Config
from scrape_handler.core import git_tools
from scrape_handler.services.pr_diff_context import PullRequestDiffContext


class GoldenFileSlicer:
    def __init__(self, config: Config, pr_diff_ctx: PullRequestDiffContext):
        self.config = config
        self.pr_diff_ctx = pr_diff_ctx

    def slice_all(self):
        return self.slice_code_file(), self.slice_test_file()

    def slice_code_file(self):
        code_before = self.pr_diff_ctx.code_before
        if self.pr_diff_ctx.code_names:
            code_sliced = self.slice_golden_file(
                code_before,
                self.pr_diff_ctx.golden_code_patch,
                "",
                return_file="pre",
                append_line_numbers=True
            )
        else:
            code_sliced = code_before.copy()
        return code_sliced

    def slice_test_file(self):
        test_before = self.pr_diff_ctx.test_before
        if self.pr_diff_ctx.test_names:
            test_sliced = self.slice_golden_file(
                test_before,
                self.pr_diff_ctx.golden_test_patch,
                "",
                return_file="post",
                append_line_numbers=True
            )
        else:
            test_sliced = test_before.copy()
        return test_sliced

    def slice_golden_file(self,
                          golden_contents_before_arr,
                          patch,
                          issue_description,
                          return_file="pre",
                          append_line_numbers=False):
        golden_contents_after_arr, stderr = git_tools.apply_patch(golden_contents_before_arr, patch)
        # Create an array where element i is the relevant patch for file i
        # Assumption: file arrays contain the files in the order they appear in the patch
        #  => true by construction, we assert this in a different place
        patch_arr = ["diff --git" + x for x in patch.split("diff --git")[1:]]
        sliced_code_arr = []  # sliced code for each changed file

        golden_patch_entries = zip(golden_contents_before_arr, golden_contents_after_arr, patch_arr)

        for golden_contents_before, golden_contents_after, this_patch in golden_patch_entries:
            # lists where each element is {line_text: function_it_belongs}
            line2func_before, line2func_after, removed_lines_list, added_lines_list = self.get_edited_functions(
                golden_contents_before,
                golden_contents_after,
                this_patch
            )
            if not line2func_before and not line2func_after:
                # probably not a Python file, which made ast to fail => don't slice
                sliced_code_arr.append(golden_contents_before)
                continue

                # Get the functions from which lines were REMOVED
            edited_functions_before = [list(x.values())[0] for x in line2func_before]
            edited_lines_before = [list(x.keys())[0] for x in line2func_before]
            # Get the functions to which lines were ADDED
            edited_functions_after = [list(x.values())[0] for x in line2func_after]
            edited_lines_after = [list(x.keys())[0] for x in line2func_after]

            # Add them together and we have the edited functions
            # functions_to_keep = list(set(edited_functions_before + edited_functions_after))
            # functions_called_in_issue_desc = extract_python_function_calls(issue_description)

            # if return_file == "pre":
            mapping_before = self.map_functions_to_classes(edited_functions_before)
            # else: # "post"
            mapping_after = self.map_functions_to_classes(edited_functions_after)
            # TODO: by concatenating the mappings, we will have problems in the (very unlikely) scenario
            #  where a method is moved from one class to another.
            mapping = mapping_before + mapping_after
            class2methods = {}
            for method2class in mapping:
                for (k, v) in method2class.items():
                    class2methods[v] = class2methods.get(v, []) + [k]
            global_funcs = class2methods.pop('global', [])
            # global_funcs = []

            if return_file == "pre":  # apply slicing to the file before the patch
                sliced_code = self.slice_javascript_code(
                    golden_contents_before,
                    global_funcs,
                    class2methods,
                    append_line_numbers=append_line_numbers,
                    edited_lines=removed_lines_list
                )
            else:
                sliced_code = self.slice_javascript_code(
                    golden_contents_after,
                    global_funcs,
                    class2methods,
                    append_line_numbers=append_line_numbers,
                    edited_lines=added_lines_list
                )

            sliced_code_arr.append(sliced_code)
        return sliced_code_arr

    def get_edited_functions(self, code_before: str, code_after: str, diff: str) -> tuple:
        """
        Given:
          1) code: the contents of a .js file (string)
          2) diff: a patch in unified diff format (string)

        TODO: It only looks functions containing lines added in the updated version of the code
        so if a function is modified by only deleting lines it wouldn't get returned

        Returns:
          A list of dicts, each with the form:
            {added_line: high_level_function}
          where 'added_line' is the exact text of the line added by the patch,
          and 'high_level_function' is the *highest-level* function to which
          this line belongs (or "global" if it is not inside any function).
        """

        # -------------------------------------------------------------------------
        # 1) Parse the diff to identify which lines were added and their line
        #    numbers in the updated file.
        # -------------------------------------------------------------------------
        added_lines_info = []
        removed_lines_info = []

        hunk_header_regex = re.compile(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@')
        diff_lines = diff.splitlines()
        i = 0

        while i < len(diff_lines):
            line = diff_lines[i]
            match = hunk_header_regex.match(line)
            if match:
                # Extract the start lines for the old and new files
                old_start = int(match.group(1))
                new_start = int(match.group(2))

                # Initialize the counters for line numbers
                current_line_original = old_start - 1
                current_line_updated = new_start - 1
                i += 1

                # Process the lines in this diff hunk
                while i < len(diff_lines) and not diff_lines[i].startswith('@@'):
                    patch_line = diff_lines[i]

                    # Lines that begin with '+' but not "+++" are added lines
                    if patch_line.startswith('+') and not patch_line.startswith('+++'):
                        current_line_updated += 1
                        # We only track "new" line numbers for added lines
                        added_text = patch_line[1:]  # remove leading '+'
                        added_lines_info.append((current_line_updated, added_text))

                    # Lines that begin with '-' but not "---" are removed lines
                    elif patch_line.startswith('-') and not patch_line.startswith('---'):
                        current_line_original += 1
                        # We only track "old" line numbers for removed lines
                        removed_text = patch_line[1:]  # remove leading '-'
                        removed_lines_info.append((current_line_original, removed_text))

                    else:
                        # Unchanged lines (or lines like '---'/'+++') appear in both old & new files
                        # So increment both counters
                        current_line_original += 1
                        current_line_updated += 1

                    i += 1
            else:
                i += 1
        # Extract only the line numbers to return them
        removed_lines_list = [x[0] for x in removed_lines_info]
        added_lines_list = [x[0] for x in added_lines_info]

        # -------------------------------------------------------------------------
        # 2) Parse the updated code with tree-sitter, and figure out for *every line*
        #    which top-level function it belongs to (or "global").
        # -------------------------------------------------------------------------

        # Parse code with tree-sitter
        try:
            tree_after = Parser(self.config.parse_language).parse(bytes(code_after, 'utf-8'))
        except SyntaxError as e:
            # Maybe a non-javascript file was edited (e.g., .css), return empty array
            tree_after = None

        try:
            tree_before = Parser(self.config.parse_language).parse(bytes(code_before, 'utf-8'))
        except SyntaxError as e:
            # Maybe a non-javascript file was edited (e.g., .css), return empty array
            tree_before = None

        def build_line_scope_map(tree: Tree) -> dict:
            line_scope_map = {}

            def mark_lines(node: Node, scope_name: str) -> None:
                # Mark line number with scope
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

            def mark_decorators(node: Node, scope_name: str) -> None:
                # Mark decorator lines & JSDocs if present
                prev = node.prev_sibling
                if prev:
                    txt = prev.text.decode("utf-8")
                    if all([  # If decorate found and without empty previous lines
                        (txt.startswith("@") or txt.startswith("/**")),
                        node.start_point[0] - 1 == prev.end_point[0]
                    ]):
                        mark_lines(prev, scope_name)
                        mark_decorators(prev, scope_name)  # Iterate further back in case of several

            def visit_body(node: Node, scope_name: str) -> None:
                # Visit the function/class body if available
                for child in self.get_node_body(node):
                    visit_node(child, scope_name)

            def visit_node(node: Node, scope_name: str = "global") -> None:
                if node.type in {"function_declaration", "method_definition"}:
                    new_scope = self.get_node_name(node, "<function>")
                    scope_name = f"{scope_name}.{new_scope}"  # Concatenate with dot for methods

                    mark_decorators(node, scope_name)
                    mark_lines(node, scope_name)
                    visit_body(node, scope_name)

                elif node.type == "class_declaration":
                    new_scope = self.get_node_name(node, "<class>")
                    if scope_name != "global":
                        # If class is nested, concatenate with colon to easily differentiate
                        new_scope = f"{scope_name}:{new_scope}"

                    mark_decorators(node, scope_name)
                    mark_lines(node, scope_name)
                    visit_body(node, new_scope)

                else:
                    # For other nodes, use the current scope
                    if any([  # Skip nodes with missing line info
                        node.start_point is None,
                        node.end_point is None,
                        node.start_point[0] is None,
                        node.end_point[0] is None,
                        all([  # Skip global comments
                            scope_name == "global",
                            node.type == "comment",
                            not node.text.decode("utf-8").startswith("/**")
                        ])
                    ]):
                        pass
                    else:
                        mark_lines(node, scope_name)

            for root_child in tree.root_node.children:
                visit_node(root_child)
            return line_scope_map

        # Walk through tree-sitter to fill line_scope_map with function scopes or 'global'
        # We'll store the scope of each line in a dictionary: line -> function_scope_name or "global"
        map_arr_after = []
        if tree_after is not None:
            line_scope_map_after = build_line_scope_map(tree_after)

            for (added_line_number, added_line_text) in added_lines_info:
                scope = line_scope_map_after.get(added_line_number, "global")
                map_arr_after.append({added_line_text: scope})

        map_arr_before = []
        if tree_before is not None:
            line_scope_map_before = build_line_scope_map(tree_before)

            for (added_line_number, added_line_text) in removed_lines_info:
                scope = line_scope_map_before.get(added_line_number, "global")
                map_arr_before.append({added_line_text: scope})

        return map_arr_before, map_arr_after, removed_lines_list, added_lines_list

    @staticmethod
    def map_functions_to_classes(function_list: list[str]) -> list:
        """
        Given:
          function_list: a list of function names (full scope) that we want to check

        Returns:
          A list of dicts: [{"function_scope_name": scope}, ...] where `scope` is either
          the class name in which the function is defined, or "global" if
          it is defined at the top level.

          Example return value:
          [
              {"MyClass.my_func": "MyClass"},
              {"other_func": "global"}
          ]
        """

        # For each function in our list, report the scope we found (or "global" if missing)
        results = []
        for item in function_list:
            parts = item.split(":")
            segments = [class_scope.split(".") for class_scope in parts]
            if len(segments) == 1 and len(segments[0]) > 1:  # If only one segment, no nested classes
                key = ".".join(segments[0][1:]) if segments[0][0] == "global" else item  # Skip "global" keyword
                results.append({key: segments[0][0]})
            elif len(segments) > 1:
                # For more than one segment there are nested classes, first part of last segment is parent class
                results.append({item: segments[-1][0]})
        return results

    def slice_javascript_code(self,
                              source_code: str,
                              global_funcs: list[str],
                              class_methods: dict[str, list[str]],
                              append_line_numbers: bool = False,
                              edited_lines: list[int] = []) -> str:
        """
        Return a 'sliced' version of the given Javascript source code, preserving
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
        If `append_line_numbers` is True, each kept line starts with the line number of the original source.
        If it is False, then instead of line numbers, the edited lines start with
        a '+' (edited lines are in the edited_lines list)
        NOTE: This approach *skips entire lines* belonging to unwanted nodes.
              It does not attempt partial-line slicing.
        """

        # Parse the code with tree-sitter
        tree = Parser(self.config.parse_language).parse(bytes(source_code, 'utf-8'))

        # We'll create a "skip set" of line numbers to exclude from final output.
        # tree-sitter's nodes have start and end points, 0-based.
        # We'll later skip all lines in these ranges for nodes we *don't* want.
        lines_to_skip: set[int] = set()

        # Convert the source into a list of lines for easy indexing
        source_lines = source_code.splitlines(keepends=True)  # keep original \n

        # --- Helper functions ---

        def is_jsdoc(node: Node) -> bool:
            """
            Returns True if 'node' is a comment node containing a JSDoc
            """
            return (
                    node.type == "comment"
                    and node.text.decode("utf-8").startswith("/**")
            )

        def mark_lines_skip(start: int, end: int) -> None:
            """Mark all lines [start, end] (inclusive) to be skipped."""
            for ln in range(start, end + 1):
                lines_to_skip.add(ln)

        def mark_lines_keep(start: int, end: int) -> None:
            """Mark all lines [start, end] (inclusive) to be kept if skipped unintentionally (i.e., decorators)."""
            lines_to_skip.difference_update(list(range(start, end + 1)))

        def keep_top_level_node(node: Node) -> bool:
            """Decide if a top-level node is to be kept."""
            # 1. Keep import statements
            if node.type == "import_statement":
                return True
            # 2. Keep top-level assignments
            if node.type in {"variable_declaration", "lexical_declaration"}:
                return True
            # 3. Keep top-level functions if name is in global_funcs
            if node.type == "function_declaration":
                return self.get_node_name(node) in global_funcs
            # 4. Keep top-level classes if name is in class_methods
            if node.type == "class_declaration":
                return self.get_node_name(node) in class_methods
            # 5. Keep top-level comments (except global JSDocs not assigned to a class or function)
            if node.type == "comment":
                return not is_jsdoc(node)
            return False

        def keep_class_child(node: Node, class_name: str) -> bool:
            """
            Decide if a node *inside* a class body is to be kept.
            """
            # Keep class-level assignments
            if node.type in {"variable_declaration", "lexical_declaration", "field_definition"}:
                return True
            # Only keep comments, mark decorators later for allowed methods
            if node.type == "comment":
                return not is_jsdoc(node)
            # Keep methods if they match criteria
            if node.type == "method_definition":
                if self.get_node_name(node) == 'constructor':
                    return True
                # Or if the method is in the allowed list (split last segment to get method name from scope)
                allowed_list = [method_name.split(".") for method_name in class_methods[class_name]]
                if any(self.get_node_name(node) in sublist for sublist in allowed_list):
                    return True
            # Otherwise, skip
            return False

        def keep_decorators(node: Node) -> None:
            # Mark decorator lines & JSDocs if present
            prev = node.prev_sibling
            if prev:
                txt = prev.text.decode("utf-8")
                if all([
                    (txt.startswith("@") or txt.startswith("/**")),
                    node.start_point[0] - 1 == prev.end_point[0]
                ]):
                    mark_node(prev, True)
                    keep_decorators(prev)

        def mark_node(node: Node, keep: bool) -> None:
            """
            Recursively mark lines to keep or skip based on the 'keep' flag.

            If we skip, all lines of this node are marked as skipped.
            If we keep, we *may still skip children* if we are inside a class and
            the child isn't wanted.
            """
            if any([  # Skip nodes with missing line info
                node.start_point is None,
                node.end_point is None,
                node.start_point[0] is None,
                node.end_point[0] is None
            ]):
                # Some nodes (e.g. interactive mode) may not have line info
                return

            # If we're skipping this node, skip all its lines
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            if keep:
                mark_lines_keep(start_line, end_line)
            else:
                mark_lines_skip(start_line, end_line)
                return

            if node.type in {"class_declaration", "function_declaration", "method_definition"}:
                keep_decorators(node)
            # If it's a class declaration, we need to process children
            if node.type == "class_declaration":
                # The node itself is kept, but we might skip unwanted child nodes
                body = node.child_by_field_name("body")
                if body:
                    for child in body.named_children:
                        child_keep = keep_class_child(child, self.get_node_name(node))
                        mark_node(child, child_keep)

        # --- Main slicing logic ---
        # 1) Walk top-level nodes and mark them keep/skip
        for root_child in tree.root_node.children:
            keep_flag = keep_top_level_node(root_child)
            mark_node(root_child, keep_flag)

        # 2) Rebuild final code, skipping lines we marked
        result_lines = []
        for i, original_line in enumerate(source_lines, start=1):
            if i not in lines_to_skip:  # and original_line.strip():
                if append_line_numbers:
                    # Strip trailing newline if any, append comment, then re-add newline
                    stripped_line = original_line.rstrip('\n')
                    annotated_line = f"{i} {stripped_line}\n"
                    result_lines.append(annotated_line)
                else:
                    if i in edited_lines:
                        annotated_line = f"+{original_line}"
                        result_lines.append(annotated_line)
                    else:
                        annotated_line = f" {original_line}"
                        result_lines.append(annotated_line)

        res = "".join(result_lines)
        res_cln = self.filter_stray_decorators(res)
        if append_line_numbers:  # Collapse multiple newlines starting with an integer to one
            res_cln = re.sub(r'(^\d+ \n)(\d+ \n)+', r'\1', res_cln, flags=re.MULTILINE)
        else:  # Collapse multiple newlines to one
            res_cln = re.sub(r'(\n )+', r'\n ', res_cln)
        return res_cln

    @staticmethod
    def get_node_body(node: Node) -> list | None:
        """Return the body of a node (i.e., function / class body)."""
        body = node.child_by_field_name("body")
        return body.named_children if body else []

    @staticmethod
    def get_node_name(node: Node, fallback="") -> str:
        """Return the name of a node (i.e., function / class name)."""
        identifier = node.child_by_field_name("name")
        return identifier.text.decode("utf-8") if identifier else fallback

    def filter_stray_decorators(self, text: str) -> str:
        """
        1) Finds blocks of consecutive decorators (each block may be multi-line if parentheses).
        2) Keeps all those decorator blocks only if the next line afterward is 'def' or 'class'
           (with optional digits/spaces).
        3) Otherwise, discards them. Any non-decorator lines are kept automatically.
        """
        lines = text.splitlines()
        kept = []
        i = 0
        n = len(lines)

        while i < n:
            line = lines[i]

            # If this line starts a decorator
            if self.is_decorator_start(line):
                # We'll collect all consecutive decorator blocks
                decorator_blocks = []

                # Keep going while the line starts with '@'
                while i < n and self.is_decorator_start(lines[i]):
                    # Find the end of this one decorator block
                    block_start = i
                    block_end = self.find_decorator_end(lines, block_start)

                    # Slice out that block
                    block_lines = lines[block_start: block_end + 1]
                    decorator_blocks.append(block_lines)

                    # Move i to the line after the block
                    i = block_end + 1

                # Now i is at a line that does NOT start with '@' or it's beyond the end.
                # We check if that line starts with 'def' or 'class'
                if i < n and self.is_function_or_class_start(lines[i]):
                    # Keep *all* consecutive decorator blocks
                    for block in decorator_blocks:
                        kept.extend(block)
                else:
                    # Discard them all (do nothing)
                    pass

            else:
                # Normal line => keep it
                kept.append(line)
                i += 1

        return "\n".join(kept)

    @staticmethod
    def is_decorator_start(line: str) -> bool:
        """
        Check if a line starts with optional digits/spaces followed by '@'.
        e.g. "300 @something", "   @something", "@something"
        """
        return bool(re.match(r'^\s*\d*\s*@', line))

    @staticmethod
    def is_function_or_class_start(line: str) -> bool:
        """
        Check if a line starts with optional digits/spaces followed by:
          - an optional 'async' then 'function' (for global function declarations),
          - 'class', or
          - an optional 'async' then an identifier followed by '(' (for class method definitions).
        e.g. "  10 function foo() {", "  async function bar() {",
             "  class Baz {", or "  async myMethod() {"
        """
        return bool(
            re.match(
                r'^\s*\d*\s*(?:(?:async\s+)?function\b|class\b|(?:async\s+)?[A-Za-z_$][A-Za-z0-9:$]*\s*\()',
                line
            )
        )

    @staticmethod
    def find_decorator_end(lines: list[str], start_index: int) -> int:
        """
        Given a list of lines and the index of a line that starts a decorator ('@'),
        return the last line index that belongs to this decorator block.

        A decorator can span multiple lines if parentheses are opened '(' and not yet closed.
        We'll count '(' and ')' across lines until balanced or until we run out of lines.
        """
        open_parens = 0
        end_index = start_index
        i = start_index

        while i < len(lines):
            line = lines[i]
            # Count parentheses
            for char in line:
                if char == '(':
                    open_parens += 1
                elif char == ')':
                    open_parens -= 1

            end_index = i
            i += 1

            # If parentheses are balanced (or never opened), stop.
            if open_parens == 0:
                break

        return end_index
