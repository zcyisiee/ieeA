# Task Plan: Dynamic glossary integration test on real corpus

## Goal
Design and implement an integration-style test that uses corpus content from `output/2407.12281/main.tex` to verify dynamic per-chunk glossary filtering and batch union behavior in the translation pipeline.

## Current Phase
Phase 5

## Phases

### Phase 1: Requirements & Discovery
- [x] Understand user intent and acceptance criteria
- [x] Map glossary filtering and batch union code paths
- [x] Confirm existing repository test patterns and conventions
- **Status:** complete

### Phase 2: Test Design
- [x] Select representative chunks from parsed real corpus
- [x] Define single-chunk and batch assertions
- [x] Define metadata assertions (`had_glossary_terms`, `glossary_terms_count`)
- **Status:** complete

### Phase 3: Implementation
- [x] Add integration test file and mock provider
- [x] Add assertions for per-chunk filtering
- [x] Add assertions for batch union kwargs and per-chunk metadata
- **Status:** complete

### Phase 4: Testing & Verification
- [x] Run targeted pytest for new integration test
- [x] Run broader related tests if needed
- [x] Record pass/fail evidence in progress.md
- **Status:** complete

### Phase 5: Delivery
- [x] Summarize implementation and evidence
- [x] Highlight any pre-existing failures if encountered
- **Status:** complete

## Key Questions
1. Which parsed chunks from `main.tex` best demonstrate non-overlapping glossary terms?
2. What is the most stable way to assert `glossary_hints` passed to provider in async flow?
3. Where should this integration test live given current repo layout?

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Verify behavior at `TranslationPipeline.translate_chunk` and `translate_batch` level | Confirms dynamic filter and batch union without external API dependence |
| Use real text snippets from parsed `output/2407.12281/main.tex` | Matches user requirement for corpus-based verification |
| Assert provider call kwargs plus result metadata | Covers both call-time union and per-chunk accounting semantics |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| `rg` command unavailable in shell | 1 | Switched to `grep`/`ast_grep_search` tools |

## Notes
- Update phase status as you progress: pending → in_progress → complete
- Log ALL errors - they help avoid repetition
