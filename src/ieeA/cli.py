import asyncio
import os
import shutil
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text

from ieeA.compiler import LaTeXCompiler
from ieeA.downloader.arxiv import ArxivDownloader
from ieeA.parser.latex_parser import LaTeXParser
from ieeA.rules.config import load_config
from ieeA.rules.glossary import load_glossary
from ieeA.rules.examples import load_examples
from ieeA.translator import get_sdk_client
from ieeA.translator.pipeline import TranslationPipeline
from ieeA.translator.logger import TranslationLogger
from ieeA.validator.engine import ValidationEngine

app = typer.Typer(
    name="ieeA",
    help="ieeA - arXiv Paper Translator",
    add_completion=False,
    no_args_is_help=True,
)
config_app = typer.Typer(help="Manage configuration")
glossary_app = typer.Typer(help="Manage glossary terms")
app.add_typer(config_app, name="config")
app.add_typer(glossary_app, name="glossary")

console = Console()

CONFIG_DIR = Path.home() / ".ieeA"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
GLOSSARY_FILE = CONFIG_DIR / "glossary.yaml"


def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


@app.command()
def translate(
    arxiv_url: str = typer.Argument(..., help="arXiv ID or URL to translate"),
    output_dir: Path = typer.Option(
        Path("output"), "-o", "--output-dir", help="Directory to save results"
    ),
    sdk: Optional[str] = typer.Option(
        None, help="SDK to use (openai, anthropic, or None for direct HTTP)"
    ),
    model: Optional[str] = typer.Option(None, help="Model name to use"),
    key: Optional[str] = typer.Option(None, help="API Key"),
    endpoint: Optional[str] = typer.Option(None, help="API endpoint URL"),
    no_compile: bool = typer.Option(False, help="Skip PDF compilation"),
    keep_source: bool = typer.Option(False, help="Keep downloaded source files"),
    concurrency: int = typer.Option(
        50,
        "-c",
        "--concurrency",
        help="Max concurrent API requests (lower = safer for rate limits)",
    ),
    high_quality: bool = typer.Option(
        False,
        "--high-quality",
        "-hq",
        help="启用高质量翻译模式，为每个 chunk 提供摘要上下文",
    ),
    abstract: Optional[str] = typer.Option(
        None, "--abstract", help="手动提供摘要文本（覆盖自动提取）"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="启用详细日志输出到控制台",
    ),
):
    """
    Translate an arXiv paper to Chinese.
    """
    # Load configuration
    config = load_config()

    # Overrides
    sdk_name = sdk or config.llm.sdk
    model_name = model or config.llm.get_model()
    key_val = key or config.llm.key
    endpoint_val = endpoint or config.llm.endpoint

    if sdk_name is not None and not key_val:
        console.print(
            f"[bold red]Error:[/bold red] API key not found. "
            f"Please set llm.key in config or use --key."
        )
        raise typer.Exit(code=1)

    console.print(
        Panel.fit(
            f"[bold blue]ieeA Translation Pipeline[/bold blue]\n"
            f"Target: [cyan]{arxiv_url}[/cyan]\n"
            f"SDK: [green]{sdk_name or 'HTTP'}[/green] ({model_name})\n"
            f"Output: [yellow]{output_dir}[/yellow]",
            title="Starting Job",
        )
    )

    async def run_pipeline():
        try:
            # 1. Download
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Downloading source...", total=None)
                downloader = ArxivDownloader()
                try:
                    download_result = downloader.download(arxiv_url, output_dir)
                    progress.update(
                        task, description=f"Downloaded: {download_result.arxiv_id}"
                    )
                except Exception as e:
                    progress.update(
                        task, description=f"[red]Download failed: {e}[/red]"
                    )
                    raise

            # 2. Parse
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Parsing LaTeX...", total=None)
                parser = LaTeXParser()
                try:
                    doc = parser.parse_file(str(download_result.main_tex))
                    progress.update(
                        task, description=f"Parsed {len(doc.chunks)} chunks"
                    )
                except Exception as e:
                    progress.update(task, description=f"[red]Parsing failed: {e}[/red]")
                    raise

            # 3. Translate
            # Initialize translation logger
            translation_logger = TranslationLogger(
                output_dir=output_dir / download_result.arxiv_id,
                verbose=verbose,
                hq_mode=high_quality,
            )
            translation_logger.set_source_file(str(download_result.main_tex))
            translation_logger.start_timing()

            console.print("\n[bold]Translating...[/bold]")
            glossary = load_glossary()
            provider = get_sdk_client(
                sdk_name,
                model=model_name,
                key=key_val,
                endpoint=endpoint_val,
                temperature=config.llm.temperature,
            )

            # Prepare high-quality mode parameters
            abstract_text = None
            examples = []
            if high_quality:
                # Get abstract: CLI argument > extracted abstract > fallback
                abstract_text = abstract or getattr(doc, "abstract", "") or ""
                # Load few-shot examples
                examples_path = getattr(config.translation, "examples_path", None)
                examples = (
                    load_examples(examples_path) if examples_path else load_examples()
                )
                console.print(
                    f"[cyan]High-quality mode enabled: {len(examples)} examples loaded[/cyan]"
                )

            pipeline = TranslationPipeline(
                provider=provider,
                glossary=glossary,
                state_file=output_dir
                / download_result.arxiv_id
                / "translation_state.json",
                few_shot_examples=examples,
                abstract_context=abstract_text,
                custom_system_prompt=config.translation.custom_system_prompt,
            )

            chunk_data = [{"chunk_id": c.id, "content": c.content} for c in doc.chunks]

            console.print(
                f"[bold]Translating {len(chunk_data)} chunks (max {concurrency} concurrent)...[/bold]"
            )

            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task_id = progress.add_task(
                    "Translating chunks...", total=len(chunk_data)
                )

                def update_progress(completed: int, total: int):
                    progress.update(task_id, completed=completed, total=total)

                translated_chunks = await pipeline.translate_document(
                    chunks=chunk_data,
                    context="Academic Paper",
                    max_concurrent=concurrency,
                    progress_callback=update_progress,
                )

            results = [tc.model_dump() for tc in translated_chunks]
            console.print(f"[green]Translation complete: {len(results)} chunks[/green]")

            # Reconstruct
            translated_map = {r["chunk_id"]: r["translation"] for r in results}
            translated_tex = doc.reconstruct(translated_map)

            # Save
            out_file = download_result.main_tex.parent / "main_translated.tex"
            out_file.write_text(translated_tex, encoding="utf-8")
            console.print(f"[green]Translation saved to {out_file}[/green]")

            # Save translation log
            log_path = translation_logger.save()
            if log_path:
                if verbose:
                    console.print(f"[green]Log saved to {log_path}[/green]")

            # 4. Validate
            console.print("\n[bold]Validating...[/bold]")
            validator = ValidationEngine()

            # Extract original text for validation
            original_full = doc.reconstruct()

            val_result = validator.validate(translated_tex, original_full)

            if val_result.valid:
                console.print("[green]Validation Passed[/green]")
            else:
                console.print(
                    f"[yellow]Validation Issues ({len(val_result.errors)}):[/yellow]"
                )
                for err in val_result.errors:
                    color = "red" if err.severity == "error" else "yellow"
                    console.print(f"[{color}]- {err.message}[/{color}]")
                    if err.suggestion:
                        console.print(f"  Suggestion: {err.suggestion}", style="dim")

            # 5. Compile
            if not no_compile:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[bold blue]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task("Compiling PDF...", total=None)
                    compiler = LaTeXCompiler(timeout=config.compilation.timeout)
                    try:
                        latex_source = out_file.read_text(encoding="utf-8")
                        # Inject Chinese font support before compilation
                        latex_source = compiler.inject_chinese_support(latex_source)
                        # Save the final version that will be compiled (for debugging)
                        out_file.write_text(latex_source, encoding="utf-8")
                        pdf_path = (
                            output_dir
                            / download_result.arxiv_id
                            / f"{download_result.arxiv_id}.pdf"
                        )
                        result = compiler.compile(
                            latex_source,
                            pdf_path,
                            working_dir=download_result.main_tex.parent,
                        )
                        if result.success:
                            progress.update(
                                task, description=f"Compiled: {result.pdf_path}"
                            )
                            console.print(
                                Panel(
                                    f"[bold green]Success![/bold green]\nPDF: {result.pdf_path}"
                                )
                            )
                        else:
                            progress.update(
                                task, description=f"[red]Compilation failed[/red]"
                            )
                            console.print(
                                f"[yellow]Error: {result.error_message}[/yellow]"
                            )
                            console.print(
                                "[yellow]Generated .tex file is saved. You may try compiling it manually.[/yellow]"
                            )
                    except Exception as e:
                        progress.update(
                            task, description=f"[red]Compilation failed: {e}[/red]"
                        )
                        console.print(
                            "[yellow]Generated .tex file is saved. You may try compiling it manually.[/yellow]"
                        )

        except Exception as e:
            console.print(f"[bold red]Pipeline failed:[/bold red] {e}")
            raise typer.Exit(code=1)

    asyncio.run(run_pipeline())


@config_app.command("show")
def config_show():
    """Show current configuration."""
    config = load_config()
    console.print(config.model_dump())


@config_app.command("set")
def config_set(key: str, value: str):
    """
    Set a configuration value (dot-separated).
    Example: ieeA config set llm.model gpt-4
    """
    ensure_config_dir()

    # Load raw yaml to preserve structure if possible, or just dict
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    # Update nested key
    keys = key.split(".")
    current = data
    for k in keys[:-1]:
        if k not in current:
            current[k] = {}
        current = current[k]
        if not isinstance(current, dict):
            console.print(f"[red]Error: {k} is not a dictionary[/red]")
            raise typer.Exit(1)

    # Attempt type conversion
    val = value
    if value.lower() == "true":
        val = True
    elif value.lower() == "false":
        val = False
    elif value.isdigit():
        val = int(value)
    else:
        try:
            val = float(value)
        except ValueError:
            pass

    current[keys[-1]] = val

    with open(CONFIG_FILE, "w") as f:
        yaml.dump(data, f)

    console.print(f"[green]Updated {key} = {val}[/green]")


@glossary_app.command("add")
def glossary_add(
    term: str = typer.Argument(..., help="Term to add"),
    translation: str = typer.Argument(..., help="Translation of the term"),
    domain: Optional[str] = typer.Option(None, help="Domain context"),
    notes: Optional[str] = typer.Option(None, help="Additional notes"),
):
    """Add a term to the glossary."""
    ensure_config_dir()

    if GLOSSARY_FILE.exists():
        with open(GLOSSARY_FILE, "r") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    data[term] = {"target": translation, "domain": domain, "notes": notes}

    with open(GLOSSARY_FILE, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True)

    console.print(f"[green]Added term:[/green] {term} -> {translation}")


@app.command()
def validate(
    tex_file: Path = typer.Argument(..., exists=True, help="Path to .tex file"),
    original_file: Optional[Path] = typer.Option(
        None, help="Original .tex file for comparison"
    ),
):
    """
    Validate a LaTeX file.
    """
    with open(tex_file, "r", encoding="utf-8") as f:
        content = f.read()

    original = ""
    if original_file and original_file.exists():
        with open(original_file, "r", encoding="utf-8") as f:
            original = f.read()

    validator = ValidationEngine()
    result = validator.validate(content, original)

    if result.valid:
        console.print("[green]File is valid![/green]")
    else:
        console.print(f"[red]Found {len(result.errors)} errors[/red]")
        for err in result.errors:
            console.print(f"- {err.message} ({err.severity})")


def main():
    app()


if __name__ == "__main__":
    main()
