# Findings & Decisions

## Requirements
- Download and install the recommended academic CJK fonts (Source Han Serif SC, Source Han Sans SC, Source Han Mono SC).
- Update font usage so XeLaTeX uses these fonts by default for CJK.
- Add a test script that verifies the fonts are callable by XeLaTeX.

## Research Findings
- Font auto-detection and injection live in `src/ieeA/compiler/chinese_support.py`, using `fc-list` to detect CJK fonts and defaulting to Noto CJK families.
- LaTeX compilation uses xelatex by default in `src/ieeA/compiler/latex_compiler.py` and `src/ieeA/compiler/engine.py`.
- Official Source Han download sources are Adobe GitHub repositories (source-han-serif, source-han-sans, source-han-mono) with SIL OFL 1.1 license.
- Homebrew casks exist for `font-source-han-serif-sc`, `font-source-han-sans-sc`, and `font-source-han-mono` on macOS.
- XeLaTeX usage via `xeCJK` with `\setCJKmainfont`, `\setCJKsansfont`, `\setCJKmonofont` is standard.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Install fonts via Homebrew casks | Fast, macOS-native, consistent updates |
| Add scripts/test_cjk_fonts.py | Simple XeLaTeX compile to verify font availability |
| Set default fonts in defaults config | Ensure XeLaTeX uses Source Han by default |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| session-catchup.py path missing ($CLAUDE_PLUGIN_ROOT) | Retried with absolute path |
| Homebrew cask font-source-han-*-sc unavailable | Downloaded fonts from official GitHub releases and installed to ~/Library/Fonts |

## Resources
- `src/ieeA/compiler/chinese_support.py`
- `src/ieeA/compiler/latex_compiler.py`
- `src/ieeA/compiler/engine.py`
- https://github.com/adobe-fonts/source-han-serif
- https://github.com/adobe-fonts/source-han-sans
- https://github.com/adobe-fonts/source-han-mono

## Visual/Browser Findings
-
