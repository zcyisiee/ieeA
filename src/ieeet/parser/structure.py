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
    
    def reconstruct(self, translated_chunks: Optional[Dict[str, str]] = None) -> str:
        """
        Reconstructs the full document.
        
        Args:
            translated_chunks: Dict mapping chunk ID to translated text.
        """
        body_parts = []
        for chunk in self.chunks:
            trans_text = translated_chunks.get(chunk.id) if translated_chunks else None
            body_parts.append(chunk.reconstruct(trans_text))
            
        return self.preamble + "".join(body_parts)
