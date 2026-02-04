# Configuration Guide

This guide covers all configuration options for ieeA.

## Configuration Hierarchy

ieeA uses a layered configuration system (later layers override earlier):

1. Built-in defaults: `src/ieeA/defaults/config.yaml`
2. User config: `~/.ieeA/config.yaml`
3. Command-line flags: override selected settings

## Creating a Configuration File

### User Configuration

Create `~/.ieeA/config.yaml`:

```yaml
llm:
  # SDK: openai | anthropic | null (null = direct HTTP)
  sdk: null
  # Model name or list (first item is used)
  models: openai/gpt-5-mini
  # API key (required when sdk is not null)
  key: ""
  # Optional custom endpoint
  endpoint: https://openrouter.ai/api/v1/chat/completions
  temperature: 0.1
  max_tokens: 4000

compilation:
  engine: xelatex
  timeout: 120
  clean_aux: true

paths:
  output_dir: output
  cache_dir: .cache

fonts:
  auto_detect: true
  # Optional manual overrides
  main: null
  sans: null
  mono: null

translation:
  custom_system_prompt: null
  custom_user_prompt: null
  preserve_terms: []
  quality_mode: standard
  examples_path: null

parser:
  extra_protected_environments: []
  extra_translatable_environments: []
```

## Configuration Options

### LLM Settings

```yaml
llm:
  sdk: openai
  models: gpt-4o-mini
  key: "sk-..."
  endpoint: null
  temperature: 0.1
  max_tokens: 4000
```

Notes:
- `sdk` must be `openai`, `anthropic`, or `null`.
- `models` can be a string or a list; lists use the first item.
- When `sdk` is not null, `key` is required (or provide `--key` on the CLI).

### Compilation Settings

```yaml
compilation:
  engine: xelatex
  timeout: 120
  clean_aux: true
```

### Path Settings

```yaml
paths:
  output_dir: output
  cache_dir: .cache
```

### Font Settings

```yaml
fonts:
  auto_detect: true
  main: null
  sans: null
  mono: null
```

### Translation Settings

```yaml
translation:
  custom_system_prompt: null
  custom_user_prompt: null
  preserve_terms: []
  quality_mode: standard
  examples_path: null
```

### Parser Settings

```yaml
parser:
  extra_protected_environments: []
  extra_translatable_environments: []
```

### Glossary File (separate)

The glossary is loaded from `~/.ieeA/glossary.yaml` and is not part of `config.yaml`.
See [Custom Rules & Glossary](custom-rules.md).

## Command-Line Overrides

Selected settings can be overridden via command line:

```bash
# Override SDK, model, key, endpoint
ieeA translate paper.tex --sdk anthropic --model claude-3-sonnet-20240229 --key "sk-..."
ieeA translate paper.tex --endpoint https://openrouter.ai/api/v1/chat/completions

# Override output directory
ieeA translate paper.tex --output-dir ./my-output/

# Control concurrency
ieeA translate paper.tex --concurrency 20

# Enable high-quality translation mode
ieeA translate https://arxiv.org/abs/2301.07041 --high-quality

# Provide custom abstract for context
ieeA translate https://arxiv.org/abs/2301.07041 --high-quality --abstract "This paper proposes..."

# Skip compilation or keep source
ieeA translate paper.tex --no-compile --keep-source

# Verbose logging
ieeA translate paper.tex --verbose
```

## Complete Example Configuration

```yaml
# ~/.ieeA/config.yaml - Full example

llm:
  sdk: openai
  models: gpt-4o-mini
  key: "sk-..."
  endpoint: null
  temperature: 0.1
  max_tokens: 4000

compilation:
  engine: xelatex
  timeout: 120
  clean_aux: true

paths:
  output_dir: ~/Documents/translations
  cache_dir: ~/.ieeA/cache

fonts:
  auto_detect: true
  main: null
  sans: null
  mono: null

translation:
  custom_system_prompt: null
  custom_user_prompt: null
  preserve_terms: []
  quality_mode: standard
  examples_path: null

parser:
  extra_protected_environments: []
  extra_translatable_environments: []
```

## Configuration Validation

ieeA validates configuration on startup. Invalid settings will produce clear error messages:

```
Error: Invalid configuration
  llm.sdk: sdk must be 'openai', 'anthropic', or None, got 'invalid'
  llm.models: models cannot be empty
```

## Next Steps

- [Custom Rules & Glossary](custom-rules.md) - Create custom translation rules
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
