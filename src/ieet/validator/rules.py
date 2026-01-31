import re
from typing import List, Tuple, Set, Dict, Any

class BuiltInRules:
    @staticmethod
    def check_braces(text: str) -> List[str]:
        """Check for balanced braces and brackets."""
        stack = []
        errors = []
        mapping = {')': '(', ']': '[', '}': '{'}
        
        # Simple stack-based check. 
        # Note: This is a naive check that doesn't ignore escaped braces.
        # Enhancing to ignore escaped chars.
        
        i = 0
        while i < len(text):
            char = text[i]
            
            # Skip escaped characters
            if char == '\\':
                i += 2
                continue
                
            if char in '({[':
                stack.append((char, i))
            elif char in ')}]':
                if not stack:
                    errors.append(f"Unmatched closing brace '{char}' at position {i}")
                else:
                    last_open, _ = stack.pop()
                    if mapping[char] != last_open:
                        errors.append(f"Mismatched brace '{char}' at {i}, expected closing for '{last_open}'")
            
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
        
        orig_inline = original.count('$')
        trans_inline = translated.count('$')
        
        # We expect even numbers of $ usually
        if trans_inline % 2 != 0:
            errors.append("Odd number of '$' delimiters in translated text.")
            
        # We might expect the same number of math blocks, but sometimes they get merged/split?
        # Strictly speaking they should match if text structure is preserved.
        if orig_inline != trans_inline:
            errors.append(f"Math delimiter count mismatch: Original {orig_inline}, Translated {trans_inline}")
            
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
