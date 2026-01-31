import pytest
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tarfile
import io

from ieet.downloader import ArxivDownloader, DownloadResult

@pytest.fixture
def temp_dirs(tmp_path):
    cache_dir = tmp_path / "cache"
    output_dir = tmp_path / "output"
    cache_dir.mkdir()
    output_dir.mkdir()
    return cache_dir, output_dir

@pytest.fixture
def downloader(temp_dirs):
    cache_dir, _ = temp_dirs
    return ArxivDownloader(cache_dir=cache_dir)

class TestArxivDownloader:
    
    def test_parse_id_simple(self, downloader):
        assert downloader.parse_id("2301.07041") == "2301.07041"
        assert downloader.parse_id("  2301.07041  ") == "2301.07041"
        assert downloader.parse_id("2301.07041v2") == "2301.07041v2"

    def test_parse_id_url(self, downloader):
        assert downloader.parse_id("https://arxiv.org/abs/2301.07041") == "2301.07041"
        assert downloader.parse_id("http://arxiv.org/pdf/2301.07041.pdf") == "2301.07041"
        assert downloader.parse_id("https://arxiv.org/e-print/2301.07041") == "2301.07041"

    def test_parse_id_old_format(self, downloader):
        assert downloader.parse_id("math/0510097") == "math/0510097"
        assert downloader.parse_id("https://arxiv.org/abs/math/0510097") == "math/0510097"

    def test_parse_id_invalid(self, downloader):
        with pytest.raises(ValueError):
            downloader.parse_id("invalid-id")
        with pytest.raises(ValueError):
            downloader.parse_id("https://google.com")

    def test_find_main_tex_priority_filename(self, downloader, tmp_path):
        # Create dummy files
        (tmp_path / "other.tex").touch()
        main = tmp_path / "main.tex"
        main.touch()
        files = [tmp_path / "other.tex", main]
        
        assert downloader.find_main_tex(files) == main

    def test_find_main_tex_content_search(self, downloader, tmp_path):
        # Create dummy files
        f1 = tmp_path / "chap1.tex"
        f1.write_text("content")
        
        f2 = tmp_path / "actual_paper.tex"
        f2.write_text("% comment\n\\documentclass{article}")
        
        files = [f1, f2]
        assert downloader.find_main_tex(files) == f2

    def test_find_main_tex_fallback_size(self, downloader, tmp_path):
        f1 = tmp_path / "small.tex"
        f1.write_text("a")
        
        f2 = tmp_path / "large.tex"
        f2.write_text("aaaaa")
        
        files = [f1, f2]
        assert downloader.find_main_tex(files) == f2

    def test_find_main_tex_no_tex(self, downloader):
        with pytest.raises(FileNotFoundError):
            downloader.find_main_tex([Path("image.png")])

    @patch("requests.get")
    def test_download_success(self, mock_get, downloader, temp_dirs):
        cache_dir, output_dir = temp_dirs
        arxiv_id = "2301.07041"
        
        # Mock response content (valid tar.gz)
        # Create a real small tar.gz in memory
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            info = tarfile.TarInfo(name="main.tex")
            data = b"\\documentclass{article}"
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        tar_bytes = tar_buffer.getvalue()
        
        mock_response = Mock()
        mock_response.headers = {'content-type': 'application/x-eprint-tar'}
        mock_response.iter_content = lambda chunk_size: [tar_bytes]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = downloader.download(arxiv_id, output_dir)
        
        assert result.arxiv_id == arxiv_id
        assert result.main_tex.name == "main.tex"
        assert (cache_dir / f"{arxiv_id}.tar.gz").exists()
        assert (output_dir / arxiv_id / "main.tex").exists()
        
        # Check URL
        mock_get.assert_called_with(f"https://arxiv.org/e-print/{arxiv_id}", stream=True, timeout=30)

    @patch("requests.get")
    def test_download_cached(self, mock_get, downloader, temp_dirs):
        cache_dir, output_dir = temp_dirs
        arxiv_id = "2301.07041"
        
        # Pre-create cached file
        tar_path = cache_dir / f"{arxiv_id}.tar.gz"
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            info = tarfile.TarInfo(name="main.tex")
            data = b"\\documentclass{article}"
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        tar_path.write_bytes(tar_buffer.getvalue())
        
        result = downloader.download(arxiv_id, output_dir)
        
        # Should not call requests.get
        mock_get.assert_not_called()
        assert result.main_tex.name == "main.tex"

    @patch("requests.get")
    @patch("time.sleep")
    def test_rate_limit(self, mock_sleep, mock_get, downloader, temp_dirs):
        cache_dir, output_dir = temp_dirs
        arxiv_id = "2301.07041"
        
        # Setup mock for success
        mock_response = Mock()
        mock_response.headers = {'content-type': 'application/x-eprint-tar'}
        mock_response.iter_content = lambda chunk_size: [b""] # Invalid tar but enough to trigger logic
        mock_get.return_value = mock_response
        
        # First call sets the time
        try:
            downloader.download(arxiv_id, output_dir)
        except:
            pass # We expect failure due to bad tar content, that's fine
            
        # Second call should trigger sleep if immediate
        try:
            downloader.download("2301.07042", output_dir)
        except:
            pass
            
        assert mock_sleep.called

    @patch("requests.get")
    def test_download_pdf_error(self, mock_get, downloader, temp_dirs):
        cache_dir, output_dir = temp_dirs
        arxiv_id = "2301.07041"
        
        mock_response = Mock()
        mock_response.headers = {'content-type': 'application/pdf'}
        mock_get.return_value = mock_response
        
        with pytest.raises(ValueError, match="got PDF"):
            downloader.download(arxiv_id, output_dir)
