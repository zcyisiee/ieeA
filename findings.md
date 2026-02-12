# Findings & Decisions

## Requirements (Current Task)
- Use corpus content from `output/2407.12281/main.tex` to validate glossary dynamic loading.
- Prove per-chunk filtering is applied (not full glossary each time).
- Prove batch path passes union glossary hints while per-chunk metadata remains chunk-local.
- Provide executable test evidence.

## Research Findings
- Dynamic glossary filtering lives in `src/ieeA/translator/pipeline.py:69` (`_build_glossary_hints`) and uses `casefold` substring matching.
- Single-chunk path calls filter on the chunk source text (`src/ieeA/translator/pipeline.py:229`) and writes glossary metadata in return object (`src/ieeA/translator/pipeline.py:258`).
- Batch path computes per-chunk hints (`src/ieeA/translator/pipeline.py:284`), unions via `batch_glossary_hints.update(...)` (`src/ieeA/translator/pipeline.py:286`), passes union to provider (`src/ieeA/translator/pipeline.py:308`), then writes chunk-local metadata (`src/ieeA/translator/pipeline.py:334`).
- Provider interface receives `glossary_hints` through `LLMProvider.translate(...)` in `src/ieeA/translator/llm_base.py:24`.
- Real corpus file exists and parses successfully: `output/2407.12281/main.tex` -> 198 chunks (via `LaTeXParser.parse_file`).
- Candidate corpus terms with broad coverage include `large language models`, `data poisoning`, `prefix-tuning`, and `trigger`.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Build integration-style test around `TranslationPipeline` with mocked provider | Verifies internal behavior without network calls |
| Feed test strings sampled from parsed real corpus | Satisfies user requirement for corpus-based scenario |
| Assert provider kwargs for batch union + result metadata for per-chunk counts | Ensures both transport semantics and bookkeeping are correct |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| `rg` unavailable in shell | Switched to built-in `grep` and `ast_grep_search` tools |
| `tests/` directory not present in current checkout | Derived patterns from source and scripts, then plan to create focused test file |

## Resources
- `src/ieeA/translator/pipeline.py`
- `src/ieeA/translator/prompts.py`
- `src/ieeA/translator/llm_base.py`
- `src/ieeA/parser/latex_parser.py`
- `output/2407.12281/main.tex`

## Visual/Browser Findings
- Not applicable (no browser interaction in this task).
