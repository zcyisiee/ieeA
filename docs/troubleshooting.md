# Troubleshooting Guide

This guide covers common issues and their solutions when using ieeT.

## Installation Issues

### Python version error

**Problem:**
```
ERROR: This package requires Python >=3.10
```

**Solution:**
```bash
# Check your Python version
python --version

# Install Python 3.10+ or use pyenv
pyenv install 3.10.0
pyenv local 3.10.0
```

### XeLaTeX not found

**Problem:**
```
Error: xelatex not found in PATH
```

**Solution:**
```bash
# macOS
brew install --cask mactex

# Ubuntu/Debian
sudo apt install texlive-xetex texlive-lang-chinese

# Verify installation
which xelatex
```

### Missing Python dependencies

**Problem:**
```
ModuleNotFoundError: No module named 'pylatexenc'
```

**Solution:**
```bash
pip install -e .
# or
pip install pylatexenc pydantic pyyaml requests
```

## API Key Issues

### API key not found

**Problem:**
```
Error: API key not found. Set OPENAI_API_KEY environment variable.
```

**Solution:**
```bash
# Set the environment variable
export OPENAI_API_KEY="sk-your-key-here"

# Or add to your shell profile
echo 'export OPENAI_API_KEY="sk-your-key-here"' >> ~/.bashrc
source ~/.bashrc
```

### Invalid API key

**Problem:**
```
Error: Invalid API key provided
```

**Solution:**
1. Verify the key is correct (no extra spaces)
2. Check the key hasn't expired
3. Ensure you're using the right provider's key

## Download Issues

### arXiv paper not found

**Problem:**
```
Error: Could not download paper 2301.99999
```

**Solution:**
1. Verify the arXiv ID is correct
2. Check if the paper exists: `https://arxiv.org/abs/2301.99999`
3. Some papers don't have source available (only PDF)

### Source not available (got PDF)

**Problem:**
```
Error: Source not available for 2301.07041 (got PDF)
```

**Solution:**
This paper only has PDF available, not LaTeX source. Try a different paper or obtain the source manually.

### Network timeout

**Problem:**
```
Error: Connection timeout while downloading
```

**Solution:**
```bash
# Check internet connection
curl https://arxiv.org

# Try again (arXiv rate limits requests)
# Wait 3+ seconds between requests
```

## Parsing Issues

### LaTeX parse error

**Problem:**
```
Error: Failed to parse LaTeX content: Unclosed group
```

**Solution:**
1. Check for unbalanced braces in the source
2. Some papers have non-standard LaTeX that may fail
3. Try with `--strict-mode off` (if available)

### No .tex files found

**Problem:**
```
Error: No .tex files found in the archive
```

**Solution:**
The arXiv source may be in an unusual format. Check the downloaded archive manually:
```bash
tar -tzf papers_cache/2301.07041.tar.gz
```

### Wrong main file detected

**Problem:**
The parser selected the wrong main .tex file.

**Solution:**
Specify the main file explicitly:
```bash
ieeA translate ./paper/main.tex
```

## Translation Issues

### Rate limit exceeded

**Problem:**
```
Error: Rate limit exceeded. Please wait before retrying.
```

**Solution:**
```yaml
# In config.yaml, increase rate limit delay
translation:
  rate_limit_delay: 2.0  # seconds between requests
```

### Translation timeout

**Problem:**
```
Error: Translation request timed out
```

**Solution:**
1. Try a faster model (gpt-4o-mini instead of gpt-4)
2. Reduce chunk size
3. Check your network connection

### Translation too short/long

**Problem:**
```
Warning: Translation length ratio 0.3 is outside expected range
```

**Solution:**
This is usually a warning, not an error. The LLM may have:
- Summarized instead of translated
- Added explanatory text
- Review the output and adjust temperature if needed

## Compilation Issues

### Missing CTeX package

**Problem:**
```
! LaTeX Error: File `ctex.sty' not found.
```

**Solution:**
```bash
# Install CTeX package
sudo tlmgr install ctex

# Or install full Chinese support
sudo apt install texlive-lang-chinese
```

### Font not found

**Problem:**
```
! Font \...=SimSun at ... not loadable
```

**Solution:**
Install Chinese fonts:
```bash
# macOS - fonts usually available
# Linux
sudo apt install fonts-noto-cjk
```

### Compilation timeout

**Problem:**
```
Error: Compilation timed out after 120 seconds
```

**Solution:**
```yaml
# In config.yaml, increase timeout
compilation:
  timeout: 300  # 5 minutes
```

## Validation Errors

### Unbalanced braces

**Problem:**
```
Error: Unbalanced braces in translation: missing }
```

**Solution:**
The LLM may have corrupted LaTeX structure. Options:
1. Re-run translation (may get different result)
2. Manually fix the output
3. Use a more capable model

### Missing citations

**Problem:**
```
Error: Citation \cite{smith2020} missing in translation
```

**Solution:**
The LLM removed a citation. Options:
1. Re-run with lower temperature
2. Add the citation back manually
3. Update prompt to emphasize citation preservation

## Resume/Recovery

### Resuming interrupted translation

If translation was interrupted:
```bash
# State is saved automatically, just run again
ieeA translate paper.tex
# Will resume from last completed chunk
```

### Clearing state

To start fresh:
```bash
rm .cache/state.json
ieeA translate paper.tex
```

## Getting Help

### Debug mode

Run with verbose output:
```bash
ieeA translate paper.tex --verbose
```

### Check logs

Logs are saved to:
- `~/.ieeA/logs/` (user logs)
- `./ieet.log` (project logs)

### Reporting issues

When reporting issues, include:
1. ieeT version: `ieeA --version`
2. Python version: `python --version`
3. OS and version
4. Full error message
5. Minimal reproduction steps

## Next Steps

- [Known Limitations](known-limitations.md) - Current limitations
- [Configuration Guide](configuration.md) - Adjust settings
