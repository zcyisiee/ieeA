#!/usr/bin/env python3
import tempfile
from pathlib import Path

from ieeA.compiler.chinese_support import inject_chinese_support
from ieeA.compiler.engine import TeXCompiler


def main() -> int:
    font_config = {
        "auto_detect": False,
        "main": "Source Han Serif SC",
        "sans": "Source Han Sans SC",
        "mono": "Source Han Mono SC",
    }

    latex_source = r"""\documentclass{article}
\usepackage{fontspec}
\begin{document}
中文测试 Chinese Test
\textbf{粗体} \textit{斜体}
\texttt{等宽}
\end{document}
"""

    latex_source = inject_chinese_support(latex_source, font_config=font_config)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        tex_file = tmp_path / "font_test.tex"
        tex_file.write_text(latex_source, encoding="utf-8")

        compiler = TeXCompiler(engine="xelatex", timeout=120, clean_aux=True)
        compiler.compile(tex_file)

    print("OK: XeLaTeX loaded Source Han CJK fonts successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
