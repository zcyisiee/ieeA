import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union
import uuid


@dataclass
class Chunk:
    """
    Represents a translatable unit of text from a LaTeX document.
    """

    id: str
    content: str
    # Format string to wrap the translated content back into LaTeX
    # e.g., "\section{%s}" or just "%s" for plain text
    latex_wrapper: str = "%s"
    context: str = ""  # e.g. "abstract", "section_title", "paragraph"
    # Map of placeholders (e.g., "[[MATH_0]]") to original LaTeX content
    preserved_elements: Dict[str, str] = field(default_factory=dict)

    def reconstruct(self, translated_text: Optional[str] = None) -> str:
        """
        Reconstructs the chunk with translated text or original content,
        restoring preserved elements.
        """
        text = translated_text if translated_text is not None else self.content

        # Restore preserved elements
        # We need to be careful about order if nested, but usually they are flat per chunk
        # If text is translated, the placeholders should still be there.
        result = text
        for placeholder, original in self.preserved_elements.items():
            result = result.replace(placeholder, original)

        return self.latex_wrapper % result


@dataclass
class LaTeXDocument:
    """
    Represents a parsed LaTeX document.
    """

    preamble: str
    chunks: List[Chunk]
    body_template: str = ""
    abstract: Optional[str] = None
    # Map of global placeholders (e.g., "[[CITE_1]]") to original LaTeX content
    # These are stored at document level as they don't belong to any specific chunk
    global_placeholders: Dict[str, str] = field(default_factory=dict)

    def _reconstruct_internal(
        self,
        translated_chunks: Optional[Dict[str, str]] = None,
        collect_chunk_start_lines: bool = False,
    ) -> Tuple[str, Dict[str, int]]:
        preamble_result = self.preamble
        body_result = self.body_template if self.body_template else ""
        chunk_start_lines: Dict[str, int] = {}

        full_result = preamble_result + body_result

        max_iterations = 10
        for _ in range(max_iterations):
            replacements_made = False
            for placeholder, original in self.global_placeholders.items():
                if placeholder in full_result:
                    full_result = full_result.replace(placeholder, original)
                    replacements_made = True
            if not replacements_made:
                break

        for chunk in self.chunks:
            placeholder = f"{{{{CHUNK_{chunk.id}}}}}"
            if placeholder in full_result:
                trans_text = (
                    translated_chunks.get(chunk.id) if translated_chunks else None
                )
                reconstructed = chunk.reconstruct(trans_text)
                if collect_chunk_start_lines:
                    start_marker = f"__IEEA_CHUNK_START_{chunk.id}__"
                    end_marker = f"__IEEA_CHUNK_END_{chunk.id}__"
                    reconstructed = f"{start_marker}{reconstructed}{end_marker}"
                full_result = full_result.replace(placeholder, reconstructed)

        for chunk in self.chunks:
            for placeholder, original in chunk.preserved_elements.items():
                full_result = full_result.replace(placeholder, original)

        for _ in range(max_iterations):
            replacements_made = False
            for placeholder, original in self.global_placeholders.items():
                if placeholder in full_result:
                    full_result = full_result.replace(placeholder, original)
                    replacements_made = True
            if not replacements_made:
                break

        if collect_chunk_start_lines:
            for chunk in self.chunks:
                start_marker = f"__IEEA_CHUNK_START_{chunk.id}__"
                end_marker = f"__IEEA_CHUNK_END_{chunk.id}__"
                marker_index = full_result.find(start_marker)
                if marker_index == -1:
                    continue
                content_start = marker_index + len(start_marker)
                chunk_start_lines[chunk.id] = (
                    full_result.count("\n", 0, content_start) + 1
                )
                full_result = full_result.replace(start_marker, "", 1)
                full_result = full_result.replace(end_marker, "", 1)

        return full_result, chunk_start_lines

    def reconstruct(self, translated_chunks: Optional[Dict[str, str]] = None) -> str:
        full_result, _ = self._reconstruct_internal(
            translated_chunks=translated_chunks,
            collect_chunk_start_lines=False,
        )
        return full_result

    def reconstruct_with_chunk_start_lines(
        self, translated_chunks: Optional[Dict[str, str]] = None
    ) -> Tuple[str, Dict[str, int]]:
        return self._reconstruct_internal(
            translated_chunks=translated_chunks,
            collect_chunk_start_lines=True,
        )

    def save_parser_state(self, filepath: Union[str, Path]) -> None:
        """将完整的 parser 状态序列化为 JSON 文件。"""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        state = {
            "version": "1.0",
            "global_placeholders": self.global_placeholders,
            "chunks": [
                {
                    "id": chunk.id,
                    "content": chunk.content,
                    "context": chunk.context,
                    "latex_wrapper": chunk.latex_wrapper,
                    "preserved_elements": chunk.preserved_elements,
                }
                for chunk in self.chunks
            ],
            "all_valid_placeholders": sorted(
                set(
                    list(self.global_placeholders.keys())
                    + [
                        ph
                        for chunk in self.chunks
                        for ph in chunk.preserved_elements.keys()
                    ]
                )
            ),
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    @classmethod
    def load_valid_placeholders(cls, filepath: Union[str, Path]) -> Set[str]:
        """从 JSON 文件加载所有有效的占位符集合。"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data["all_valid_placeholders"])
