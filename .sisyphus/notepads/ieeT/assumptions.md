# Assumption Validation Findings

## Summary
All foundational assumptions validated successfully (10/10 papers passed all tests).

## Key Findings

### 1. Source Availability: 10/10 ✓
- All arXiv papers provide source code via e-print endpoint
- URL pattern: `https://arxiv.org/e-print/{arxiv_id}`
- Rate limit of 3 seconds between requests is sufficient

### 2. Archive Format
- **100% tar.gz**: All 10 papers returned tar.gz archives
- No single .tex.gz files encountered in this sample
- Archive sizes ranged from 6 to 38 files

### 3. Main TeX Detection: 10/10 ✓
Detection methods breakdown:
- `filename_match:main.tex`: 5 papers (50%)
- `documentclass_search`: 5 papers (50%)

Papers NOT using main.tex:
- 1706.03762 (Transformer): `ms.tex`
- 2203.02155: `neurips_2021.tex`
- 1312.6114 (VAE): `iclr14_sva.tex`
- 1409.1556 (VGGNet): `ilsvrc14.tex`
- 1512.03385 (ResNet): `residual_v1_arxiv_release.tex`

### 4. pylatexenc Parsing: 10/10 ✓
- All papers parsed successfully with pylatexenc
- LatexWalker + LatexNodes2Text combination works reliably
- No parsing errors encountered

### 5. File Structure Patterns

| Paper | Total Files | TeX Files | Has Subdirs |
|-------|------------|-----------|-------------|
| 2301.07041 | 18 | 12 | Yes |
| 1706.03762 | 23 | 10 | Yes |
| 2305.10601 | 16 | 1 | Yes |
| 1810.04805 | 28 | 20 | No |
| 2203.02155 | 32 | 6 | Yes |
| 1312.6114 | 14 | 4 | Yes |
| 2006.11239 | 24 | 1 | Yes |
| 1409.1556 | 6 | 1 | No |
| 1512.03385 | 13 | 1 | Yes |
| 2010.11929 | 38 | 9 | Yes |

Common file types:
- `.tex` - LaTeX source files
- `.bbl` - Pre-compiled bibliography
- `.pdf`, `.png`, `.jpg` - Figures
- `.sty`, `.cls`, `.bst` - Style files

### 6. Observations for Implementation

1. **Main file detection priority works**: `main.tex` catches 50%, `\documentclass` search catches the rest
2. **Multi-file papers common**: Many papers split content into sections/chapters
3. **Subdirectories typical**: 8/10 papers use subdirectories (often for figures)
4. **Style files bundled**: Papers often include custom .sty files
5. **Pre-compiled bibliographies**: .bbl files common (no need to compile .bib)

## Thresholds Met

| Metric | Result | Target | Status |
|--------|--------|--------|--------|
| Source available | 10/10 | ≥8/10 | ✓ PASS |
| Main TeX identified | 10/10 | ≥8/10 | ✓ PASS |
| pylatexenc success | 10/10 | ≥6/10 | ✓ PASS |
