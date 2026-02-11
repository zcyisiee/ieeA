import re
from typing import List, Tuple, Set, Dict, Any, Optional


class BuiltInRules:
    @staticmethod
    def _is_escaped_brace(text: str, index: int) -> bool:
        backslash_count = 0
        cursor = index - 1
        while cursor >= 0 and text[cursor] == "\\":
            backslash_count += 1
            cursor -= 1
        return backslash_count % 2 == 1

    @staticmethod
    def _brace_text_tokens(text: str) -> List[Tuple[str, int]]:
        tokens: List[Tuple[str, int]] = []
        in_text = False
        text_start = 0

        for idx, char in enumerate(text):
            if char in "{}" and not BuiltInRules._is_escaped_brace(text, idx):
                if in_text:
                    tokens.append(("T", text_start))
                    in_text = False
                tokens.append((char, idx))
            else:
                if not in_text:
                    in_text = True
                    text_start = idx

        if in_text:
            tokens.append(("T", text_start))

        return tokens

    @staticmethod
    def _line_col_from_offset(text: str, offset: int) -> Tuple[int, int, str]:
        if not text:
            return 1, 1, ""

        bounded_offset = max(0, min(offset, len(text)))
        line_no = text.count("\n", 0, bounded_offset) + 1
        line_start = text.rfind("\n", 0, bounded_offset) + 1
        line_end = text.find("\n", bounded_offset)
        if line_end == -1:
            line_end = len(text)
        line_text = text[line_start:line_end]
        col_no = bounded_offset - line_start + 1
        return line_no, col_no, line_text

    @staticmethod
    def _line_snippet_with_pointer(
        line_text: str,
        col_no: int,
        window: int = 30,
    ) -> Tuple[str, int]:
        if not line_text:
            return "", 1

        bounded_col = max(1, min(col_no, len(line_text)))
        center = bounded_col - 1
        start = max(0, center - window)
        end = min(len(line_text), center + window + 1)

        snippet = line_text[start:end]
        pointer_pos = (center - start) + 1

        if start > 0:
            snippet = f"...{snippet}"
            pointer_pos += 3
        if end < len(line_text):
            snippet = f"{snippet}..."

        return snippet, pointer_pos

    @staticmethod
    def _find_first_brace_structure_mismatch(
        source: str,
        translation: str,
    ) -> Optional[Dict[str, Any]]:
        source_tokens = BuiltInRules._brace_text_tokens(source)
        translation_tokens = BuiltInRules._brace_text_tokens(translation)

        idx = 0
        min_len = min(len(source_tokens), len(translation_tokens))
        while idx < min_len and source_tokens[idx][0] == translation_tokens[idx][0]:
            idx += 1

        if idx == len(source_tokens) and idx == len(translation_tokens):
            return None

        source_kind = source_tokens[idx][0] if idx < len(source_tokens) else "<EOF>"
        translation_kind = (
            translation_tokens[idx][0] if idx < len(translation_tokens) else "<EOF>"
        )

        source_offset = (
            source_tokens[idx][1] if idx < len(source_tokens) else len(source)
        )
        translation_offset = (
            translation_tokens[idx][1]
            if idx < len(translation_tokens)
            else len(translation)
        )

        return {
            "source_kind": source_kind,
            "translation_kind": translation_kind,
            "source_offset": source_offset,
            "translation_offset": translation_offset,
        }

    @staticmethod
    def _format_chunk_structure_mismatch(
        source: str,
        translation: str,
        source_offset: int,
        translation_offset: int,
        source_chunk_start_line: int,
        translation_chunk_start_line: int,
    ) -> str:
        source_local_line, source_col, source_line_text = (
            BuiltInRules._line_col_from_offset(source, source_offset)
        )
        translation_local_line, translation_col, translation_line_text = (
            BuiltInRules._line_col_from_offset(translation, translation_offset)
        )

        source_global_line = source_chunk_start_line + source_local_line - 1
        translation_global_line = (
            translation_chunk_start_line + translation_local_line - 1
        )

        source_snippet, _ = BuiltInRules._line_snippet_with_pointer(
            source_line_text, source_col
        )
        translation_snippet, translation_pointer_pos = (
            BuiltInRules._line_snippet_with_pointer(
                translation_line_text, translation_col
            )
        )

        translation_prefix = f"translation: {translation_global_line}行: "
        pointer_line = (
            " " * (len(translation_prefix) + translation_pointer_pos - 1) + "⬆️"
        )

        return (
            f"source: {source_global_line}行: {source_snippet}\n"
            f"translation: {translation_global_line}行: {translation_snippet}\n"
            f"{pointer_line}"
        )

    @staticmethod
    def check_chunk_brace_structure(
        translated_chunks: List[Any],
        source_chunk_start_lines: Dict[str, int],
        translation_chunk_start_lines: Dict[str, int],
    ) -> List[str]:
        errors: List[str] = []

        for chunk in translated_chunks:
            chunk_id = getattr(chunk, "chunk_id", None)
            source = getattr(chunk, "source", None)
            translation = getattr(chunk, "translation", None)

            if not isinstance(chunk_id, str):
                continue
            if not isinstance(source, str) or not isinstance(translation, str):
                continue

            mismatch = BuiltInRules._find_first_brace_structure_mismatch(
                source, translation
            )
            if mismatch is None:
                continue

            source_start_line = source_chunk_start_lines.get(chunk_id, 1)
            translation_start_line = translation_chunk_start_lines.get(chunk_id, 1)
            detail = BuiltInRules._format_chunk_structure_mismatch(
                source=source,
                translation=translation,
                source_offset=mismatch["source_offset"],
                translation_offset=mismatch["translation_offset"],
                source_chunk_start_line=source_start_line,
                translation_chunk_start_line=translation_start_line,
            )

            errors.append(
                "Chunk brace structure mismatch "
                f"(chunk_id={chunk_id}, source_token={mismatch['source_kind']}, "
                f"translation_token={mismatch['translation_kind']}):\n{detail}"
            )

        return errors

    @staticmethod
    def check_braces(text: str) -> List[str]:
        """Check for balanced braces and brackets."""
        stack = []
        errors = []
        mapping = {"]": "[", "}": "{"}

        i = 0
        while i < len(text):
            char = text[i]

            if char == "\\":
                if i + 1 < len(text):
                    next_char = text[i + 1]
                    if next_char in "{}":
                        i += 2
                        continue
                    elif next_char == "\\":
                        i += 2
                        continue
                    else:
                        i += 1
                        while i < len(text) and text[i].isalpha():
                            i += 1
                        continue
                else:
                    i += 1
                    continue

            if char in "{[":
                stack.append((char, i))
            elif char in "}]":
                if not stack:
                    errors.append(f"Unmatched closing brace '{char}' at position {i}")
                else:
                    last_open, _ = stack.pop()
                    if mapping[char] != last_open:
                        errors.append(
                            f"Mismatched brace '{char}' at {i}, expected closing for '{last_open}'"
                        )

            i += 1

        if stack:
            for char, pos in stack:
                errors.append(f"Unmatched opening brace '{char}' at position {pos}")

        return errors

    @staticmethod
    def extract_commands(text: str, command: str) -> Set[str]:
        r"""Extract contents of a specific LaTeX command, e.g., \cite{...}."""
        # This regex matches \command{content} and handles simple nesting if needed,
        # but for IDs usually it's simple.
        # Using a simpler regex for now: \\command\{([^}]+)\}
        pattern = f"\\\\{command}\\{{([^}}]+)\\}}"
        return set(re.findall(pattern, text))

    @staticmethod
    def check_citations(original: str, translated: str) -> List[str]:
        """Ensure all citations in original exist in translated."""
        orig_cites = BuiltInRules.extract_commands(original, "cite")
        trans_cites = BuiltInRules.extract_commands(translated, "cite")

        errors = []
        missing = orig_cites - trans_cites
        extra = trans_cites - orig_cites

        if missing:
            errors.append(f"Missing citations: {', '.join(missing)}")
        if extra:
            errors.append(f"Unexpected citations: {', '.join(extra)}")

        return errors

    @staticmethod
    def check_references(original: str, translated: str) -> List[str]:
        """Ensure all refs in original exist in translated."""
        orig_refs = BuiltInRules.extract_commands(original, "ref")
        trans_refs = BuiltInRules.extract_commands(translated, "ref")

        errors = []
        missing = orig_refs - trans_refs
        # Extra refs might be okay if added by translator for clarity, but usually not.
        if missing:
            errors.append(f"Missing references: {', '.join(missing)}")

        return errors

    @staticmethod
    def check_math_environments(original: str, translated: str) -> List[str]:
        """Check if math delimiters are preserved."""
        # Simple check for counts of $ and $$
        # A more robust check would parse, but this catches obvious errors.
        errors = []

        # Remove placeholders [[...]] before counting
        orig_cleaned = re.sub(r"\[\[[A-Z_]+_\d+\]\]", "", original)
        trans_cleaned = re.sub(r"\[\[[A-Z_]+_\d+\]\]", "", translated)

        # Remove escaped dollar signs \$ before counting
        orig_cleaned = orig_cleaned.replace(r"\$", "")
        trans_cleaned = trans_cleaned.replace(r"\$", "")

        orig_inline = orig_cleaned.count("$")
        trans_inline = trans_cleaned.count("$")

        # We expect even numbers of $ usually
        if trans_inline % 2 != 0:
            errors.append("Odd number of '$' delimiters in translated text.")

        # We might expect the same number of math blocks, but sometimes they get merged/split?
        # Strictly speaking they should match if text structure is preserved.
        if orig_inline != trans_inline:
            errors.append(
                f"Math delimiter count mismatch: Original {orig_inline}, Translated {trans_inline}"
            )

        return errors

    @staticmethod
    def check_length_ratio(original: str, translated: str) -> List[str]:
        """Check if translation length is within reasonable bounds (Chinese vs English)."""
        # Heuristic: Chinese usually 0.6-0.8 of English characters
        if not original.strip():
            return []

        len_orig = len(original)
        len_trans = len(translated)

        ratio = len_trans / len_orig if len_orig > 0 else 0

        # These bounds are heuristics and might need tuning
        if ratio < 0.2:
            return [f"Translation suspiciously short (Ratio: {ratio:.2f})"]
        if ratio > 1.5:
            return [f"Translation suspiciously long (Ratio: {ratio:.2f})"]

        return []
