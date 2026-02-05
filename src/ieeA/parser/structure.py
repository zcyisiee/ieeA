from dataclasses import dataclass, field
from typing import Dict, List, Optional
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

    def reconstruct(self, translated_chunks: Optional[Dict[str, str]] = None) -> str:
        """
        Reconstructs the full document.

        Args:
            translated_chunks: Dict mapping chunk ID to translated text.

        Reconstruction order (critical for nested structures):
        1. Restore global_placeholders (exposes {{CHUNK_...}} inside protected envs)
        2. Replace {{CHUNK_...}} with translated content
        3. Restore chunk.preserved_elements
        4. Restore global_placeholders AGAIN (for [[MATH_n]] etc inside chunks)
        """
        preamble_result = self.preamble
        body_result = self.body_template if self.body_template else ""

        full_result = preamble_result + body_result

        # Step 1: Restore global placeholders FIRST
        # This exposes any {{CHUNK_...}} that were inside protected environments
        # (e.g., caption inside algorithm: [[MATHENV_1]] contains {{CHUNK_abc}})
        max_iterations = 10
        for _ in range(max_iterations):
            replacements_made = False
            for placeholder, original in self.global_placeholders.items():
                if placeholder in full_result:
                    full_result = full_result.replace(placeholder, original)
                    replacements_made = True
            if not replacements_made:
                break

        # Step 2: Replace {{CHUNK_...}} with translated content
        # Now chunks that were inside protected envs are visible and can be translated
        for chunk in self.chunks:
            placeholder = f"{{{{CHUNK_{chunk.id}}}}}"
            if placeholder in full_result:
                trans_text = (
                    translated_chunks.get(chunk.id) if translated_chunks else None
                )
                reconstructed = chunk.reconstruct(trans_text)
                full_result = full_result.replace(placeholder, reconstructed)

        # Step 3: Restore chunk.preserved_elements (e.g., [[AUTHOR_1]])
        for chunk in self.chunks:
            for placeholder, original in chunk.preserved_elements.items():
                full_result = full_result.replace(placeholder, original)

        # Step 4: Restore global placeholders AGAIN
        # Chunk content may contain [[MATH_n]], [[CITE_n]] etc that need restoration
        for _ in range(max_iterations):
            replacements_made = False
            for placeholder, original in self.global_placeholders.items():
                if placeholder in full_result:
                    full_result = full_result.replace(placeholder, original)
                    replacements_made = True
            if not replacements_made:
                break

        return full_result
