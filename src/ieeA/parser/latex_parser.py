import os
import re
import uuid
from typing import Optional, Tuple, List, Dict, Set

from .structure import LaTeXDocument, Chunk


def is_placeholder_only(content: str) -> bool:
    return bool(re.fullmatch(r"\[\[[A-Z_]+_\d+\]\]", content.strip()))


class LaTeXParser:
    """
    Parses LaTeX files into a structured LaTeXDocument.
    Uses placeholder-based approach to preserve document structure.
    """

    PROTECTED_ENVIRONMENTS = {
        "equation",
        "align",
        "gather",
        "split",
        "eqnarray",
        "multline",
        "equation*",
        "align*",
        "gather*",
        "eqnarray*",
        "multline*",
        "tikzpicture",
        "lstlisting",
        "verbatim",
        "minted",
        "algorithm",
        "algorithm2e",
        "algorithmic",
    }

    TRANSLATABLE_ENVIRONMENTS = {
        "abstract",
        "itemize",
        "enumerate",
        "description",
    }
    CAPTION_NO_SCAN_ENVIRONMENTS = {
        "verbatim",
        "lstlisting",
        "minted",
    }

    # NOTE: caption 不在此列表中，因为它在 _extract_captions() 中单独处理
    SECTION_COMMANDS = {
        "section",
        "subsection",
        "subsubsection",
        "paragraph",
        "subparagraph",
        "chapter",
        "part",
    }

    def __init__(self, extra_protected_envs: Optional[List[str]] = None):
        self.chunks: List[Chunk] = []
        self.protected_counter = 0
        self.placeholder_map: Dict[str, str] = {}
        self._protected_envs: Set[str] = set(self.PROTECTED_ENVIRONMENTS)
        if extra_protected_envs:
            self._protected_envs.update(extra_protected_envs)

    def extract_abstract(self, content: str) -> Optional[str]:
        """Extract abstract content from LaTeX document.

        Args:
            content: Full LaTeX document content

        Returns:
            Abstract text or None if not found
        """
        # Match \begin{abstract}...\end{abstract}
        pattern = re.compile(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", re.DOTALL)
        match = pattern.search(content)
        if match:
            abstract_text = match.group(1)
            # Filter out LaTeX comment lines (lines starting with %)
            lines = abstract_text.split("\n")
            filtered_lines = [
                line for line in lines if not line.strip().startswith("%")
            ]
            abstract_text = "\n".join(filtered_lines).strip()
            # Truncate to ~500 tokens (≈2000 chars)
            if len(abstract_text) > 2000:
                abstract_text = abstract_text[:2000] + "..."
            return abstract_text if abstract_text else None
        return None

    def parse_file(self, filepath: str) -> LaTeXDocument:
        base_dir = os.path.dirname(os.path.abspath(filepath))
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        flattened_content = self._flatten_latex(content, base_dir)
        flattened_content = self._remove_comments(flattened_content)
        abstract = self.extract_abstract(flattened_content)
        preamble, body_content = self._split_preamble_body(flattened_content)

        self.chunks = []
        self.protected_counter = 0
        self.placeholder_map = {}

        preamble = self._extract_title_command(preamble)
        preamble = self._inject_chinese_support(preamble)
        body_content = self._extract_title_command(body_content)

        body_template = self._process_body(body_content)

        # Consistency check: all chunks should have placeholders
        import warnings

        chunk_ids_in_preamble = set(re.findall(r"\{\{CHUNK_([a-f0-9-]+)\}\}", preamble))
        chunk_ids_in_body = set(
            re.findall(r"\{\{CHUNK_([a-f0-9-]+)\}\}", body_template)
        )
        all_placeholder_ids = chunk_ids_in_preamble | chunk_ids_in_body
        chunk_ids_created = set(c.id for c in self.chunks)
        protected_chunk_ids = set(c.id for c in self.chunks if c.context == "protected")

        orphan_ids = chunk_ids_created - all_placeholder_ids - protected_chunk_ids
        if orphan_ids:
            warnings.warn(
                f"LaTeX Parser: {len(orphan_ids)} chunk(s) created without placeholders. "
                f"This may cause untranslated content in output.",
                UserWarning,
            )

        return LaTeXDocument(
            preamble=preamble,
            chunks=self.chunks,
            body_template=body_template,
            abstract=abstract,
            global_placeholders=self.placeholder_map,
        )

    def _protect_author_block(self, text: str) -> str:
        # Match \author{ start
        pattern = re.compile(r"(\\author\s*\{)", re.DOTALL)
        result = []
        pos = 0

        for match in pattern.finditer(text):
            # Add text before the match
            result.append(text[pos : match.start()])

            # Find the matching closing brace
            start = match.end()
            brace_count = 1
            i = start

            while i < len(text) and brace_count > 0:
                if text[i] == "{":
                    brace_count += 1
                elif text[i] == "}":
                    brace_count -= 1
                i += 1

            # Check if we found the closing brace
            if brace_count == 0:
                # Extract the full author block including \author{...}
                full_block = match.group(0) + text[start:i]

                self.protected_counter += 1
                placeholder = f"[[AUTHOR_{self.protected_counter}]]"
                chunk_id = str(uuid.uuid4())

                chunk = Chunk(
                    id=chunk_id,
                    content=placeholder,
                    latex_wrapper="%s",
                    context="protected",
                    preserved_elements={placeholder: full_block},
                )
                self.chunks.append(chunk)
                result.append(placeholder)
                pos = i
            else:
                # Unbalanced braces, just keep the original text
                # to avoid swallowing the rest of the document
                result.append(match.group(0))
                pos = match.end()

        result.append(text[pos:])
        return "".join(result)

    def _inject_chinese_support(self, preamble: str) -> str:
        """Inject Chinese support using auto-detected system fonts."""
        from ..compiler.chinese_support import inject_chinese_support

        return inject_chinese_support(preamble)

    def _extract_title_command(self, text: str) -> str:
        """Extract \\title{...} command content and create title chunks."""
        pattern = re.compile(r"(\\title\s*\{)")
        result = []
        pos = 0

        for match in pattern.finditer(text):
            result.append(text[pos : match.start()])
            start = match.end()
            brace_count = 1
            i = start

            while i < len(text) and brace_count > 0:
                if text[i] == "{":
                    brace_count += 1
                elif text[i] == "}":
                    brace_count -= 1
                i += 1

            if brace_count == 0:
                content = text[start : i - 1]
                stripped_content = content.strip()
                if (
                    not stripped_content
                    or stripped_content.startswith("[[")
                    or stripped_content.startswith("{{CHUNK_")
                ):
                    result.append(match.group(0) + content + "}")
                else:
                    chunk_id = str(uuid.uuid4())
                    placeholder = f"{{{{CHUNK_{chunk_id}}}}}"
                    chunk = Chunk(
                        id=chunk_id,
                        content=stripped_content,
                        latex_wrapper="%s",
                        context="title",
                        preserved_elements={},
                    )
                    self.chunks.append(chunk)
                    result.append(match.group(1) + placeholder + "}")
                pos = i
            else:
                result.append(match.group(0))
                pos = match.end()

        result.append(text[pos:])
        return "".join(result)

    def _skip_whitespace(self, text: str, index: int) -> int:
        i = index
        while i < len(text) and text[i].isspace():
            i += 1
        return i

    def _parse_balanced_group(
        self, text: str, start: int, open_char: str, close_char: str
    ) -> Tuple[Optional[str], Optional[int]]:
        """Parse a balanced group and return (inner_content, end_index)."""
        if start >= len(text) or text[start] != open_char:
            return None, None

        depth = 1
        i = start + 1
        while i < len(text):
            ch = text[i]
            if ch == "\\":
                # Skip escaped character so \\{ and \\} don't affect nesting.
                i += 2
                continue
            if ch == open_char:
                depth += 1
            elif ch == close_char:
                depth -= 1
                if depth == 0:
                    return text[start + 1 : i], i + 1
            i += 1
        return None, None

    def _parse_environment_token_at(
        self, text: str, index: int, token: str
    ) -> Tuple[Optional[str], Optional[int]]:
        """Parse \\begin{env} or \\end{env} at index and return (env, end_idx)."""
        prefix = "\\" + token
        if not text.startswith(prefix, index):
            return None, None

        i = self._skip_whitespace(text, index + len(prefix))
        env_name, end_idx = self._parse_balanced_group(text, i, "{", "}")
        if env_name is None or end_idx is None:
            return None, None
        return env_name.strip(), end_idx

    def _find_environment_end(
        self, text: str, search_start: int, env_name: str
    ) -> Optional[int]:
        """Find matching \\end{env_name} from search_start with nesting support."""
        depth = 1
        i = search_start
        while i < len(text):
            begin_env, begin_end = self._parse_environment_token_at(text, i, "begin")
            if begin_env is not None and begin_end is not None:
                if begin_env == env_name:
                    depth += 1
                i = begin_end
                continue

            end_env, end_end = self._parse_environment_token_at(text, i, "end")
            if end_env is not None and end_end is not None:
                if end_env == env_name:
                    depth -= 1
                    if depth == 0:
                        return end_end
                i = end_end
                continue

            i += 1
        return None

    def _build_caption_no_scan_ranges(self, text: str) -> List[Tuple[int, int]]:
        """Build ranges where caption scanning should be disabled."""
        ranges: List[Tuple[int, int]] = []
        i = 0
        while i < len(text):
            env_name, begin_end = self._parse_environment_token_at(text, i, "begin")
            if env_name is not None and begin_end is not None:
                if env_name in self.CAPTION_NO_SCAN_ENVIRONMENTS:
                    end_idx = self._find_environment_end(text, begin_end, env_name)
                    if end_idx is None:
                        end_idx = len(text)
                    ranges.append((i, end_idx))
                    i = end_idx
                    continue
                i = begin_end
                continue
            i += 1
        return ranges

    def _parse_caption_command_at(
        self, text: str, cmd_start: int
    ) -> Tuple[Optional[int], Optional[int], Optional[str], Optional[str]]:
        """Parse caption family command at cmd_start.

        Returns:
            (body_start, body_end, content, replacement_prefix)
            where replacement_prefix is text before body braces.
        """
        n = len(text)
        if text.startswith("\\captionof", cmd_start):
            cursor = cmd_start + len("\\captionof")
            cursor = self._skip_whitespace(text, cursor)

            # captionof requires first mandatory arg: {figure|table|...}
            _, type_end = self._parse_balanced_group(text, cursor, "{", "}")
            if type_end is None:
                return None, None, None, None
            cursor = self._skip_whitespace(text, type_end)
        elif text.startswith("\\caption*", cmd_start):
            cursor = cmd_start + len("\\caption*")
            cursor = self._skip_whitespace(text, cursor)
        elif text.startswith("\\caption", cmd_start):
            cursor = cmd_start + len("\\caption")
            cursor = self._skip_whitespace(text, cursor)
        else:
            return None, None, None, None

        # Optional list entry argument (supports nested brackets)
        if cursor < n and text[cursor] == "[":
            _, opt_end = self._parse_balanced_group(text, cursor, "[", "]")
            if opt_end is None:
                return None, None, None, None
            cursor = self._skip_whitespace(text, opt_end)

        if cursor >= n or text[cursor] != "{":
            return None, None, None, None

        content, body_end = self._parse_balanced_group(text, cursor, "{", "}")
        if content is None or body_end is None:
            return None, None, None, None

        replacement_prefix = text[cmd_start:cursor]
        return cursor, body_end, content, replacement_prefix

    def _extract_captions(self, text: str) -> str:
        """Extract caption content for translation before environment protection."""
        no_scan_ranges = self._build_caption_no_scan_ranges(text)
        command_pattern = re.compile(r"\\caption(?:of)?\*?(?![A-Za-z])")

        result = []
        pos = 0
        range_idx = 0

        for match in command_pattern.finditer(text):
            cmd_start = match.start()

            while (
                range_idx < len(no_scan_ranges)
                and cmd_start >= no_scan_ranges[range_idx][1]
            ):
                range_idx += 1

            if range_idx < len(no_scan_ranges):
                start, end = no_scan_ranges[range_idx]
                if start <= cmd_start < end:
                    continue

            body_start, body_end, content, replacement_prefix = (
                self._parse_caption_command_at(text, cmd_start)
            )
            if (
                body_start is None
                or body_end is None
                or content is None
                or replacement_prefix is None
            ):
                continue

            result.append(text[pos:cmd_start])

            stripped = content.strip()
            if (
                stripped
                and not stripped.startswith("[[")
                and not stripped.startswith("{{CHUNK_")
            ):
                chunk_id = str(uuid.uuid4())
                placeholder = f"{{{{CHUNK_{chunk_id}}}}}"
                chunk = Chunk(
                    id=chunk_id,
                    content=stripped,
                    latex_wrapper="%s",
                    context="caption",
                    preserved_elements={},
                )
                self.chunks.append(chunk)
                result.append(replacement_prefix + "{" + placeholder + "}")
            else:
                result.append(text[cmd_start:body_end])

            pos = body_end

        result.append(text[pos:])
        return "".join(result)

    # Backward-compatible alias for existing internal/external calls.
    def _extract_title_from_preamble(self, preamble: str) -> str:
        return self._extract_title_command(preamble)

    def _process_body(self, body: str) -> str:
        result = body

        result = self._extract_pre_protection_chunks(result)
        result = self._protect_environments(result)
        result = self._protect_inline_math(result)
        result = self._protect_commands(result)
        result = self._extract_translatable_text(result)

        return result

    def _extract_pre_protection_chunks(self, text: str) -> str:
        text = self._protect_author_block(text)
        text = self._extract_captions(text)
        return text

    def _protect_environments(self, text: str) -> str:
        for env in self._protected_envs:
            text = self._protect_single_environment(text, env)
        return text

    # Backward-compatible alias for existing internal/external calls.
    def _protect_math_environments(self, text: str) -> str:
        return self._protect_environments(text)

    def _protect_single_environment(self, text: str, env: str) -> str:
        begin_pattern = re.compile(r"(\\begin\{" + re.escape(env) + r"\})")
        result = []
        pos = 0

        for match in begin_pattern.finditer(text):
            result.append(text[pos : match.start()])
            start = match.start()
            env_count = 1
            i = match.end()

            while i < len(text) and env_count > 0:
                if text[i:].startswith(r"\begin{" + env + "}"):
                    env_count += 1
                    i += len(r"\begin{" + env + "}")
                elif text[i:].startswith(r"\end{" + env + "}"):
                    env_count -= 1
                    if env_count == 0:
                        i += len(r"\end{" + env + "}")
                        break
                    else:
                        i += len(r"\end{" + env + "}")
                else:
                    i += 1

            if env_count == 0:
                full_env = text[start:i]
                self.protected_counter += 1
                placeholder = f"[[MATHENV_{self.protected_counter}]]"
                self.placeholder_map[placeholder] = full_env
                result.append(placeholder)
                pos = i
            else:
                result.append(match.group(0))
                pos = match.end()

        result.append(text[pos:])
        return "".join(result)

    def _protect_inline_math(self, text: str) -> str:
        result = []
        i = 0
        n = len(text)

        while i < n:
            if i < n - 1 and text[i] == "\\" and text[i + 1] == "$":
                result.append(text[i : i + 2])
                i += 2
                continue

            if text[i] == "$":
                is_display = i + 1 < n and text[i + 1] == "$"
                delim = "$$" if is_display else "$"
                start = i
                i += len(delim)

                while i < n:
                    if text[i] == "\\" and i + 1 < n and text[i + 1] == "$":
                        i += 2
                        continue
                    if is_display and i + 1 < n and text[i : i + 2] == "$$":
                        i += 2
                        break
                    if not is_display and text[i] == "$":
                        i += 1
                        break
                    i += 1

                math_content = text[start:i]
                if "\n\n" not in math_content:
                    self.protected_counter += 1
                    placeholder = f"[[MATH_{self.protected_counter}]]"
                    self.placeholder_map[placeholder] = math_content
                    result.append(placeholder)
                else:
                    result.append(math_content)
            else:
                result.append(text[i])
                i += 1

        text = "".join(result)

        text = self._protect_display_math_delimiters(text, r"\[", r"\]")
        text = self._protect_display_math_delimiters(text, r"\(", r"\)")
        return text

    def _protect_display_math_delimiters(
        self, text: str, open_delim: str, close_delim: str
    ) -> str:
        open_escaped = re.escape(open_delim)
        pattern = re.compile(r"(" + open_escaped + r")")
        result = []
        pos = 0

        for match in pattern.finditer(text):
            result.append(text[pos : match.start()])
            start = match.start()
            i = match.end()
            delim_len = len(open_delim)

            while i < len(text):
                if text[i : i + len(close_delim)] == close_delim:
                    i += len(close_delim)
                    full_math = text[start:i]
                    self.protected_counter += 1
                    placeholder = f"[[MATH_{self.protected_counter}]]"
                    self.placeholder_map[placeholder] = full_math
                    result.append(placeholder)
                    pos = i
                    break
                i += 1
            else:
                result.append(match.group(0))
                pos = match.end()

        result.append(text[pos:])
        return "".join(result)

    def _protect_commands(self, text: str) -> str:
        commands_with_brace_counting = [
            ("cite", "CITE"),
            ("ref", "REF"),
            ("eqref", "REF"),
            ("label", "LABEL"),
            ("url", "URL"),
            ("footnote", "FOOTNOTE"),
            ("href", "HREF"),
        ]
        for cmd, prefix in commands_with_brace_counting:
            text = self._protect_nested_command(text, cmd, prefix)

        text = self._protect_includegraphics(text)

        return text

    def _protect_includegraphics(self, text: str) -> str:
        pattern = re.compile(r"(\\includegraphics(?:\[[^\]]*\])?\s*\{)")
        result = []
        pos = 0

        for match in pattern.finditer(text):
            result.append(text[pos : match.start()])
            start = match.end()
            brace_count = 1
            i = start

            while i < len(text) and brace_count > 0:
                if text[i] == "{":
                    brace_count += 1
                elif text[i] == "}":
                    brace_count -= 1
                i += 1

            if brace_count == 0:
                full_command = match.group(0) + text[start:i]
                self.protected_counter += 1
                placeholder = f"[[GRAPHICS_{self.protected_counter}]]"
                self.placeholder_map[placeholder] = full_command
                result.append(placeholder)
                pos = i
            else:
                result.append(match.group(0))
                pos = match.end()

        result.append(text[pos:])
        return "".join(result)

    def _protect_nested_command(self, text: str, cmd: str, prefix: str) -> str:
        """Protect commands that may contain nested braces using brace counting."""
        pattern = re.compile(r"(\\" + cmd + r"\s*\{)")
        result = []
        pos = 0

        for match in pattern.finditer(text):
            result.append(text[pos : match.start()])
            start = match.end()
            brace_count = 1
            i = start

            while i < len(text) and brace_count > 0:
                if text[i] == "{":
                    brace_count += 1
                elif text[i] == "}":
                    brace_count -= 1
                i += 1

            if brace_count == 0:
                full_command = match.group(0) + text[start:i]
                self.protected_counter += 1
                placeholder = f"[[{prefix}_{self.protected_counter}]]"
                self.placeholder_map[placeholder] = full_command
                result.append(placeholder)
                pos = i
            else:
                # Unbalanced braces, keep original
                result.append(match.group(0))
                pos = match.end()

        result.append(text[pos:])
        return "".join(result)

    def _replace_with_placeholder(
        self, text: str, pattern: re.Pattern, prefix: str, force: bool = False
    ) -> str:
        def replacer(match):
            matched_text = match.group(0)
            if not force and "{{CHUNK_" in matched_text:
                return matched_text

            self.protected_counter += 1
            placeholder = f"[[{prefix}_{self.protected_counter}]]"
            self.placeholder_map[placeholder] = matched_text
            return placeholder

        return pattern.sub(replacer, text)

    def _extract_section_command(self, text: str, cmd: str) -> str:
        """Extract section commands with brace counting to handle nested braces."""
        pattern = re.compile(r"(\\" + cmd + r")(\*?)(\s*\{)")
        result = []
        pos = 0

        for match in pattern.finditer(text):
            result.append(text[pos : match.start()])
            start = match.end()
            brace_count = 1
            i = start

            while i < len(text) and brace_count > 0:
                if text[i] == "{":
                    brace_count += 1
                elif text[i] == "}":
                    brace_count -= 1
                i += 1

            if brace_count == 0:
                content = text[start : i - 1]
                if not content.strip() or content.startswith("[["):
                    result.append(match.group(0) + content + "}")
                else:
                    chunk_id = str(uuid.uuid4())
                    placeholder = f"{{{{CHUNK_{chunk_id}}}}}"
                    chunk = Chunk(
                        id=chunk_id,
                        content=content,
                        latex_wrapper="%s",
                        context=cmd,
                        preserved_elements={},
                    )
                    self.chunks.append(chunk)
                    result.append(
                        match.group(1)
                        + match.group(2)
                        + match.group(3)
                        + placeholder
                        + "}"
                    )
                pos = i
            else:
                result.append(match.group(0))
                pos = match.end()

        result.append(text[pos:])
        return "".join(result)

    def _extract_translatable_text(self, text: str) -> str:
        for cmd in self.SECTION_COMMANDS:
            text = self._extract_section_command(text, cmd)

        for env in self.TRANSLATABLE_ENVIRONMENTS:
            text = self._extract_translatable_environment(text, env)

        text = self._chunk_paragraphs(text)

        return text

    # Backward-compatible alias for existing internal/external calls.
    def _extract_translatable_content(self, text: str) -> str:
        return self._extract_translatable_text(text)

    def _extract_translatable_environment(self, text: str, env: str) -> str:
        begin_pattern = re.compile(r"(\\begin\{" + re.escape(env) + r"\})")
        result = []
        pos = 0

        for match in begin_pattern.finditer(text):
            if match.start() < pos:
                continue
            result.append(text[pos : match.start()])
            begin_tag = match.group(1)
            start = match.end()
            env_count = 1
            i = start

            while i < len(text) and env_count > 0:
                if text[i:].startswith(r"\begin{" + env + "}"):
                    env_count += 1
                    i += len(r"\begin{" + env + "}")
                elif text[i:].startswith(r"\end{" + env + "}"):
                    env_count -= 1
                    if env_count == 0:
                        end_tag = r"\end{" + env + "}"
                        i += len(end_tag)
                        content = text[start : i - len(end_tag)]

                        if content.strip():
                            chunk_id = str(uuid.uuid4())
                            placeholder = f"{{{{CHUNK_{chunk_id}}}}}"
                            chunk = Chunk(
                                id=chunk_id,
                                content=content.strip(),
                                latex_wrapper="%s",
                                context=env,
                                preserved_elements={},
                            )
                            self.chunks.append(chunk)
                            result.append(f"{begin_tag}\n{placeholder}\n{end_tag}")
                        else:
                            result.append(match.group(0) + content + end_tag)
                        pos = i
                        break
                    else:
                        i += len(r"\end{" + env + "}")
                else:
                    i += 1
            else:
                result.append(match.group(0))
                pos = match.end()

        result.append(text[pos:])
        return "".join(result)

    def _create_chunk_for_pattern(
        self,
        text: str,
        pattern: re.Pattern,
        context: str,
        groups: tuple,
        content_group: int,
    ) -> str:
        def replacer(match):
            content = match.group(content_group)
            if not content.strip() or content.startswith("[["):
                return match.group(0)

            chunk_id = str(uuid.uuid4())
            placeholder = f"{{{{CHUNK_{chunk_id}}}}}"

            chunk = Chunk(
                id=chunk_id,
                content=content,
                latex_wrapper="%s",
                context=context,
                preserved_elements={},
            )
            self.chunks.append(chunk)

            parts = [match.group(g) for g in groups]
            parts[groups.index(content_group)] = placeholder
            return "".join(parts)

        return pattern.sub(replacer, text)

    def _create_chunk_for_env(
        self, text: str, pattern: re.Pattern, context: str
    ) -> str:
        def replacer(match):
            begin_tag = match.group(1)
            content = match.group(2)
            end_tag = match.group(3)

            if not content.strip():
                return match.group(0)

            chunk_id = str(uuid.uuid4())
            placeholder = f"{{{{CHUNK_{chunk_id}}}}}"

            chunk = Chunk(
                id=chunk_id,
                content=content.strip(),
                latex_wrapper="%s",
                context=context,
                preserved_elements={},
            )
            self.chunks.append(chunk)

            return f"{begin_tag}\n{placeholder}\n{end_tag}"

        return pattern.sub(replacer, text)

    def _chunk_paragraphs(self, text: str) -> str:
        lines = text.split("\n")
        result_lines = []
        current_para = []

        for line in lines:
            stripped = line.strip()

            if self._is_structural_line(stripped):
                if current_para:
                    para_text = "\n".join(current_para)
                    result_lines.append(self._maybe_chunk_paragraph(para_text))
                    current_para = []
                result_lines.append(line)
            elif stripped == "":
                if current_para:
                    para_text = "\n".join(current_para)
                    result_lines.append(self._maybe_chunk_paragraph(para_text))
                    current_para = []
                result_lines.append(line)
            else:
                current_para.append(line)

        if current_para:
            para_text = "\n".join(current_para)
            result_lines.append(self._maybe_chunk_paragraph(para_text))

        return "\n".join(result_lines)

    def _is_structural_line(self, line: str) -> bool:
        structural_patterns = [
            r"^\\begin\{",
            r"^\\end\{",
            r"^\\section",
            r"^\\subsection",
            r"^\\subsubsection",
            r"^\\paragraph",
            r"^\\subparagraph",
            r"^\\chapter",
            r"^\\part",
            r"^\\title",
            r"^\\author",
            r"^\\maketitle",
            r"^\\bibliographystyle",
            r"^\\bibliography",
            r"^\\tableofcontents",
            r"^\\listoffigures",
            r"^\\listoftables",
            r"^\\newpage",
            r"^\\clearpage",
            r"^\\balance",
            r"^%",
            r"^\s*\\item",
            r"^\s*\\caption",
            r"^\s*\\centering",
            r"^\s*\\label",
            r"^\s*\[",
            r"^\s*\]",
            r"^\\toprule",
            r"^\\midrule",
            r"^\\bottomrule",
            r"^\\hline",
            r"^\s*&",
            r"\\\\\s*$",
        ]
        for pattern in structural_patterns:
            if re.match(pattern, line):
                return True
        return False

    def _maybe_chunk_paragraph(self, para_text: str) -> str:
        if is_placeholder_only(para_text):
            return para_text

        text_content = para_text
        for placeholder in re.findall(r"\[\[[A-Z_]+_\d+\]\]", para_text):
            text_content = text_content.replace(placeholder, "")
        for placeholder in re.findall(r"\{\{CHUNK_[a-f0-9-]+\}\}", para_text):
            text_content = text_content.replace(placeholder, "")

        clean_text = re.sub(
            r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^}]*\})*", "", text_content
        )
        clean_text = re.sub(r"[{}\[\]\\]", "", clean_text)
        clean_text = clean_text.strip()

        if len(clean_text) < 20:
            return para_text

        chunk_id = str(uuid.uuid4())
        placeholder = f"{{{{CHUNK_{chunk_id}}}}}"

        chunk = Chunk(
            id=chunk_id,
            content=para_text.strip(),
            latex_wrapper="%s",
            context="paragraph",
            preserved_elements={},
        )
        self.chunks.append(chunk)

        return placeholder

    def _flatten_latex(self, content: str, base_dir: str) -> str:
        def replace_input(match):
            prefix = match.group(1)  # 保留前导字符（换行符或非%字符）
            filename = match.group(3)
            target_path = self._resolve_path(base_dir, filename)

            if target_path and os.path.exists(target_path):
                try:
                    with open(target_path, "r", encoding="utf-8") as f:
                        sub_content = f.read()
                    sub_dir = os.path.dirname(target_path)
                    return prefix + self._flatten_latex(sub_content, sub_dir)
                except Exception as e:
                    print(f"Warning: Could not read included file {target_path}: {e}")
                    return match.group(0)
            else:
                print(f"Warning: Included file not found: {filename} in {base_dir}")
                return match.group(0)

        pattern = re.compile(r"(^|[^%])\\(input|include)\{([^}]+)\}")
        return pattern.sub(replace_input, content)

    def _resolve_path(self, base_dir: str, filename: str) -> Optional[str]:
        candidates = [filename]
        if not filename.lower().endswith(".tex"):
            candidates.append(filename + ".tex")
        for cand in candidates:
            path = os.path.join(base_dir, cand)
            if os.path.exists(path):
                return path
        return None

    def _remove_comments(self, content: str) -> str:
        r"""精准删除LaTeX注释，保留必要的结构。

        规则：
        1. 删除整行注释（以%开头，前面只有空白）
        2. 删除行尾注释（%及其后内容，但保留转义的\%）
        3. 保留 %! 开头的编译器指令（如 %!TEX）
        4. 保留 verbatim/lstlisting 环境中的内容
        """
        lines = content.split("\n")
        result = []
        in_verbatim = False
        verbatim_envs = {"verbatim", "lstlisting", "minted", "comment"}

        for line in lines:
            # 检测 verbatim 环境的开始/结束
            for env in verbatim_envs:
                if f"\\begin{{{env}}}" in line:
                    in_verbatim = True
                if f"\\end{{{env}}}" in line:
                    in_verbatim = False

            # verbatim 环境内保持原样
            if in_verbatim:
                result.append(line)
                continue

            # 保留编译器指令（%!TEX, %!BIB 等）
            stripped = line.lstrip()
            if stripped.startswith("%!"):
                result.append(line)
                continue

            # 整行注释：跳过
            if stripped.startswith("%"):
                continue

            # 行尾注释：删除 % 及其后内容（但保留 \%）
            cleaned = re.sub(r"(?<!\\)%.*$", "", line)

            # 保留非空行或原本就是空行
            if cleaned.strip() or not line.strip():
                result.append(cleaned.rstrip())

        return "\n".join(result)

    def _split_preamble_body(self, content: str) -> Tuple[str, str]:
        match = re.search(r"\\begin\{document\}", content)
        if match:
            end_idx = match.end()
            preamble = content[:end_idx]
            body = content[end_idx:]
            return preamble, body
        return "", content
