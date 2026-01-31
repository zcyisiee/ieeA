# Compiler Module Notes

## Design Decisions

### Engine Priority
We prioritized LaTeX engines in this order:
1.  **xelatex**: Best support for CJK characters and modern fonts. Primary choice.
2.  **lualatex**: Good alternative if xelatex is missing or fails.
3.  **pdflatex**: Fallback. Unlikely to handle CJK well without complex setup, but included for completeness.

### Chinese Support Injection
- **Method**: Regex injection of `xeCJK` package and font settings.
- **Location**: Immediately after `\documentclass{...}`.
- **Fonts**: Hardcoded to Noto CJK family (`Noto Serif CJK SC`, `Noto Sans CJK SC`, `Noto Sans Mono CJK SC`) as per requirements.
- **Idempotency**: Checks if `xeCJK` is already present to prevent duplicate imports.

### Error Handling
- LaTeX logs are verbose. We extract the first error starting with `!` and capture 5 lines of context.
- Falls back to scanning for "Fatal error" if no `!` is found.

### Resource Management
- Compilation runs in a `tempfile.TemporaryDirectory`.
- Resources from `working_dir` are copied to the temp directory before compilation.
- Generated PDF is moved to the target output path upon success.
