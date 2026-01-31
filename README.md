# ieeT

**ieeT** (IEEE/arXiv Translator) is a tool for translating academic LaTeX papers from English to Chinese while preserving mathematical formulas, citations, and document structure.

## Features

- **arXiv Paper Download**: Automatically download source files from arXiv
- **LaTeX Parsing**: Parse complex LaTeX documents with proper handling of imports, math, and citations
- **Smart Chunking**: Split documents into translatable chunks while preserving structure
- **Glossary Support**: Maintain consistent terminology across translations
- **Multiple LLM Providers**: Support for OpenAI, Claude, Qwen, and Doubao
- **Validation Engine**: Verify translation quality and structural integrity
- **Resume Capability**: Save/restore translation progress for large documents

## Quick Start

```bash
# Install ieeT
pip install -e .

# Translate an arXiv paper
ieeet translate 2301.07041 --output ./translated/

# Or translate a local LaTeX file
ieeet translate paper.tex --output ./translated/
```

## Installation

### Requirements

- Python 3.10 or higher
- XeLaTeX (for PDF compilation)
- An API key for at least one LLM provider

### Basic Installation

```bash
# Clone the repository
git clone https://github.com/your-org/ieeet.git
cd ieeet

# Install in development mode
pip install -e .

# Install development dependencies
pip install -e ".[dev]"
```

For detailed installation instructions, see [docs/installation.md](docs/installation.md).

## Usage

### Translating arXiv Papers

```bash
# By arXiv ID
ieeet translate 1706.03762

# By arXiv URL
ieeet translate https://arxiv.org/abs/1706.03762

# With custom output directory
ieeet translate 1706.03762 --output ./my-translations/
```

### Translating Local Files

```bash
# Single file
ieeet translate paper.tex

# With custom glossary
ieeet translate paper.tex --glossary my-glossary.yaml
```

### Using Custom Configuration

```bash
# Use a specific config file
ieeet translate paper.tex --config my-config.yaml

# Override LLM provider
ieeet translate paper.tex --provider claude --model claude-3-sonnet
```

## Configuration

ieeT uses a layered configuration system:

1. **Default config**: Built-in defaults
2. **User config**: `~/.ieeet/config.yaml`
3. **Project config**: `./ieeet.yaml` in working directory
4. **Command-line flags**: Override any setting

### Example Configuration

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
  output_dir: output
  cache_dir: .cache
```

For all configuration options, see [docs/configuration.md](docs/configuration.md).

## Glossary

ieeT supports custom glossaries for consistent terminology:

```yaml
# glossary.yaml
"attention mechanism": "注意力机制"
"transformer": "Transformer架构"
"self-attention":
  target: "自注意力"
  context: "Deep Learning"
  domain: "NLP"
```

See [docs/custom-rules.md](docs/custom-rules.md) for details.

## Supported LLM Providers

| Provider | Models | API Key Env Var |
|----------|--------|-----------------|
| OpenAI | gpt-4o, gpt-4o-mini, gpt-4-turbo | `OPENAI_API_KEY` |
| Claude | claude-3-opus, claude-3-sonnet | `ANTHROPIC_API_KEY` |
| Qwen | qwen-turbo, qwen-plus, qwen-max | `DASHSCOPE_API_KEY` |
| Doubao | doubao-pro-* | `VOLCENGINE_API_KEY` |

## Project Structure

```
ieeet/
├── src/ieeet/
│   ├── cli.py              # Command-line interface
│   ├── downloader/         # arXiv paper downloader
│   ├── parser/             # LaTeX parsing and chunking
│   ├── translator/         # LLM translation pipeline
│   ├── validator/          # Translation validation
│   ├── rules/              # Glossary and validation rules
│   └── defaults/           # Default configuration
├── tests/                  # Test suite
│   ├── integration/        # End-to-end tests
│   └── ...                 # Unit tests
└── docs/                   # Documentation
```

## Documentation

- [Installation Guide](docs/installation.md)
- [Configuration Guide](docs/configuration.md)
- [Custom Rules & Glossary](docs/custom-rules.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Known Limitations](docs/known-limitations.md)

## Running Tests

```bash
# Run all tests
pytest

# Run unit tests only (fast)
pytest -m "not slow"

# Run integration tests with real papers
pytest -m slow

# Run with coverage
pytest --cov=ieeet
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting pull requests.
