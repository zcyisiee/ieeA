import os
import time
import tarfile
import re
import requests
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class DownloadResult:
    arxiv_id: str
    source_dir: Path
    main_tex: Path
    downloaded_files: List[Path]

class ArxivDownloader:
    """Downloader for arXiv source files."""
    
    BASE_URL = "https://arxiv.org/e-print/"
    _last_request_time = 0

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize downloader with optional cache directory."""
        self.cache_dir = cache_dir or Path("papers_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _rate_limit(self):
        """Ensure at least 3 seconds between requests."""
        current_time = time.time()
        elapsed = current_time - self._last_request_time
        if elapsed < 3:
            time.sleep(3 - elapsed)
        self._last_request_time = time.time()

    def parse_id(self, input_str: str) -> str:
        """Extract arXiv ID from URL or string."""
        clean_str = input_str.strip()
        # Matches modern arXiv IDs: YYMM.NNNNN(vV)
        match = re.search(r'(\d{4}\.\d{4,5}(?:v\d+)?)', clean_str)
        if match:
            return match.group(1)
        
        # Matches old arXiv IDs: category/YYMMNNN
        old_match = re.search(r'([a-zA-Z\-\.]+\/\d{7})', clean_str)
        if old_match:
            return old_match.group(1)
            
        raise ValueError(f"Could not parse arXiv ID from: {input_str}")

    def download(self, arxiv_id_or_url: str, output_dir: Path) -> DownloadResult:
        """
        Download and extract source files for a given arXiv ID/URL.
        
        Args:
            arxiv_id_or_url: arXiv ID or URL
            output_dir: Directory to extract files to
            
        Returns:
            DownloadResult containing paths and metadata
        """
        arxiv_id = self.parse_id(arxiv_id_or_url)
        tar_path = self.cache_dir / f"{arxiv_id}.tar.gz"
        
        # Download if not cached
        if not tar_path.exists():
            self._rate_limit()
            url = f"{self.BASE_URL}{arxiv_id}"
            
            try:
                response = requests.get(url, stream=True, timeout=30)
                response.raise_for_status()
                
                # Check if we got a PDF instead of source (header check)
                content_type = response.headers.get('content-type', '')
                if 'application/pdf' in content_type:
                    raise ValueError(f"Source not available for {arxiv_id} (got PDF)")
                
                with open(tar_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
            except Exception as e:
                # Clean up incomplete download
                if tar_path.exists():
                    tar_path.unlink()
                raise e
        
        # Extract files
        extract_dir = output_dir / arxiv_id
        # Clean extract dir if exists to ensure fresh extraction
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)
        
        extracted_files = self.extract_source(tar_path, extract_dir)
        
        if not extracted_files:
            raise ValueError(f"No files extracted from {tar_path}")
            
        main_tex = self.find_main_tex(extracted_files)
        
        return DownloadResult(
            arxiv_id=arxiv_id,
            source_dir=extract_dir,
            main_tex=main_tex,
            downloaded_files=extracted_files
        )

    def extract_source(self, archive_path: Path, extract_dir: Path) -> List[Path]:
        """Extract tar.gz archive to directory."""
        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                
                # Safety check for zip/tar bombs or absolute paths could go here
                # For now trusting arXiv content
                tar.extractall(path=extract_dir)
                
        except tarfile.ReadError:
            raise ValueError(f"File {archive_path} is not a valid tar.gz archive")
            
        # Recursively find all files
        all_files = []
        for root, _, filenames in os.walk(extract_dir):
            for name in filenames:
                all_files.append(Path(root) / name)
        
        return sorted(all_files)

    def find_main_tex(self, tex_files: List[Path]) -> Path:
        """Find the main LaTeX file using heuristics."""
        # Filter for .tex files
        candidates = [f for f in tex_files if f.suffix.lower() == '.tex']
        
        if not candidates:
            # Handle case where main file might not have .tex extension (rare but happens in old papers)
            # Or if it's a single file submission
            raise FileNotFoundError("No .tex files found in the archive")
            
        # Priority 1: Filename match
        priorities = ["main.tex", "paper.tex", "arxiv.tex", "ms.tex", "article.tex"]
        for p in priorities:
            for f in candidates:
                if f.name.lower() == p:
                    return f
                    
        # Priority 2: content search for \documentclass
        for f in candidates:
            try:
                # Read first 2000 chars to find documentclass
                content = f.read_text(errors='ignore')[:5000]
                # Remove comments
                content_no_comments = re.sub(r'%.*', '', content)
                if r'\documentclass' in content_no_comments:
                    return f
            except Exception:
                continue
                
        # Fallback: Return the largest .tex file
        return max(candidates, key=lambda p: p.stat().st_size)
