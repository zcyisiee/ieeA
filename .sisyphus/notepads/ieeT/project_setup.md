# Project Setup Decisions

## Packaging
- **Standard**: `pyproject.toml` (PEP 621)
- **Backend**: `hatchling` (Modern, fast, supports reproducible builds)
- **Layout**: `src` layout (prevents import errors during testing, enforces installation)

## Development Tools
- **Testing**: `pytest` (Standard industry practice)
- **Linting/Formatting**: `ruff` (Fast, replaces flake8/black/isort)
- **Type Checking**: `mypy` (Static type safety)

## Directory Structure
- `src/ieeet`: Main package
- Submodules initialized: `downloader`, `parser`, `translator`, `validator`, `compiler`, `rules`, `defaults`
