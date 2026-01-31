# Configuration and Rules System Design

## Configuration Schema
The configuration system uses Pydantic models with YAML backing.
- **Location**: `src/ieet/defaults/config.yaml` (defaults), `~/.ieet/config.yaml` (user overrides).
- **Structure**:
  - `llm`: Provider settings (openai, model, api_key_env, temp, max_tokens).
  - `compilation`: LaTeX engine settings (xelatex, timeout).
  - `paths`: Directory management (output, cache).

## Glossary Format
Supports a hybrid format for flexibility:
1. **Simple Mapping**: `"Term": "Translation"`
2. **Structured Entry**:
   ```yaml
   "Term":
     target: "Translation"
     context: "Context string"
     domain: "Field domain"
     priority: 10
     notes: "Usage notes"
   ```
- **Loading Logic**: User glossary merges into default glossary. User entries overwrite defaults if keys match.

## Validation Rules
Declarative rules defined in YAML.
- **Fields**:
  - `id`: Unique identifier
  - `description`: Human readable description
  - `pattern`: Regex pattern to match
  - `replacement`: Optional suggestion
  - `severity`: warning/error/info
  - `trigger`: Execution phase (e.g., post-translate)
