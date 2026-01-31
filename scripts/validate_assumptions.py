#!/usr/bin/env python3
"""
Assumption Validation Script for arXiv Paper Processing

Tests foundational assumptions before building the full system:
1. Source code availability from arXiv
2. File structure patterns in downloaded archives
3. pylatexenc parsing success rate
4. Main tex file identification accuracy
"""

import json
import os
import re
import tarfile
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import gzip
import shutil

import requests

# Optional: pylatexenc for LaTeX parsing
try:
    from pylatexenc.latex2text import LatexNodes2Text
    from pylatexenc.latexwalker import LatexWalker, LatexWalkerError
    PYLATEXENC_AVAILABLE = True
except ImportError:
    LatexWalker = None  # type: ignore[misc, assignment]
    LatexNodes2Text = None  # type: ignore[misc, assignment]
    LatexWalkerError = Exception  # type: ignore[misc, assignment]
    PYLATEXENC_AVAILABLE = False
    print("Warning: pylatexenc not installed. Install with: pip install pylatexenc")


# Test papers from various categories and time periods
TEST_PAPERS = [
    "2301.07041",  # CS.CL - Standard NLP paper
    "1706.03762",  # CS.CL - Transformer paper (classic)
    "2305.10601",  # CS.CL - Recent NLP paper
    "1810.04805",  # CS.CL - BERT paper
    "2203.02155",  # CS.CV - Computer vision
    "1312.6114",   # CS.LG - VAE paper (older format)
    "2006.11239",  # CS.LG - DDPM paper
    "1409.1556",   # CS.CV - VGGNet (older)
    "1512.03385",  # CS.CV - ResNet
    "2010.11929",  # CS.CV - ViT paper
]

ARXIV_SOURCE_URL = "https://arxiv.org/e-print/{arxiv_id}"
RATE_LIMIT_SECONDS = 3
CACHE_DIR = Path("papers_cache")


@dataclass
class PaperResult:
    """Results for a single paper validation."""
    arxiv_id: str
    source_available: bool = False
    download_error: Optional[str] = None
    archive_type: Optional[str] = None  # "tar.gz", "gz", "tex"
    file_count: int = 0
    tex_files: list = field(default_factory=list)
    main_tex_detected: Optional[str] = None
    main_tex_method: Optional[str] = None  # How we detected the main file
    has_documentclass: bool = False
    pylatexenc_parse_success: bool = False
    pylatexenc_error: Optional[str] = None
    file_structure: dict = field(default_factory=dict)


@dataclass 
class ValidationReport:
    """Overall validation report."""
    total_papers: int = 0
    source_available_count: int = 0
    main_tex_identified_count: int = 0
    pylatexenc_success_count: int = 0
    papers: list = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "summary": {
                "total_papers": self.total_papers,
                "source_available": self.source_available_count,
                "source_available_rate": f"{self.source_available_count}/{self.total_papers}",
                "main_tex_identified": self.main_tex_identified_count,
                "main_tex_identification_rate": f"{self.main_tex_identified_count}/{self.total_papers}",
                "pylatexenc_success": self.pylatexenc_success_count,
                "pylatexenc_success_rate": f"{self.pylatexenc_success_count}/{self.total_papers}",
                "thresholds": {
                    "source_available_target": "≥8/10",
                    "main_tex_target": "≥8/10",
                    "pylatexenc_target": "≥6/10"
                },
                "pass_status": {
                    "source_available": self.source_available_count >= 8,
                    "main_tex_identified": self.main_tex_identified_count >= 8,
                    "pylatexenc_success": self.pylatexenc_success_count >= 6
                }
            },
            "papers": [self._paper_to_dict(p) for p in self.papers]
        }
    
    def _paper_to_dict(self, p: PaperResult) -> dict:
        return {
            "arxiv_id": p.arxiv_id,
            "source_available": p.source_available,
            "download_error": p.download_error,
            "archive_type": p.archive_type,
            "file_count": p.file_count,
            "tex_files": p.tex_files,
            "main_tex_detected": p.main_tex_detected,
            "main_tex_method": p.main_tex_method,
            "has_documentclass": p.has_documentclass,
            "pylatexenc_parse_success": p.pylatexenc_parse_success,
            "pylatexenc_error": p.pylatexenc_error,
            "file_structure": p.file_structure
        }


def download_paper_source(arxiv_id: str) -> tuple[Optional[Path], Optional[str]]:
    """Download paper source from arXiv e-print endpoint."""
    url = ARXIV_SOURCE_URL.format(arxiv_id=arxiv_id)
    cache_path = CACHE_DIR / f"{arxiv_id}.tar.gz"
    
    # Check cache first
    if cache_path.exists():
        print(f"  Using cached: {cache_path}")
        return cache_path, None
    
    try:
        print(f"  Downloading from {url}...")
        response = requests.get(url, timeout=30, allow_redirects=True)
        response.raise_for_status()
        
        # Save to cache
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(response.content)
        return cache_path, None
        
    except requests.exceptions.RequestException as e:
        return None, str(e)


def detect_archive_type(file_path: Path) -> str:
    """Detect if file is tar.gz, gzip, or plain text."""
    with open(file_path, 'rb') as f:
        header = f.read(10)
    
    # Check for gzip magic number
    if header[:2] == b'\x1f\x8b':
        # Try to open as tar
        try:
            with tarfile.open(file_path, 'r:gz') as tf:
                tf.getnames()  # Test if it's a valid tar
            return "tar.gz"
        except tarfile.TarError:
            return "gz"  # Plain gzipped file (likely single .tex)
    
    # Check for plain TeX
    if b'\\documentclass' in header or b'%' in header:
        return "tex"
    
    return "unknown"


def extract_archive(file_path: Path, extract_dir: Path) -> tuple[list[Path], str]:
    """Extract archive and return list of files and archive type."""
    archive_type = detect_archive_type(file_path)
    files: list[Path] = []
    
    if archive_type == "tar.gz":
        with tarfile.open(file_path, 'r:gz') as tf:
            tf.extractall(extract_dir)
        files = list(extract_dir.rglob("*"))
    
    elif archive_type == "gz":
        output_path = extract_dir / "paper.tex"
        with gzip.open(file_path, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        files = [output_path]
    
    elif archive_type == "tex":
        output_path = extract_dir / "paper.tex"
        shutil.copy(file_path, output_path)
        files = [output_path]
    
    return [f for f in files if f.is_file()], archive_type


def find_tex_files(files: list[Path]) -> list[Path]:
    """Find all .tex files in extracted files."""
    return [f for f in files if f.suffix.lower() == '.tex']


def detect_main_tex(tex_files: list[Path], extract_dir: Path) -> tuple[Optional[Path], Optional[str]]:
    """
    Detect main tex file using priority order:
    1. main.tex
    2. paper.tex  
    3. arxiv.tex
    4. Search for \\documentclass
    """
    priority_names = ["main.tex", "paper.tex", "arxiv.tex"]
    
    # Check priority names
    for priority_name in priority_names:
        for tex_file in tex_files:
            if tex_file.name.lower() == priority_name:
                return tex_file, f"filename_match:{priority_name}"
    
    # Search for \documentclass
    for tex_file in tex_files:
        try:
            content = tex_file.read_text(encoding='utf-8', errors='ignore')
            if re.search(r'\\documentclass', content):
                return tex_file, "documentclass_search"
        except Exception:
            continue
    
    # Fallback: return first tex file if any
    if tex_files:
        return tex_files[0], "fallback_first"
    
    return None, None


def check_documentclass(tex_file: Path) -> bool:
    """Check if file contains \\documentclass."""
    try:
        content = tex_file.read_text(encoding='utf-8', errors='ignore')
        return bool(re.search(r'\\documentclass', content))
    except Exception:
        return False


def test_pylatexenc_parsing(tex_file: Path) -> tuple[bool, Optional[str]]:
    """Test if pylatexenc can parse the main tex file."""
    if not PYLATEXENC_AVAILABLE:
        return False, "pylatexenc not installed"
    
    try:
        content = tex_file.read_text(encoding='utf-8', errors='ignore')
        
        from pylatexenc.latex2text import LatexNodes2Text
        from pylatexenc.latexwalker import LatexWalker, LatexWalkerError
        
        walker = LatexWalker(content)
        nodes, _, _ = walker.get_latex_nodes()
        
        converter = LatexNodes2Text()
        text = converter.latex_to_text(content[:5000])
        
        if len(text) > 100:
            return True, None
        else:
            return False, "Minimal text extracted"
            
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:100]}"


def analyze_file_structure(files: list[Path], extract_dir: Path) -> dict:
    """Analyze the file structure of the extracted archive."""
    structure = {
        "total_files": len(files),
        "tex_files": 0,
        "bib_files": 0,
        "image_files": 0,
        "style_files": 0,
        "other_files": 0,
        "has_subdirectories": False,
        "extensions": {}
    }
    
    image_exts = {'.png', '.jpg', '.jpeg', '.pdf', '.eps', '.ps'}
    style_exts = {'.sty', '.cls', '.bst'}
    
    for f in files:
        ext = f.suffix.lower()
        structure["extensions"][ext] = structure["extensions"].get(ext, 0) + 1
        
        if ext == '.tex':
            structure["tex_files"] += 1
        elif ext == '.bib':
            structure["bib_files"] += 1
        elif ext in image_exts:
            structure["image_files"] += 1
        elif ext in style_exts:
            structure["style_files"] += 1
        else:
            structure["other_files"] += 1
        
        # Check for subdirectories
        if f.parent != extract_dir:
            structure["has_subdirectories"] = True
    
    return structure


def validate_paper(arxiv_id: str) -> PaperResult:
    """Validate a single paper."""
    result = PaperResult(arxiv_id=arxiv_id)
    
    # Download
    file_path, error = download_paper_source(arxiv_id)
    if error or file_path is None:
        result.download_error = error
        return result
    
    result.source_available = True
    
    # Extract to temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        extract_dir = Path(tmpdir)
        
        try:
            files, archive_type = extract_archive(file_path, extract_dir)
            result.archive_type = archive_type
            result.file_count = len(files)
            
            # Find tex files
            tex_files = find_tex_files(files)
            result.tex_files = [str(f.relative_to(extract_dir)) for f in tex_files]
            
            # Analyze file structure
            result.file_structure = analyze_file_structure(files, extract_dir)
            
            # Detect main tex
            main_tex, method = detect_main_tex(tex_files, extract_dir)
            if main_tex:
                result.main_tex_detected = str(main_tex.relative_to(extract_dir))
                result.main_tex_method = method
                result.has_documentclass = check_documentclass(main_tex)
                
                # Test pylatexenc
                success, error = test_pylatexenc_parsing(main_tex)
                result.pylatexenc_parse_success = success
                result.pylatexenc_error = error
                
        except Exception as e:
            result.download_error = f"Extraction error: {str(e)}"
    
    return result


def run_validation() -> ValidationReport:
    """Run validation on all test papers."""
    report = ValidationReport(total_papers=len(TEST_PAPERS))
    
    print(f"\n{'='*60}")
    print("arXiv Paper Assumption Validation")
    print(f"{'='*60}")
    print(f"Testing {len(TEST_PAPERS)} papers...\n")
    
    for i, arxiv_id in enumerate(TEST_PAPERS):
        print(f"[{i+1}/{len(TEST_PAPERS)}] Processing {arxiv_id}...")
        
        result = validate_paper(arxiv_id)
        report.papers.append(result)
        
        if result.source_available:
            report.source_available_count += 1
        if result.main_tex_detected:
            report.main_tex_identified_count += 1
        if result.pylatexenc_parse_success:
            report.pylatexenc_success_count += 1
        
        # Status
        status = "✓" if result.source_available else "✗"
        main_status = "✓" if result.main_tex_detected else "✗"
        parse_status = "✓" if result.pylatexenc_parse_success else "✗"
        print(f"  Source: {status} | Main tex: {main_status} | Parse: {parse_status}")
        
        # Rate limit (except for last)
        if i < len(TEST_PAPERS) - 1:
            print(f"  Waiting {RATE_LIMIT_SECONDS}s (rate limit)...")
            time.sleep(RATE_LIMIT_SECONDS)
    
    return report


def print_summary(report: ValidationReport):
    """Print validation summary."""
    data = report.to_dict()
    summary = data["summary"]
    
    print(f"\n{'='*60}")
    print("VALIDATION SUMMARY")
    print(f"{'='*60}")
    
    print(f"\nSource Availability: {summary['source_available_rate']} (target: {summary['thresholds']['source_available_target']})")
    print(f"  Status: {'✓ PASS' if summary['pass_status']['source_available'] else '✗ FAIL'}")
    
    print(f"\nMain TeX Identification: {summary['main_tex_identification_rate']} (target: {summary['thresholds']['main_tex_target']})")
    print(f"  Status: {'✓ PASS' if summary['pass_status']['main_tex_identified'] else '✗ FAIL'}")
    
    print(f"\npylatexenc Parsing: {summary['pylatexenc_success_rate']} (target: {summary['thresholds']['pylatexenc_target']})")
    print(f"  Status: {'✓ PASS' if summary['pass_status']['pylatexenc_success'] else '✗ FAIL'}")
    
    # Detection methods breakdown
    methods = {}
    for paper in data["papers"]:
        method = paper.get("main_tex_method") or "not_detected"
        methods[method] = methods.get(method, 0) + 1
    
    print(f"\nMain TeX Detection Methods:")
    for method, count in sorted(methods.items(), key=lambda x: -x[1]):
        print(f"  {method}: {count}")
    
    # Archive types
    archive_types = {}
    for paper in data["papers"]:
        atype = paper.get("archive_type") or "failed"
        archive_types[atype] = archive_types.get(atype, 0) + 1
    
    print(f"\nArchive Types:")
    for atype, count in sorted(archive_types.items(), key=lambda x: -x[1]):
        print(f"  {atype}: {count}")
    
    # Parse failures
    failures = [(p["arxiv_id"], p["pylatexenc_error"]) 
                for p in data["papers"] 
                if not p["pylatexenc_parse_success"] and p["pylatexenc_error"]]
    if failures:
        print(f"\npylatexenc Parse Failures:")
        for arxiv_id, error in failures:
            print(f"  {arxiv_id}: {error}")
    
    print(f"\n{'='*60}")
    all_pass = all(summary['pass_status'].values())
    print(f"OVERALL: {'✓ ALL ASSUMPTIONS VALIDATED' if all_pass else '✗ SOME ASSUMPTIONS FAILED'}")
    print(f"{'='*60}\n")


def main():
    """Main entry point."""
    report = run_validation()
    
    # Save report
    report_path = Path("validation_report.json")
    with open(report_path, 'w') as f:
        json.dump(report.to_dict(), f, indent=2)
    print(f"Report saved to: {report_path}")
    
    # Print summary
    print_summary(report)
    
    return report


if __name__ == "__main__":
    main()
