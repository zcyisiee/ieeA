# Known Limitations

This document describes the current limitations of ieeT and potential workarounds.

## LaTeX Parsing Limitations

### Complex Custom Macros

**Limitation:** Papers with heavily customized macros may not parse correctly.

**Details:** ieeT uses pylatexenc for parsing, which handles standard LaTeX well but may struggle with:
- Custom macro definitions with complex argument patterns
- Non-standard package commands
- Self-defined environments

**Workaround:** 
- Expand macros manually before translation
- Add custom macro definitions to a local pylatexenc context

### Nested Environments

**Limitation:** Deeply nested environments may not chunk optimally.

**Details:** Chunks are created at paragraph boundaries, but complex nesting (e.g., itemize inside figure inside table) may result in suboptimal chunk boundaries.

**Workaround:** Review and manually adjust problematic sections.

### Comments and Verbatim

**Limitation:** LaTeX comments are preserved but not translated.

**Details:** Content in `%` comments and `\verb` environments is kept as-is.

**Impact:** If important content is in comments, it won't be translated.

## Translation Limitations

### Context Window

**Limitation:** Very long paragraphs may exceed LLM context limits.

**Details:** While chunking handles most cases, extremely long unbroken text blocks may cause issues.

**Workaround:** Add paragraph breaks to long sections before translation.

### Mathematical Accuracy

**Limitation:** LLMs may occasionally alter mathematical expressions.

**Details:** While ieeT preserves math environments as placeholders, the surrounding text translation may affect mathematical meaning.

**Workaround:** Always review mathematical sections carefully.

### Domain-Specific Terminology

**Limitation:** Specialized terminology may be translated inconsistently.

**Details:** Without a comprehensive glossary, the LLM may use different translations for the same term.

**Workaround:** Create a domain-specific glossary for your field.

### Figures and Tables

**Limitation:** Figure/table captions are translated, but content is not.

**Details:** Text in figures (as images) or table cell alignment cannot be translated.

**Workaround:** Recreate figures with Chinese text manually.

## arXiv Paper Limitations

### Source Availability

**Limitation:** Not all arXiv papers have LaTeX source available.

**Details:** Some papers are uploaded as PDF only, especially:
- Older papers
- Papers with proprietary formatting
- Papers with sensitive content

**Workaround:** Contact authors for source or use OCR-based solutions.

### Non-Standard Formats

**Limitation:** Papers using unusual LaTeX setups may fail.

**Examples:**
- Papers using obsolete LaTeX2.09 syntax
- Papers with non-UTF8 encodings
- Papers split across many files with complex dependencies

**Workaround:** Pre-process papers to standardize format.

### Multi-File Projects

**Limitation:** Complex multi-file projects may not resolve all imports.

**Details:** While `\input{}` and `\include{}` are handled, unusual patterns may fail:
- Conditional includes
- Generated file names
- Relative paths from subdirectories

**Workaround:** Manually flatten the document before translation.

## Compilation Limitations

### Font Requirements

**Limitation:** Compiled PDFs require Chinese fonts.

**Details:** XeLaTeX needs appropriate CJK fonts installed:
- SimSun, SimHei (Windows)
- STSong, STHeiti (macOS)
- Noto Sans CJK (Linux)

**Workaround:** Install fonts or configure alternative fonts in preamble.

### Package Compatibility

**Limitation:** Some packages may conflict with Chinese typesetting.

**Examples:**
- Packages that assume single-byte characters
- Fixed-width layout packages
- Some bibliography styles

**Workaround:** Add CTeX compatibility settings to preamble.

## Provider-Specific Limitations

### OpenAI

- Rate limits vary by account tier
- gpt-4 is slower but more accurate than gpt-4o-mini
- Token limits affect very long documents

### Claude

- Longer context window but higher latency
- Different handling of LaTeX in prompts

### Qwen/Doubao

- Better native Chinese but may lack LaTeX expertise
- Rate limits may be more restrictive

## Performance Limitations

### Speed

**Limitation:** Large papers take significant time to translate.

**Details:** A typical 20-page paper with 100+ chunks may take 10-30 minutes depending on:
- LLM provider and model
- Rate limiting settings
- Network latency

**Workaround:** Use resume capability for long translations.

### Memory

**Limitation:** Very large documents may consume significant memory.

**Details:** Parsing and holding entire documents in memory can be intensive for papers with many embedded resources.

**Workaround:** Process sections independently if needed.

## Planned Improvements

The following improvements are planned for future versions:

1. **Better macro expansion** - Handle more custom macro patterns
2. **Parallel translation** - Translate multiple chunks concurrently
3. **Interactive review** - Web UI for reviewing translations
4. **Figure text extraction** - OCR for figure text
5. **Bibliography translation** - Translate reference titles

## Reporting Limitations

If you encounter a limitation not listed here:

1. Check if it's a bug vs. a limitation
2. Search existing issues on GitHub
3. Create a new issue with:
   - Paper ID or minimal example
   - Expected behavior
   - Actual behavior
   - ieeT version

## See Also

- [Troubleshooting](troubleshooting.md) - Solutions to common problems
- [Configuration](configuration.md) - Adjust settings for better results
