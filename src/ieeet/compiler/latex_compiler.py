import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union

from .chinese_support import inject_chinese_support

@dataclass
class CompilationResult:
    success: bool
    pdf_path: Optional[Path] = None
    log_content: Optional[str] = None
    error_message: Optional[str] = None
    engine_used: Optional[str] = None

class LaTeXCompiler:
    def __init__(self, timeout: int = 120):
        self.timeout = timeout
        # Priority: xelatex (best CJK), lualatex (good CJK), pdflatex (fallback)
        self.engines = ["xelatex", "lualatex", "pdflatex"]

    def inject_chinese_support(self, latex_source: str) -> str:
        """Wrapper around the injection logic."""
        return inject_chinese_support(latex_source)

    def compile(self, latex_source: str, output_path: Union[str, Path], working_dir: Optional[Union[str, Path]] = None) -> CompilationResult:
        """
        Compiles LaTeX source to PDF using multiple engines with fallback.
        
        Args:
            latex_source: The LaTeX code to compile.
            output_path: Where to save the generated PDF.
            working_dir: Optional directory containing resources (images, etc.). 
                         If provided, contents are copied to the temp compile dir.
        """
        output_path = Path(output_path).resolve()
        
        # Create a temporary directory for compilation to keep things clean
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # If working_dir is provided, copy its contents to temp_dir
            if working_dir:
                working_dir_path = Path(working_dir)
                if working_dir_path.exists():
                    self._copy_resources(working_dir_path, temp_path)
            
            # Write source to file
            source_file = temp_path / "main.tex"
            source_file.write_text(latex_source, encoding="utf-8")
            
            last_error = None
            last_log = None
            
            for engine in self.engines:
                # Skip engines that are not installed
                if not shutil.which(engine):
                    continue
                    
                success, log, error = self._run_engine(engine, source_file, temp_path)
                
                if success:
                    # Move generated PDF to output_path
                    pdf_file = temp_path / "main.pdf"
                    if pdf_file.exists():
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(pdf_file, output_path)
                        return CompilationResult(
                            success=True,
                            pdf_path=output_path,
                            log_content=log,
                            engine_used=engine
                        )
                
                last_log = log
                last_error = error
            
            # If we reach here, all engines failed
            return CompilationResult(
                success=False,
                log_content=last_log,
                error_message=f"All engines failed. Last error: {last_error}",
                engine_used=None
            )

    def _copy_resources(self, src: Path, dst: Path):
        """Copies resource files from src to dst, ignoring hidden files."""
        try:
            for item in src.iterdir():
                if item.name.startswith('.'):
                    continue
                
                target = dst / item.name
                if item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, target)
        except Exception:
            # Ignore copy errors (e.g. permission issues), compilation might still work
            pass

    def _run_engine(self, engine: str, source_file: Path, cwd: Path) -> Tuple[bool, str, Optional[str]]:
        """Runs a specific latex engine."""
        cmd = [
            engine,
            "-interaction=nonstopmode",
            "-halt-on-error",
            source_file.name
        ]
        
        try:
            process = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                encoding='utf-8',
                errors='replace'
            )
            
            # Read log file if it exists, as it's more complete than stdout
            log_content = process.stdout + "\n" + process.stderr
            log_file = cwd / "main.log"
            if log_file.exists():
                try:
                    file_log = log_file.read_text(encoding='utf-8', errors='replace')
                    if file_log.strip():
                        log_content = file_log
                except Exception:
                    pass

            if process.returncode == 0:
                return True, log_content, None
            else:
                return False, log_content, self._extract_error(log_content)
                
        except subprocess.TimeoutExpired:
            return False, "Timeout expired", "Compilation timed out"
        except Exception as e:
            return False, str(e), str(e)

    def _extract_error(self, log: str) -> str:
        """Extracts the first meaningful error from the log."""
        if not log:
            return "No log content"
            
        lines = log.splitlines()
        for i, line in enumerate(lines):
            # LaTeX errors usually start with !
            if line.strip().startswith("!"):
                # capture context (up to 5 lines)
                return "\n".join(lines[i:min(i+5, len(lines))])
        
        # Fallback: check for common error patterns if no ! found
        if "Fatal error" in log:
             return "Fatal error detected in logs"
             
        return "Unknown error (check full logs)"
