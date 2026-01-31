# Downloader Implementation Notes

## arXiv API Quirks
- The `/e-print/{id}` endpoint redirects to a tar.gz file for source code.
- If source is not available, it might return a PDF. We check `Content-Type` header for `application/pdf` to detect this failure mode.
- Rate limiting is strictly enforced by arXiv (they recommend 3 seconds). Implemented `_rate_limit` method to sleep if requests are too frequent.

## File Structure Patterns
- Most papers are flat tar.gz archives.
- Main tex file detection strategy implemented:
  1. Priority filenames (`main.tex`, `paper.tex`, etc.)
  2. Content search for `\documentclass` in first 5KB
  3. Fallback to largest .tex file

## Implementation Details
- Caching: Downloaded tar.gz files are stored in `papers_cache/` (or configured cache dir).
- Extraction: Files are extracted to `{output_dir}/{arxiv_id}/`.
- Security: Uses `tarfile` but currently trusts arXiv content. Future improvement: Add tar bomb protection.
