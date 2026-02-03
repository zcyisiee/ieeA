import re
import uuid
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass, field

from pylatexenc.latexwalker import (
    LatexWalker,
    LatexNode,
    LatexCharsNode,
    LatexGroupNode,
    LatexCommentNode,
    LatexMacroNode,
    LatexEnvironmentNode,
    LatexMathNode,
)

from .structure import Chunk

class LatexChunker:
    """
    Splits LaTeX content into translatable Chunks.
    """
    
    # Macros that should be treated as structural dividers/containers for text
    # The content inside these arguments is translatable.
    SECTION_MACROS = {
        'section', 'subsection', 'subsubsection', 'paragraph', 'subparagraph',
        'chapter', 'part', 'caption', 'title', 'abstract'
    }
    
    # Macros that are part of the text flow and should be protected (treated as opaque placeholders)
    # or preserved as-is.
    INLINE_PROTECTED_MACROS = {
        'cite', 'ref', 'eqref', 'label', 'url', 'href', 'code'
    }

    def __init__(self):
        self.chunks: List[Chunk] = []
        self.current_chunk_text: List[str] = []
        self.current_preserved: Dict[str, str] = {}
        self.math_counter = 0
        self.protected_counter = 0

    def chunk_nodes(self, nodes: List[LatexNode]) -> List[Chunk]:
        """
        Main entry point to chunk a list of LaTeX nodes.
        """
        self.chunks = []
        self._reset_accumulator()
        
        self._process_nodes(nodes)
        
        # Flush any remaining text
        self._flush_chunk()
        
        return self.chunks

    def _reset_accumulator(self):
        self.current_chunk_text = []
        self.current_preserved = {}

    def _flush_chunk(self):
        text = "".join(self.current_chunk_text).strip()
        if not text:
            return

        chunk_id = str(uuid.uuid4())
        chunk = Chunk(
            id=chunk_id,
            content=text,
            preserved_elements=self.current_preserved.copy(),
            latex_wrapper="%s",
            context="paragraph"
        )
        self.chunks.append(chunk)
        self._reset_accumulator()

    def _process_nodes(self, nodes: List[LatexNode]):
        for node in nodes:
            if isinstance(node, LatexCharsNode):
                self._handle_chars(node)
            elif isinstance(node, LatexCommentNode):
                # We skip comments for translation purposes, usually.
                # Or we could preserve them. For now, let's just append a newline if needed
                # to maintain some spacing, but usually comments are stripped.
                self.current_chunk_text.append(node.latex_verbatim())
            elif isinstance(node, LatexMathNode):
                self._handle_protected_element(node.latex_verbatim(), "MATH")
            elif isinstance(node, LatexMacroNode):
                self._handle_macro(node)
            elif isinstance(node, LatexEnvironmentNode):
                self._handle_environment(node)
            elif isinstance(node, LatexGroupNode):
                # Groups like {...} usually just contain content to be processed
                self._process_nodes(node.nodelist)
            else:
                # Fallback for unknown nodes
                if hasattr(node, 'latex_verbatim'):
                    self.current_chunk_text.append(node.latex_verbatim())

    def _handle_chars(self, node: LatexCharsNode):
        text = node.chars
        # Check for paragraph breaks (double newlines)
        # We want to split chunks on paragraph breaks.
        if '\n\n' in text:
            parts = re.split(r'(\n\s*\n)', text)
            for i, part in enumerate(parts):
                if i % 2 == 1: # This is the separator (newlines)
                    # Flush the current chunk
                    self._flush_chunk()
                    # Add the separator to the new chunk (or ignore, but spacing helps)
                    # actually, we probably want to start fresh.
                    # but if we are reconstructing, we might lose the newlines if we don't store them.
                    # For simplicity, we don't translate newlines.
                    pass 
                else:
                    if part.strip():
                        self.current_chunk_text.append(part)
        else:
            self.current_chunk_text.append(text)

    def _handle_macro(self, node: LatexMacroNode):
        name = node.macroname
        
        if name in self.SECTION_MACROS:
            # It's a section title or similar.
            # Flush current paragraph first.
            self._flush_chunk()
            
            # Extract arguments. Usually the first argument is the title.
            # We want to translate the argument content.
            # This is tricky because arguments can contain nodes.
            # We will try to extract the content of the arguments.
            
            # Simple assumption: The LAST argument is the translatable text (e.g. \section[opt]{Title}).
            if node.nodeargd and node.nodeargd.argnlist:
                # Verify if it's a standard section command which usually has {title} as arg
                # Some might be \section*{title}
                
                # We construct a specific chunk for this section title
                # We need to process the nodes INSIDE the argument
                # Use the last argument as it's typically the body/title
                target_arg = node.nodeargd.argnlist[-1]
                arg_nodes = target_arg.nodelist if target_arg else []
                
                # Create a temporary chunker for the title
                sub_chunker = LatexChunker()
                sub_chunks = sub_chunker.chunk_nodes(arg_nodes)
                
                # If the title was simple text, we get one chunk. 
                # If it had math/refs, we get a chunk with placeholders.
                
                # We assume titles are single chunks for now.
                # If multiple chunks (e.g. title with paragraph break??), join them? 
                # Titles shouldn't have paragraph breaks.
                
                full_content = ""
                combined_preserved = {}
                
                for sc in sub_chunks:
                    full_content += sc.content
                    combined_preserved.update(sc.preserved_elements)
                
                # Reconstruct the wrapper.
                # e.g. \section{...}
                # We need to know the macro structure. 
                # A safe bet is to regenerate the macro with a string placeholder.
                # But pylatexenc doesn't easily give us "macro without arg 1".
                
                wrapper = f"\\{name}{{%s}}"
                # Handle stars e.g. \section*
                # pylatexenc might treat * as an 'macro_post_space' or separate char? 
                # Actually pylatexenc handles * as part of macro name if configured? 
                # Standard LatexWalker parses \section* as macro 'section' followed by char '*'. 
                # Check how pylatexenc handles \section*. 
                # It usually sees it as Macro 'section' and then '*' Char. 
                # Unless we define a spec.
                
                # For robustness, let's just grab the VERBATIM of the macro 
                # and replace the argument content with %s.
                verbatim = node.latex_verbatim()
                
                # This is risky if arguments are complex.
                # Alternative: Explicitly construct "\name{...}"
                # If we are strictly processing specific macros:
                
                chunk_id = str(uuid.uuid4())
                chunk = Chunk(
                    id=chunk_id,
                    content=full_content,
                    latex_wrapper=wrapper,
                    context=name,
                    preserved_elements=combined_preserved
                )
                self.chunks.append(chunk)
                
            else:
                # Macro without args? Just protect it.
                self._handle_protected_element(node.latex_verbatim(), "MACRO")

        elif name in self.INLINE_PROTECTED_MACROS:
             self._handle_protected_element(node.latex_verbatim(), "REF")
        
        else:
            # Unknown macro.
            # If it has arguments, we might want to process them or protect the whole thing.
            # Safest for translation: Protect the whole thing if we don't know it.
            # BUT, things like \textbf{}, \textit{} MUST be processed recursively.
            
            # Common formatting macros
            if name in ['textbf', 'textit', 'emph', 'underline', 'item']:
                # Treat as part of text flow, but recurse into arguments.
                # For \item, it's structural-ish but often appears in lists.
                
                if node.nodeargd and node.nodeargd.argnlist:
                     # Reconstruct the macro opening
                     # This is getting complex to reconstruct perfectly.
                     # Simplification: Treat \textbf{...} as text content if possible.
                     # Ideally: "This is \textbf{bold} text" -> content: "This is **bold** text" (markdown)
                     # But we stick to LaTeX.
                     # "This is \textbf{bold} text" -> content: "This is \textbf{bold} text"
                     # The Translator needs to handle Latex markup.
                     
                     # Decision: For formatting macros, include them VERBATIM in the chunk content.
                     # The LLM knows how to handle \textbf{...}.
                     self.current_chunk_text.append(node.latex_verbatim())
                else:
                    self.current_chunk_text.append(node.latex_verbatim())
            else:
                # Default: protect
                self._handle_protected_element(node.latex_verbatim(), "MACRO")

    def _handle_environment(self, node: LatexEnvironmentNode):
        name = node.environmentname
        if name in ['equation', 'align', 'gather', 'split', 'eqnarray']:
            self._handle_protected_element(node.latex_verbatim(), "MATH_ENV")
        elif name == 'document':
             self._process_nodes(node.nodelist)
        elif name in ['itemize', 'enumerate', 'description']:
             # These contain \item macros. We just recurse.
             # The \item handling in _handle_macro needs to be careful not to consume the whole list.
             # Actually \item is usually a MacroNode.
             # We should probably process the content of the list.
             self._process_nodes(node.nodelist)
        elif name in ['abstract']:
             # Abstract is like a section.
             # We might want to chunk it.
             self._flush_chunk()
             self._process_nodes(node.nodelist)
        else:
            # Unknown environment. Protect? Recurse?
            # If it contains text (like 'quote', 'center'), recurse.
            # If it's a figure/table, we might want to protect it or extract caption.
            if name in ['figure', 'table']:
                 # We want to extract captions.
                 # The content of the figure (graphics) is ignored/protected.
                 # We iterate children.
                 for child in node.nodelist:
                     if isinstance(child, LatexMacroNode) and child.macroname == 'caption':
                         self._handle_macro(child)
                     else:
                         # Append other stuff as protected/verbatim or ignore?
                         # Usually figures have \centering, \includegraphics etc.
                         # We should probably collect them as preserved context?
                         # Or just ignore them in the "translatable stream" but we need to reconstruct the document.
                         
                         # This Chunking strategy assumes we are extracting text to translate 
                         # and replacing it in the original doc.
                         # BUT my Structure definition implies "Reconstruction from Chunks".
                         # If we skip nodes, we lose them.
                         
                         # CRITICAL: The Chunker must preserve EVERYTHING.
                         # If it's not translatable, it must be in a Chunk (maybe marked as non-translatable?)
                         # Or the Chunker only returns "Translatable Chunks" and we use a different mechanism to reconstruct?
                         
                         # Look at Structure.py: LaTeXDocument.chunks -> list of Chunks.
                         # Chunk.reconstruct() -> returns string.
                         # So yes, we must capture EVERYTHING.
                         
                         # So, for non-translatable stuff, we create a Chunk with NO translatable content?
                         # Or content that is just the latex code, and we don't send it to LLM?
                         # The Chunk class doesn't have a "do_not_translate" flag.
                         # But if we don't send it to the LLM, we just use the original content.
                         
                         # Strategy:
                         # If it's not text/translatable, we still add it to self.current_chunk_text.
                         # But we rely on `_flush_chunk` to create a "paragraph".
                         # If we encounter a big block of non-translatable stuff (like a figure),
                         # we might want to isolate it so the LLM doesn't see it in the middle of a sentence.
                         
                         if hasattr(child, 'latex_verbatim'):
                             self.current_chunk_text.append(child.latex_verbatim())
            else:
                # Recurse by default for unknown environments to find text?
                # or Protect? 
                # Let's Recurse.
                self._process_nodes(node.nodelist)

    def _handle_protected_element(self, latex_text: str, prefix: str):
        placeholder = f"[[{prefix}_{self.protected_counter}]]"
        self.protected_counter += 1
        self.current_preserved[placeholder] = latex_text
        self.current_chunk_text.append(placeholder)
