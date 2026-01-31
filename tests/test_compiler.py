import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ieet.compiler import LaTeXCompiler, inject_chinese_support

class TestChineseSupport:
    def test_inject_simple(self):
        source = r"\documentclass{article}" + "\n" + r"\begin{document}Hello\end{document}"
        result = inject_chinese_support(source)
        assert r"\usepackage{xeCJK}" in result
        assert r"\setCJKmainfont{Noto Serif CJK SC}" in result
        assert r"\documentclass{article}" in result

    def test_inject_no_duplication(self):
        source = r"\documentclass{article}" + "\n" + r"\usepackage{xeCJK}" + "\n" + r"\begin{document}Hello\end{document}"
        result = inject_chinese_support(source)
        # Should return unchanged if xeCJK is present
        assert result == source

    def test_inject_fallback(self):
        # No documentclass
        source = "Hello World"
        result = inject_chinese_support(source)
        assert r"\usepackage{xeCJK}" in result
        assert source in result

class TestLaTeXCompiler:
    @pytest.fixture
    def compiler(self):
        return LaTeXCompiler(timeout=10)

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_compile_success(self, mock_which, mock_run, compiler):
        mock_which.return_value = "/usr/bin/xelatex"
        
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "Output log"
        mock_process.stderr = ""
        mock_run.return_value = mock_process
        
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "output.pdf"
            
            # Mock the pdf creation (since we mocked subprocess)
            def side_effect(*args, **kwargs):
                # The compiler runs in a temp dir, we need to create the mock pdf there
                # args[0] is command list, kwargs['cwd'] is working dir
                cwd = kwargs.get('cwd')
                if cwd:
                    (cwd / "main.pdf").touch()
                return mock_process
            
            mock_run.side_effect = side_effect
            
            result = compiler.compile(r"\documentclass{article}\begin{document}Test\end{document}", out_path)
            
            assert result.success
            assert result.engine_used == "xelatex"
            assert result.pdf_path.resolve() == out_path.resolve()
            assert out_path.exists()

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_compile_fallback(self, mock_which, mock_run, compiler):
        # xelatex fails, lualatex succeeds
        def which_side_effect(cmd):
            return f"/usr/bin/{cmd}"
        mock_which.side_effect = which_side_effect
        
        # First call (xelatex) fails, second (lualatex) succeeds
        fail_process = MagicMock()
        fail_process.returncode = 1
        fail_process.stdout = "! Fatal error"
        fail_process.stderr = ""
        
        success_process = MagicMock()
        success_process.returncode = 0
        success_process.stdout = "Success"
        success_process.stderr = ""
        
        mock_run.side_effect = [fail_process, success_process]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "output.pdf"
            
            # Need to patch _run_engine slightly or mock better to handle file creation?
            # Actually, let's just trust the logic if subprocess returns 0
            # But wait, our code checks if pdf exists.
            # We need to ensure the second call creates the pdf.
            
            # Let's mock _run_engine directly for easier testing of logic flow
            with patch.object(compiler, '_run_engine') as mock_engine:
                mock_engine.side_effect = [
                    (False, "Error log", "Fatal error"), # xelatex
                    (True, "Success log", None)          # lualatex
                ]
                
                # We also need to mock shutil.copy2 since the real PDF won't exist
                with patch("shutil.copy2") as mock_copy:
                    # And check for existence
                    with patch("pathlib.Path.exists") as mock_exists:
                        mock_exists.return_value = True
                        
                        result = compiler.compile("source", out_path)
                        
                        assert result.success
                        assert result.engine_used == "lualatex"
                        # Verify we tried xelatex then lualatex
                        assert mock_engine.call_count == 2
                        assert mock_engine.call_args_list[0][0][0] == "xelatex"
                        assert mock_engine.call_args_list[1][0][0] == "lualatex"

    def test_copy_resources(self, compiler):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            src_path = Path(src)
            dst_path = Path(dst)
            
            (src_path / "image.png").touch()
            (src_path / ".hidden").touch()
            (src_path / "subdir").mkdir()
            (src_path / "subdir" / "file.txt").touch()
            
            compiler._copy_resources(src_path, dst_path)
            
            assert (dst_path / "image.png").exists()
            assert not (dst_path / ".hidden").exists()
            assert (dst_path / "subdir" / "file.txt").exists()

    def test_extract_error(self, compiler):
        log = """
This is some info
! LaTeX Error: File `article.cls' not found.
Type X to quit or <RETURN> to proceed,
or enter new name. (Default extension: cls)

Enter file name: 
"""
        error = compiler._extract_error(log)
        assert "LaTeX Error: File `article.cls' not found" in error
        assert "Type X to quit" in error # It captures context
