import json
import re
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


def _levenshtein_distance(s1: str, s2: str) -> int:
    """计算两个字符串之间的 Levenshtein 编辑距离。"""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (0 if c1 == c2 else 1)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


def validate_translated_placeholders(
    translated_chunks: Dict[str, str],
    doc: "LaTeXDocument",
    valid_placeholders: Optional[Set[str]] = None,
) -> Tuple[Dict[str, str], List[Dict]]:
    """
    校验并自动修复 LLM 翻译文本中的占位符问题。

    - typo (编辑距离 ≤ 2): 自动替换为正确占位符
    - hallucination (编辑距离 > 2 或跨 chunk 引用): 从文本中删除
    - missing (源文本有但翻译中缺失): 仅记录警告，不修复

    返回: (修复后的 translated_chunks, 问题列表)
    """
    # 1. 构建有效占位符集合
    if valid_placeholders is None:
        valid_placeholders = set(doc.global_placeholders.keys())
        for chunk in doc.chunks:
            valid_placeholders.update(chunk.preserved_elements.keys())

    # 2. 白名单: 换行 token，跳过校验
    whitelist = {"[[SL]]", "[[PL]]", "[[SL_RAW]]", "[[PL_RAW]]"}

    # 3. 构建每个 chunk 源文本中的占位符映射
    ph_pattern = re.compile(r"\[\[[A-Z_]+_\d+\]\]")

    source_ph_map: Dict[str, Set[str]] = {}
    chunk_map: Dict[str, Chunk] = {}
    for chunk in doc.chunks:
        source_ph_map[chunk.id] = set(ph_pattern.findall(chunk.content))
        chunk_map[chunk.id] = chunk

    # 4. 逐 chunk 校验
    fixed_chunks: Dict[str, str] = {}
    issues: List[Dict] = []

    for chunk_id, translated_text in translated_chunks.items():
        trans_phs = set(ph_pattern.findall(translated_text))
        source_phs = source_ph_map.get(chunk_id, set())

        # 找出翻译中多出的占位符 (spurious)
        spurious = trans_phs - source_phs

        for bad_ph in spurious:
            # 跳过白名单
            if bad_ph in whitelist:
                continue

            if bad_ph in valid_placeholders:
                # 跨 chunk 引用 → hallucination，删除
                translated_text = translated_text.replace(bad_ph, "")
                issues.append(
                    {
                        "type": "hallucination",
                        "chunk_id": chunk_id,
                        "bad": bad_ph,
                        "fixed_to": None,
                    }
                )
            else:
                # 不在全局有效集合中 → 尝试编辑距离匹配
                best_match = None
                best_dist = float("inf")
                for src_ph in source_phs:
                    dist = _levenshtein_distance(bad_ph, src_ph)
                    if dist < best_dist:
                        best_dist = dist
                        best_match = src_ph

                if best_dist <= 2 and best_match is not None:
                    # typo → 自动修复
                    translated_text = translated_text.replace(bad_ph, best_match)
                    issues.append(
                        {
                            "type": "typo_fixed",
                            "chunk_id": chunk_id,
                            "bad": bad_ph,
                            "fixed_to": best_match,
                        }
                    )
                else:
                    # hallucination → 删除
                    translated_text = translated_text.replace(bad_ph, "")
                    issues.append(
                        {
                            "type": "hallucination",
                            "chunk_id": chunk_id,
                            "bad": bad_ph,
                            "fixed_to": None,
                        }
                    )

        # 找出源文本中有但翻译中缺失的占位符 (missing)
        # 需要在修复后重新扫描
        current_phs = set(ph_pattern.findall(translated_text))
        missing = source_phs - current_phs
        for miss_ph in missing:
            if miss_ph in whitelist:
                continue
            issues.append(
                {
                    "type": "missing",
                    "chunk_id": chunk_id,
                    "bad": miss_ph,
                    "fixed_to": None,
                }
            )

        # 5. 空文本回退
        if translated_text.strip() == "" and chunk_id in chunk_map:
            translated_text = chunk_map[chunk_id].content

        fixed_chunks[chunk_id] = translated_text

    return fixed_chunks, issues
