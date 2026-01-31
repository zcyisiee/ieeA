import subprocess
from pathlib import Path
from typing import Optional

class TeXCompiler:
    """
    Compiles LaTeX files to PDF using available system tools (xelatex/pdflatex).
    """
    
    def __init__(self, engine: str = "xelatex", timeout: int = 120, clean_aux: bool = True):
        self.engine = engine
        self.timeout = timeout
        self.clean_aux = clean_aux

    def compile(self, tex_file: Path, output_dir: Optional[Path] = None) -> Path:
        """
        Compile the LaTeX file to PDF.
        
        Args:
            tex_file: Path to the .tex file.
            output_dir: Optional directory to place the output PDF. 
                        If None, uses the same directory as the source.
                        
        Returns:
            Path to the generated PDF.
        """
        if not tex_file.exists():
            raise FileNotFoundError(f"Source file not found: {tex_file}")

        work_dir = tex_file.parent
        cmd = [
            self.engine,
            "-interaction=nonstopmode",
            tex_file.name
        ]
        
        if output_dir:
            # -output-directory is supported by xelatex/pdflatex
            output_dir.mkdir(parents=True, exist_ok=True)
            cmd.append(f"-output-directory={output_dir.absolute()}")
            target_dir = output_dir
        else:
            target_dir = work_dir

        try:
            # Run compilation twice for references
            for _ in range(2):
                subprocess.run(
                    cmd, 
                    cwd=work_dir, 
                    check=True, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    timeout=self.timeout
                )
        except subprocess.CalledProcessError as e:
            # Capture log output if possible
            log_file = target_dir / f"{tex_file.stem}.log"
            error_msg = f"Compilation failed."
            if log_file.exists():
                error_msg += f" Check log: {log_file}"
            raise RuntimeError(error_msg) from e
            
        pdf_file = target_dir / f"{tex_file.stem}.pdf"
        
        if self.clean_aux:
            self._cleanup(target_dir, tex_file.stem)
            
        return pdf_file

    def _cleanup(self, directory: Path, stem: str):
        """Remove auxiliary files."""
        extensions = ['.aux', '.log', '.out', '.toc', '.snm', '.nav']
        for ext in extensions:
            f = directory / f"{stem}{ext}"
            if f.exists():
                f.unlink()
