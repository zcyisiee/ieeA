import os
import re
from typing import Optional, Tuple, List

from pylatexenc.latexwalker import LatexWalker, LatexNode, LatexEnvironmentNode, get_default_latex_context_db

from .structure import LaTeXDocument
from .chunker import LatexChunker

class LaTeXParser:
    """
    Parses LaTeX files into a structured LaTeXDocument.
    Handles file reading, import flattening, and chunking.
    """
    
    def __init__(self):
        self.chunker = LatexChunker()

    def parse_file(self, filepath: str) -> LaTeXDocument:
        """
        Parses a LaTeX file and its imports.
        """
        base_dir = os.path.dirname(os.path.abspath(filepath))
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Flatten imports recursively
        flattened_content = self._flatten_latex(content, base_dir)
        
        # Split Preamble and Body
        preamble, body_content = self._split_preamble_body(flattened_content)
        
        # Parse Body
        walker = LatexWalker(body_content, latex_context=get_default_latex_context_db())
        try:
            nodes, _, _ = walker.get_latex_nodes()
        except Exception as e:
            # Fallback or error handling
            # Pylatexenc is quite robust, but unclosed groups can cause issues.
            raise ValueError(f"Failed to parse LaTeX content: {e}")
        
        # Chunk the nodes
        chunks = self.chunker.chunk_nodes(nodes)
        
        return LaTeXDocument(preamble=preamble, chunks=chunks)

    def _flatten_latex(self, content: str, base_dir: str) -> str:
        """
        Recursively resolves \input{} and \include{} commands.
        """
        # Simple regex-based flattener. 
        # Note: parsing AST for input is safer but harder to reconstruct perfectly 
        # without specialized tools. Regex is standard for this simple task.
        # We need to handle comments to avoid processing commented-out inputs.
        
        def replace_input(match):
            command = match.group(2)
            filename = match.group(3)
            
            # Helper to find the file
            target_path = self._resolve_path(base_dir, filename)
            
            if target_path and os.path.exists(target_path):
                try:
                    with open(target_path, 'r', encoding='utf-8') as f:
                        sub_content = f.read()
                    # Recursively flatten
                    sub_dir = os.path.dirname(target_path)
                    return self._flatten_latex(sub_content, sub_dir)
                except Exception as e:
                    print(f"Warning: Could not read included file {target_path}: {e}")
                    return match.group(0) # Return original
            else:
                print(f"Warning: Included file not found: {filename} in {base_dir}")
                return match.group(0)

        # Regex for \input{filename} or \include{filename}
        # Ignoring commented lines is tricky with just sub, so we might process the whole file line by line
        # or use a regex that handles comments?
        # Let's try to remove comments first? No, we need to preserve them.
        
        # Improved Regex: match input/include but NOT if preceded by %
        # (This is a heuristic, perfectly stripping comments requires parsing)
        # Pattern: (Start of line OR non-%) \ (input|include) { (filename) }
        pattern = re.compile(r'(^|[^%])\\(input|include)\{([^}]+)\}')
        
        # We assume content is reasonably well-formed.
        # This will run recursively.
        
        # Since python's re module doesn't support overlapping matches well with lookbehind for variable length,
        # we iterate.
        
        new_content = content
        # We need to loop because one replacement might introduce new inputs (though distinct spots)
        # But actually sub handles all non-overlapping occurrences. 
        # Recursion is handled inside replace_input.
        
        new_content = pattern.sub(replace_input, content)
        
        return new_content

    def _resolve_path(self, base_dir: str, filename: str) -> Optional[str]:
        # Handle extensions. \input often omits .tex
        candidates = [filename]
        if not filename.lower().endswith('.tex'):
            candidates.append(filename + '.tex')
            
        for cand in candidates:
            path = os.path.join(base_dir, cand)
            if os.path.exists(path):
                return path
        return None

    def _split_preamble_body(self, content: str) -> Tuple[str, str]:
        """
        Splits content into preamble (up to \begin{document}) and body.
        Includes \begin{document} in the body or preamble?
        Usually preamble ends before \begin{document}.
        But we need to preserve \begin{document} for the final reconstruction.
        
        Let's put \begin{document} in the PREAMBLE to keep it safe.
        And \end{document} in the BODY (it will be parsed as an environment end).
        
        Wait, if we pass body to LatexWalker, and it starts with content, that's fine.
        If we put \begin{document} in preamble, the walker sees the inside.
        
        Better:
        Preamble = everything up to \begin{document} (inclusive).
        Body = everything after.
        
        But LatexWalker usually parses environments. If we chop off \begin{document}, 
        we have an unclosed environment potentially? 
        LatexWalker handles fragments fine.
        """
        
        match = re.search(r'\\begin\{document\}', content)
        if match:
            end_idx = match.end()
            preamble = content[:end_idx]
            body = content[end_idx:]
            return preamble, body
        else:
            # No document env found? Just return empty preamble and full content
            return "", content
