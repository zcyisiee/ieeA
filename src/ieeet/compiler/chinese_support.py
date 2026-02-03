import re
import shutil
import subprocess
from typing import Optional, List, Dict, Any, Union


def get_available_fonts() -> List[str]:
    """Detect available CJK fonts using fc-list."""
    if not shutil.which("fc-list"):
        return []

    try:
        # Check specifically for Chinese fonts
        result = subprocess.run(
            ["fc-list", ":lang=zh", "family"], capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return []

        fonts = set()
        for line in result.stdout.splitlines():
            # Output format: "Font Family,Font Name,..."
            # Get the first family name
            families = line.split(",")
            for family in families:
                fonts.add(family.strip())
        return list(fonts)
    except Exception:
        return []


def detect_cjk_fonts(available_fonts: List[str]) -> Dict[str, str]:
    """Select best available CJK fonts based on priority."""
    # Priority groups: (Serif, Sans, Mono)
    font_candidates = [
        # Noto CJK (Google/Adobe) - Preferred
        {
            "main": ["Noto Serif CJK SC", "Noto Serif CJK"],
            "sans": ["Noto Sans CJK SC", "Noto Sans CJK"],
            "mono": ["Noto Sans Mono CJK SC", "Noto Sans Mono CJK"],
        },
        # Source Han (Adobe)
        {
            "main": ["Source Han Serif SC", "Source Han Serif"],
            "sans": ["Source Han Sans SC", "Source Han Sans"],
            "mono": ["Source Han Sans HW SC", "Source Han Sans HW"],
        },
        # macOS Chinese Fonts
        {
            "main": ["Songti SC", "STSong"],
            "sans": ["PingFang SC", "STHeiti"],
            "mono": ["STFangsong"],
        },
        # Windows Chinese Fonts
        {
            "main": ["SimSun", "SongTi"],
            "sans": ["SimHei", "Microsoft YaHei"],
            "mono": ["FangSong", "KaiTi"],
        },
        # Fandol (TeX Live default)
        {"main": ["FandolSong"], "sans": ["FandolHei"], "mono": ["FandolKai"]},
    ]

    def find_match(candidates: List[str]) -> Optional[str]:
        for cand in candidates:
            for avail in available_fonts:
                if cand.lower() == avail.lower():
                    return avail
                if cand.lower() in avail.lower():
                    return avail
        return None

    for group in font_candidates:
        main = find_match(group["main"])
        if main:
            sans = find_match(group["sans"]) or main
            mono = find_match(group["mono"]) or sans
            return {"main": main, "sans": sans, "mono": mono}

    # Fallback
    return {
        "main": "Noto Serif CJK SC",
        "sans": "Noto Sans CJK SC",
        "mono": "Noto Sans Mono CJK SC",
    }


def inject_chinese_support(latex_source: str, font_config: Optional[Any] = None) -> str:
    r"""
    Injects xeCJK package and Noto CJK font settings into the LaTeX source.

    This function inserts the necessary LaTeX commands to support Chinese characters
    using the xeCJK package. It attempts to insert these commands
    immediately after the \documentclass declaration.

    Args:
        latex_source (str): The original LaTeX source code.
        font_config (Optional[Any]): Configuration object or dict with font settings.

    Returns:
        str: The modified LaTeX source code with Chinese support injected.
    """
    # Check if xeCJK is already present to avoid duplication
    if "xeCJK" in latex_source:
        return latex_source

    # Default: auto-detect fonts
    avail = get_available_fonts()
    detected = detect_cjk_fonts(avail)
    main_font = detected["main"]
    sans_font = detected["sans"]
    mono_font = detected["mono"]

    # Override with config if provided
    if font_config:
        # Support both Pydantic model and dict
        if isinstance(font_config, dict):
            cfg_main = font_config.get("main")
            cfg_sans = font_config.get("sans")
            cfg_mono = font_config.get("mono")
            use_auto = font_config.get("auto_detect", True)
        else:
            # Assume Pydantic model
            cfg_main = getattr(font_config, "main", None)
            cfg_sans = getattr(font_config, "sans", None)
            cfg_mono = getattr(font_config, "mono", None)
            use_auto = getattr(font_config, "auto_detect", True)

        # If auto_detect is disabled, use configured fonts
        if not use_auto:
            if cfg_main:
                main_font = cfg_main
            if cfg_sans:
                sans_font = cfg_sans
            if cfg_mono:
                mono_font = cfg_mono
        else:
            # Auto-detect is enabled, but override with any explicitly set fonts
            if cfg_main:
                main_font = cfg_main
            if cfg_sans:
                sans_font = cfg_sans
            if cfg_mono:
                mono_font = cfg_mono

    injection = (
        "\n% Auto-injected Chinese Support\n"
        r"\usepackage{xeCJK}" + "\n"
        f"\\setCJKmainfont{{{main_font}}}\n"
        f"\\setCJKsansfont{{{sans_font}}}\n"
        f"\\setCJKmonofont{{{mono_font}}}\n"
    )

    # Find position right before \begin{document}
    begin_doc_match = re.search(r"\\begin\{document\}", latex_source)
    if begin_doc_match:
        insert_pos = begin_doc_match.start()
        return latex_source[:insert_pos] + injection + "\n" + latex_source[insert_pos:]

    # Fallback: append at end if no \begin{document} found
    return latex_source + "\n" + injection
