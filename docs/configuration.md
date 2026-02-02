# Configuration Guide

This guide covers all configuration options for ieeT.

## Configuration Hierarchy

ieeT uses a layered configuration system (later layers override earlier):

1. **Built-in defaults**: `src/ieet/defaults/config.yaml`
2. **User config**: `~/.ieeA/config.yaml`
3. **Project config**: `./ieet.yaml` (in working directory)
4. **Command-line flags**: Override any setting

## Creating a Configuration File

### User Configuration

Create `~/.ieeA/config.yaml`:

```yaml
llm:
  provider: openai
  model: gpt-4o-mini
  api_key_env: OPENAI_API_KEY
  temperature: 0.1
  max_tokens: 4000

compilation:
  engine: xelatex
  timeout: 120
  clean_aux: true

paths:
  output_dir: ~/ieet-output
  cache_dir: ~/.ieeA/cache
```

### Project Configuration

Create `ieet.yaml` in your project directory for project-specific settings.

## Configuration Options

### LLM Settings

```yaml
llm:
  # LLM provider: openai, claude, qwen, doubao
  provider: openai
  
  # Model name (provider-specific)
  model: gpt-4o-mini
  
  # Environment variable containing API key
  api_key_env: OPENAI_API_KEY
  
  # Sampling temperature (0.0-2.0, lower = more deterministic)
  temperature: 0.1
  
  # Maximum tokens in response
  max_tokens: 4000
```

#### Provider-Specific Models

| Provider | Available Models | Recommended |
|----------|------------------|-------------|
| openai | gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo | gpt-4o-mini |
| claude | claude-3-opus-20240229, claude-3-sonnet-20240229 | claude-3-sonnet |
| qwen | qwen-turbo, qwen-plus, qwen-max | qwen-plus |
| doubao | doubao-pro-4k, doubao-pro-32k, doubao-pro-128k | doubao-pro-32k |

### Compilation Settings

```yaml
compilation:
  # LaTeX engine: xelatex, pdflatex, lualatex
  engine: xelatex
  
  # Compilation timeout in seconds
  timeout: 120
  
  # Remove auxiliary files after compilation
  clean_aux: true
```

### Path Settings

```yaml
paths:
  # Default output directory for translations
  output_dir: output
  
  # Cache directory for downloaded papers
  cache_dir: .cache
```

### Font Settings

```yaml
fonts:
  # Auto-detect available CJK fonts (recommended)
  auto_detect: true
  
  # Or specify fonts manually:
  # main: "STSong"      # Main font (Serif) - for body text
  # sans: "STHeiti"     # Sans font - for headings
  # mono: "STFangsong"  # Mono font - for code
```

#### Available Fonts by Platform

| Platform | Main (Serif) | Sans | Mono |
|----------|--------------|------|------|
| macOS | STSong, Songti SC | STHeiti, PingFang SC | STFangsong |
| Windows | SimSun | SimHei, Microsoft YaHei | FangSong, KaiTi |
| Linux | Noto Serif CJK SC | Noto Sans CJK SC | Noto Sans Mono CJK SC |

When `auto_detect: true`, ieeT will automatically detect available fonts in this priority order:
1. Noto CJK (Google/Adobe)
2. Source Han (Adobe)
3. macOS system fonts (STSong, PingFang SC)
4. Windows system fonts (SimSun, SimHei)
5. Fandol (TeX Live default)

### Translation Settings

```yaml
translation:
  # Maximum retries on API failure
  max_retries: 3
  
  # Base delay between retries (seconds, uses exponential backoff)
  retry_delay: 1.0
  
  # Delay between API calls for rate limiting (seconds)
  rate_limit_delay: 0.5
  
  # Save intermediate state for resume capability
  save_state: true
```

### Glossary Settings

```yaml
glossary:
  # Path to glossary file
  path: glossary.yaml
  
  # Whether to use built-in glossary
  use_builtin: true
  
  # Merge custom glossary with built-in
  merge: true
```

## Environment Variables

API keys should be set as environment variables:

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Anthropic (Claude)
export ANTHROPIC_API_KEY="sk-ant-..."

# Alibaba Cloud (Qwen/DashScope)
export DASHSCOPE_API_KEY="sk-..."

# Volcengine (Doubao)
export VOLCENGINE_API_KEY="..."
```

## Command-Line Overrides

Most settings can be overridden via command line:

```bash
# Override provider and model
ieeA translate paper.tex --provider claude --model claude-3-sonnet-20240229

# Override output directory
ieeA translate paper.tex --output ./my-output/

# Override temperature
ieeA translate paper.tex --temperature 0.2

# Use specific config file
ieeA translate paper.tex --config my-config.yaml
```

## Complete Example Configuration

```yaml
# ~/.ieeA/config.yaml - Full example

llm:
  provider: openai
  model: gpt-4o-mini
  api_key_env: OPENAI_API_KEY
  temperature: 0.1
  max_tokens: 4000

compilation:
  engine: xelatex
  timeout: 120
  clean_aux: true

paths:
  output_dir: ~/Documents/translations
  cache_dir: ~/.ieeA/cache

translation:
  max_retries: 3
  retry_delay: 1.0
  rate_limit_delay: 0.5
  save_state: true

glossary:
  path: ~/.ieeA/glossary.yaml
  use_builtin: true
  merge: true
```

## Configuration Validation

ieeT validates configuration on startup. Invalid settings will produce clear error messages:

```
Error: Invalid configuration
  llm.provider: 'invalid-provider' is not one of: openai, claude, qwen, doubao
  llm.temperature: 3.0 is greater than maximum 2.0
```

## Next Steps

- [Custom Rules & Glossary](custom-rules.md) - Create custom translation rules
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
