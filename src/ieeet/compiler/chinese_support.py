import re

def inject_chinese_support(latex_source: str) -> str:
    r"""
    Injects xeCJK package and Noto CJK font settings into the LaTeX source.
    
    This function inserts the necessary LaTeX commands to support Chinese characters
    using the xeCJK package and Noto CJK fonts. It attempts to insert these commands
    immediately after the \documentclass declaration.
    
    Args:
        latex_source (str): The original LaTeX source code.
        
    Returns:
        str: The modified LaTeX source code with Chinese support injected.
    """
    # Check if xeCJK is already present to avoid duplication
    if "xeCJK" in latex_source:
        return latex_source

    # The injection content for Chinese support
    # We use Noto fonts as requested
    injection = (
        "\n% Auto-injected Chinese Support\n"
        r"\usepackage{xeCJK}" + "\n"
        r"\setCJKmainfont{Noto Serif CJK SC}" + "\n"
        r"\setCJKsansfont{Noto Sans CJK SC}" + "\n"
        r"\setCJKmonofont{Noto Sans Mono CJK SC}" + "\n"
    )
    
    # Try to find the documentclass declaration
    # Matches \documentclass[...]{...} or \documentclass{...}
    # We search for the end of the closing brace '}'
    match = re.search(r'\\documentclass(\[.*?\])?\{.*?\}', latex_source, re.DOTALL)
    
    if match:
        end_pos = match.end()
        # Insert after the documentclass line
        return latex_source[:end_pos] + injection + latex_source[end_pos:]
    else:
        # If no documentclass is found (unlikely for valid LaTeX), 
        # prepend to the start of the file
        return injection + latex_source
