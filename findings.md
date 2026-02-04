# Findings

## Session Catchup
- Attempt 1 failed: $CLAUDE_PLUGIN_ROOT not set; /scripts/session-catchup.py missing.
- Attempt 2 ran absolute path; script returned no output (assume no unsynced context).

## Initial Grep Findings
- Citation validation messages in `src/ieeA/validator/rules.py` (Missing/Unexpected citations).
- Validation entry point in `src/ieeA/validator/engine.py` calls `check_citations`.
- Docs mention missing citations in `docs/troubleshooting.md`.
- README and `docs/custom-rules.md` mention citation preservation; `src/ieeA/parser/chunker.py` protects cite/ref/label macros.

## Evidence From Output
- `output/hq/2406.03007/main.tex:326` contains `\cite{achiam2023gpt}`, `\cite{liu2024information}`, `\cite{zhuang2024toolqa}`, `\cite{gupta2023visual}`.
- `output/hq/2406.03007/main_translated.tex:145` replaces these with numeric `\cite{96..101}`.

## Prompt + Placeholder Format
- `src/ieeA/translator/prompts.py` FORMAT_RULES already mentions preserving `\cite{...}` and placeholders like `[[MATH_0]]`.
- Placeholder patterns include `[[PREFIX_N]]` (e.g., CITE/REF/LABEL/MATH) and chunk placeholders `{{CHUNK_uuid}}` in parser/structure.

## CHUNK Placeholder Exposure
- Chunk content passed to LLM is `chunk.content` (see `src/ieeA/translator/pipeline.py`).
- `{{CHUNK_uuid}}` is primarily used in the body template, but `_maybe_chunk_paragraph` stores the full paragraph (including any `{{CHUNK_...}}`) as `chunk.content`, so CHUNK placeholders can appear in LLM input if they are embedded in paragraph text.

## Env/Command Configuration
- Protected environments and translatable environments are hardcoded in `src/ieeA/parser/latex_parser.py` (PROTECTED_ENVIRONMENTS, TRANSLATABLE_ENVIRONMENTS, SECTION_COMMANDS).
- Config fields for extra environments exist in `src/ieeA/rules/config.py` and docs (`README.md`, `docs/configuration.md`).
- Protected commands are defined in `_protect_commands` in `src/ieeA/parser/latex_parser.py` (cite/ref/eqref/label/url/footnote/href).
- `\textbf{}` is not protected by the current parser; it appears only in prompt rules and deprecated `src/ieeA/parser/chunker.py` comments.

## Parser Flow Order
- `_process_body` runs: protect author -> extract captions -> protect math environments -> protect inline math -> protect commands -> extract translatable content.
- Protected environments become `[[MATHENV_n]]`; inline math becomes `[[MATH_n]]`; protected commands become `[[CITE_n]]`, `[[REF_n]]`, etc.
- Translatable content extraction then creates `{{CHUNK_uuid}}` placeholders for titles/sections/captions/environments/paragraphs.
