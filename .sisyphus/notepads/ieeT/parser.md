# LaTeX Parser Implementation Findings

## Architecture
- **Structure**: Separated into `structure.py` (data classes), `chunker.py` (logic), and `latex_parser.py` (file handling).
- **Library**: `pylatexenc` proved robust for parsing.

## Key Decisions
1.  **Argument Parsing**: `LatexWalker` must be initialized with `latex_context=get_default_latex_context_db()` to correctly parse macro arguments. Without this, macros like `\section{...}` are seen as just the macro name, and `{...}` as a separate group.
2.  **Section Titles**: We use the **last** argument of section macros as the translatable content. This handles `\section[opt]{Title}` correctly.
3.  **Flattening**: Recursive `\input` and `\include` resolution is done via Regex (`r'(^|[^%])\\(input|include)\{([^}]+)\}'`) before parsing. This simplifies the AST construction as we work on a single "virtual" file.
4.  **Protection**:
    -   Math environments (`$`, `$$`, `\begin{equation}`) are protected.
    -   Citations and References (`\cite`, `\ref`) are protected.
    -   Unknown macros are protected.
    -   Formatting macros (`\textbf`, `\textit`) are **not** protected; their content is part of the text flow (verbatim included).
5.  **Chunking**:
    -   Primary split is double newline `\n\n` for paragraphs.
    -   Section macros trigger an immediate chunk flush.

## Known Limitations
-   Comment handling in `\input` flattening is heuristic (checks for `%` at start of line or preceding char).
-   Complex nested optional arguments might confuse the simple "last argument" rule for sections, but covers 99% of cases.
