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

    def reconstruct(self, translated_chunks: Optional[Dict[str, str]] = None) -> str:
        """
        Reconstructs the full document.

        Args:
            translated_chunks: Dict mapping chunk ID to translated text.
        """
        preamble_result = self.preamble

        for chunk in self.chunks:
            placeholder = f"{{{{CHUNK_{chunk.id}}}}}"
            if placeholder in preamble_result:
                trans_text = (
                    translated_chunks.get(chunk.id) if translated_chunks else None
                )
                reconstructed = chunk.reconstruct(trans_text)
                preamble_result = preamble_result.replace(placeholder, reconstructed)

        if self.body_template:
            result = self.body_template

            for chunk in self.chunks:
                placeholder = f"{{{{CHUNK_{chunk.id}}}}}"
                if placeholder in result:
                    trans_text = (
                        translated_chunks.get(chunk.id) if translated_chunks else None
                    )
                    reconstructed = chunk.reconstruct(trans_text)
                    result = result.replace(placeholder, reconstructed)

            for chunk in self.chunks:
                for placeholder, original in chunk.preserved_elements.items():
                    result = result.replace(placeholder, original)

            return preamble_result + result

        body_parts = []
        for chunk in self.chunks:
            trans_text = translated_chunks.get(chunk.id) if translated_chunks else None
            body_parts.append(chunk.reconstruct(trans_text))

        return preamble_result + "".join(body_parts)
