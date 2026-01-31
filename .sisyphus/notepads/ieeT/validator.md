# Validation Engine Design & Learnings

## Architecture
The validation engine uses a hybrid approach:
1. **Structural Validation (Built-in)**: Python-based logic for complex checks that regex handles poorly.
   - Brace matching (stack-based)
   - Command consistency (set comparison for \cite, \ref)
   - Math environment integrity (delimiter counting)
   - Length ratio heuristics (Chinese/English ~ 0.6-0.8)
2. **Semantic/Style Validation (User-defined)**: Regex-based rules loaded from configuration for pattern matching and auto-fixing.

## Implemented Rules
| Rule | Type | Description |
|------|------|-------------|
| Balanced Braces | Structural | Checks matching of {}, [], () ignoring escaped chars |
| Citation Check | Structural | Ensures all \cite{...} keys in original appear in translation |
| Reference Check | Structural | Ensures all \ref{...} keys in original appear in translation |
| Math Delimiters | Structural | Checks consistency of $ delimiters |
| Length Ratio | Heuristic | Warns if translation length is <0.2x or >1.5x of original |

## Common Error Patterns
- **Dropped Citations**: LLMs often summarize multiple citations [1,2] into one or drop them.
- **Broken Math**: Inline math `$x$` often loses a delimiter or gets converted to text.
- **Hallucinated Commands**: Translators sometimes invent `\cite{}` keys.

## Future Improvements
- **Advanced Math Check**: Use a proper LaTeX parser to validate math block syntax deeper than delimiter counting.
- **Glossary Enforcement**: Integrate strict glossary term checking against the Glossary module.
- **LLM-based Review**: Use a cheap model to check semantic consistency for flagged segments.
