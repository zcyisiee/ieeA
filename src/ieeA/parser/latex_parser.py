import os
import re
import uuid
from typing import Optional, Tuple, List, Dict

from .structure import LaTeXDocument, Chunk


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
    }

    TRANSLATABLE_ENVIRONMENTS = {
        "abstract",
        "itemize",
        "enumerate",
        "description",
    }

    SECTION_COMMANDS = {
        "title",
        "section",
        "subsection",
        "subsubsection",
        "paragraph",
        "subparagraph",
        "chapter",
        "part",
        "caption",
    }

    def __init__(self):
        self.chunks: List[Chunk] = []
        self.protected_counter = 0

    def parse_file(self, filepath: str) -> LaTeXDocument:
        base_dir = os.path.dirname(os.path.abspath(filepath))
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        flattened_content = self._flatten_latex(content, base_dir)
        preamble, body_content = self._split_preamble_body(flattened_content)

        self.chunks = []
        self.protected_counter = 0

        preamble = self._extract_title_from_preamble(preamble)
        preamble = self._inject_chinese_support(preamble)

        body_template = self._process_body(body_content)

        return LaTeXDocument(
            preamble=preamble, chunks=self.chunks, body_template=body_template
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

    def _extract_title_from_preamble(self, preamble: str) -> str:
        """Extract title from preamble and create translatable chunk."""
        pattern = re.compile(r"(\\title\s*\{)([^}]+)(\})")

        def replacer(match):
            prefix, content, suffix = match.group(1), match.group(2), match.group(3)
            if not content.strip() or content.startswith("[["):
                return match.group(0)

            chunk_id = str(uuid.uuid4())
            placeholder = f"{{{{CHUNK_{chunk_id}}}}}"
            chunk = Chunk(
                id=chunk_id,
                content=content.strip(),
                latex_wrapper="%s",
                context="title",
                preserved_elements={},
            )
            self.chunks.append(chunk)
            return f"{prefix}{placeholder}{suffix}"

        return pattern.sub(replacer, preamble)

    def _extract_captions(self, text: str) -> str:
        """Extract caption content for translation before environment protection."""
        pattern = re.compile(r"(\\caption)(\*?)(\s*\[[^\]]*\])?\s*\{")
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
                if (
                    content.strip()
                    and not content.startswith("[[")
                    and not content.startswith("{{CHUNK_")
                    and len(content.strip()) > 10
                ):
                    chunk_id = str(uuid.uuid4())
                    placeholder = f"{{{{CHUNK_{chunk_id}}}}}"
                    chunk = Chunk(
                        id=chunk_id,
                        content=content.strip(),
                        latex_wrapper="%s",
                        context="caption",
                        preserved_elements={},
                    )
                    self.chunks.append(chunk)
                    optional_short = match.group(3) if match.group(3) else ""
                    # Build caption string without f-string brace escaping issues
                    caption_str = (
                        match.group(1)
                        + match.group(2)
                        + optional_short
                        + "{"
                        + placeholder
                        + "}"
                    )
                    result.append(caption_str)
                else:
                    result.append(match.group(0) + content + "}")
                pos = i
            else:
                result.append(match.group(0))
                pos = match.end()

        result.append(text[pos:])
        return "".join(result)

    def _process_body(self, body: str) -> str:
        result = body

        result = self._protect_author_block(result)
        result = self._extract_captions(result)
        result = self._protect_math_environments(result)
        result = self._protect_inline_math(result)
        result = self._protect_commands(result)
        result = self._extract_translatable_content(result)

        return result

    def _protect_math_environments(self, text: str) -> str:
        for env in self.PROTECTED_ENVIRONMENTS:
            pattern = re.compile(
                r"(\\begin\{"
                + re.escape(env)
                + r"\}.*?\\end\{"
                + re.escape(env)
                + r"\})",
                re.DOTALL,
            )
            text = self._replace_with_placeholder(text, pattern, "MATHENV")
        return text

    def _protect_inline_math(self, text: str) -> str:
        pattern = re.compile(r"(\$\$.*?\$\$|\$[^$]+?\$)", re.DOTALL)
        text = self._replace_with_placeholder(text, pattern, "MATH")

        pattern = re.compile(r"(\\\[.*?\\\]|\\\(.*?\\\))", re.DOTALL)
        text = self._replace_with_placeholder(text, pattern, "MATH")
        return text

    def _protect_commands(self, text: str) -> str:
        patterns = [
            (r"(\\cite\{[^}]*\})", "CITE"),
            (r"(\\ref\{[^}]*\})", "REF"),
            (r"(\\eqref\{[^}]*\})", "REF"),
            (r"(\\label\{[^}]*\})", "LABEL"),
            (r"(\\url\{[^}]*\})", "URL"),
            (r"(\\href\{[^}]*\}\{[^}]*\})", "HREF"),
            (r"(\\footnote\{[^}]*\})", "FOOTNOTE"),
            (r"(\\includegraphics(?:\[[^\]]*\])?\{[^}]*\})", "GRAPHICS"),
        ]
        for pattern_str, prefix in patterns:
            pattern = re.compile(pattern_str)
            text = self._replace_with_placeholder(text, pattern, prefix)
        return text

    def _replace_with_placeholder(
        self, text: str, pattern: re.Pattern, prefix: str
    ) -> str:
        def replacer(match):
            self.protected_counter += 1
            placeholder = f"[[{prefix}_{self.protected_counter}]]"
            chunk_id = str(uuid.uuid4())
            chunk = Chunk(
                id=chunk_id,
                content=placeholder,
                latex_wrapper="%s",
                context="protected",
                preserved_elements={placeholder: match.group(1)},
            )
            self.chunks.append(chunk)
            return placeholder

        return pattern.sub(replacer, text)

    def _extract_translatable_content(self, text: str) -> str:
        for cmd in self.SECTION_COMMANDS:
            pattern = re.compile(r"(\\" + cmd + r")(\*?)(\{)([^}]+)(\})")
            text = self._create_chunk_for_pattern(
                text, pattern, cmd, groups=(1, 2, 3, 4, 5), content_group=4
            )

        for env in self.TRANSLATABLE_ENVIRONMENTS:
            pattern = re.compile(
                r"(\\begin\{" + env + r"\})(.*?)(\\end\{" + env + r"\})", re.DOTALL
            )
            text = self._create_chunk_for_env(text, pattern, env)

        text = self._chunk_paragraphs(text)

        return text

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
            filename = match.group(3)
            target_path = self._resolve_path(base_dir, filename)

            if target_path and os.path.exists(target_path):
                try:
                    with open(target_path, "r", encoding="utf-8") as f:
                        sub_content = f.read()
                    sub_dir = os.path.dirname(target_path)
                    return self._flatten_latex(sub_content, sub_dir)
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

    def _split_preamble_body(self, content: str) -> Tuple[str, str]:
        match = re.search(r"\\begin\{document\}", content)
        if match:
            end_idx = match.end()
            preamble = content[:end_idx]
            body = content[end_idx:]
            return preamble, body
        return "", content
