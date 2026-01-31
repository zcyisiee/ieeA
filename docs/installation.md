# Installation Guide

This guide covers all installation methods for ieeT.

## System Requirements

### Required

- **Python 3.10+**: ieeT requires Python 3.10 or newer
- **XeLaTeX**: Required for compiling translated documents to PDF
- **Network Access**: For downloading arXiv papers and LLM API calls

### Optional

- **Git**: For cloning the repository
- **Docker**: For containerized installation

## Quick Installation

```bash
pip install -e .
```

## Detailed Installation

### Step 1: Install Python 3.10+

**macOS (Homebrew):**
```bash
brew install python@3.10
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.10 python3.10-venv python3-pip
```

**Windows:**
Download from [python.org](https://www.python.org/downloads/) and run the installer.

### Step 2: Install XeLaTeX

XeLaTeX is required for PDF compilation with Chinese character support.

**macOS:**
```bash
brew install --cask mactex
# Or for a smaller installation:
brew install --cask basictex
sudo tlmgr update --self
sudo tlmgr install xetex ctex
```

**Ubuntu/Debian:**
```bash
sudo apt install texlive-xetex texlive-lang-chinese
```

**Windows:**
Download and install [MiKTeX](https://miktex.org/download) or [TeX Live](https://www.tug.org/texlive/).

### Step 3: Install ieeT

**From source (recommended for development):**
```bash
git clone https://github.com/your-org/ieeet.git
cd ieeet
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
```

**With development dependencies:**
```bash
pip install -e ".[dev]"
```

### Step 4: Configure API Keys

ieeT requires an API key for at least one LLM provider:

**OpenAI:**
```bash
export OPENAI_API_KEY="sk-your-key-here"
```

**Anthropic (Claude):**
```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

**Alibaba Cloud (Qwen):**
```bash
export DASHSCOPE_API_KEY="sk-your-key-here"
```

**Volcengine (Doubao):**
```bash
export VOLCENGINE_API_KEY="your-key-here"
```

For permanent configuration, add these to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.).

### Step 5: Verify Installation

```bash
# Check ieeT is installed
ieeet --version

# Check XeLaTeX is available
xelatex --version

# Run tests (optional)
pytest -v
```

## Virtual Environment (Recommended)

We strongly recommend using a virtual environment:

```bash
# Create virtual environment
python -m venv ieeet-env

# Activate it
source ieeet-env/bin/activate  # Linux/macOS
# or
ieeet-env\Scripts\activate     # Windows

# Install ieeT
pip install -e .
```

## Docker Installation

For a containerized installation (coming soon):

```bash
docker pull your-org/ieeet:latest
docker run -v $(pwd):/workspace ieeet translate paper.tex
```

## Troubleshooting Installation

### Python version issues

```bash
# Check Python version
python --version

# Use specific version
python3.10 -m pip install -e .
```

### XeLaTeX not found

Ensure XeLaTeX is in your PATH:
```bash
which xelatex  # Should print path
```

If not found, add TeX Live to your PATH:
```bash
export PATH="/usr/local/texlive/2024/bin/x86_64-linux:$PATH"
```

### Permission errors

Use `--user` flag or virtual environment:
```bash
pip install --user -e .
```

### Missing dependencies

Install build dependencies:
```bash
# Ubuntu/Debian
sudo apt install python3-dev build-essential

# macOS
xcode-select --install
```

## Updating ieeT

```bash
cd ieeet
git pull
pip install -e .
```

## Uninstalling

```bash
pip uninstall ieeet
```

## Next Steps

- [Configuration Guide](configuration.md) - Configure ieeT for your needs
- [Quick Start](../README.md#quick-start) - Start translating papers
